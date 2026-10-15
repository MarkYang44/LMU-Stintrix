"""Shared, pure filtering of compact facets; unknown never equals zero."""
import math,json
from datetime import datetime,time,timedelta,timezone
from event_catalog import normalize,number
from track_names import display,search_text,layout

SORTS=('时间：最新优先','时间：最早优先','阶段：升序','阶段：降序','赛道：升序','赛道：降序','车辆：升序','车辆：降序','单人优先','线上优先','最快圈：最快优先','同组完赛：名次优先','同组净提升：最多优先','总完赛：名次优先','总净提升：最多优先','比赛时长：最长优先','稳定性：波动最小','记录时长：最长优先')
TRUST={'official':'官方确认','telemetry':'遥测确认','observed':'末次观测','unknown':'未知','conflict':'成绩待核对'}
QUALITY={'valid':'有有效完整圈','gaps':'有采样缺口','partial':'没有有效完整圈','unknown':'完整性未知','xml_only':'仅官方成绩','write_error':'写盘异常','recording':'正在记录','conflict':'成绩待核对'}
DEFAULTS=dict(period=0,sort=0,phase='',track='',car='',mode='',start='',end='',layout='',vehicle_class='',team='',outcome='',trust='',quality='',weather='',front='',rear='',source='',favorite='',traffic='',tag='',available='',min_laps='',fuel_min='',fuel_max='',temp_min='',temp_max='',tc_min='',tc_max='',abs_min='',abs_max='',duration_min='',duration_max='')
CHOICES={
 'phase':('阶段',{'':'全部阶段','Race':'Race','Qualify':'Qualify','Practice':'Practice','Warmup':'Warmup'}),
 'mode':('参赛方式',{'':'全部参赛方式','single':'单人','online':'线上','unknown':'未知'}),
 'outcome':('比赛成绩',{'':'全部成绩','winner':'同组冠军','podium':'同组领奖台','top10':'同组前十','finished':'正常完赛','dnf':'未完赛（DNF）','dq':'取消资格（DQ）','unknown':'结果未知','gain':'同组名次提升'}),
 'trust':('成绩依据',{'':'全部成绩依据',**TRUST}),
 'quality':('数据质量',{'':'全部数据质量',**QUALITY}),
 'weather':('已记录圈天气',{'':'全部天气','dry':'干地（已知圈条件）','wet':'湿地（已知圈条件）','mixed':'干湿混合','unknown':'天气未知'}),
 'source':('记录来源',{'':'全部来源','Logs':'本机遥测','ImportedLogs':'导入遥测','RecoveredLogs':'恢复 / 合并遥测','DemoLogs':'演示','official':'官方 XML'}),
 'favorite':('收藏',{'':'全部收藏状态','yes':'仅收藏','no':'未收藏'}),
 'traffic':('交通人工标记',{'':'全部交通标记','yes':'已标记交通影响','no':'未标记交通影响'}),
 'available':('可用数据',{'':'全部数据','has_telemetry':'有遥测','has_review':'有赛事复盘','has_timing':'有圈速单图片','has_journal':'有比赛日志图片'}),
}

def stamp(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return (d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d).astimezone(timezone.utc)
    except (ValueError,TypeError):return None

def layout_key(f):
    n=number(f.get('length_m'))
    return json.dumps([str(f.get('track','')).casefold().strip(),str(f.get('layout','')).casefold().strip(),round(n) if n else None],ensure_ascii=False)

def limits(state):
    out={}
    for prefix in ('fuel','temp','tc','abs','duration'):
        for bound in ('min','max'):
            key=prefix+'_'+bound;raw=state.get(key,'')
            if raw in ('',None):out[key]=None;continue
            try:v=float(raw)
            except (ValueError,TypeError):raise ValueError('范围请输入有效数字') from None
            if not math.isfinite(v) or prefix!='temp' and v<0:raise ValueError('范围数值无效')
            out[key]=v
        a,b=out[prefix+'_min'],out[prefix+'_max']
        if a is not None and b is not None and a>b:raise ValueError('最小值不能大于最大值')
    raw=state.get('min_laps','')
    if raw not in ('',None):
        try:v=float(raw)
        except (ValueError,TypeError):raise ValueError('有效圈数请输入非负整数') from None
        if not math.isfinite(v) or v<0 or v!=int(v):raise ValueError('有效圈数请输入非负整数')
        out['min_laps']=int(v)
    return out

def matches(f,state,bounds):
    for key in ('track','vehicle_class','team','phase','mode','source','trust','weather'):
        if state.get(key) and f.get(key)!=state[key]:return False
    if state.get('quality')=='valid':
        if f.get('has_valid_lap') is not True and f.get('quality')!='valid':return False
    elif state.get('quality') and f.get('quality')!=state['quality']:return False
    if state.get('car') and f.get('vehicle')!=state['car']:return False
    if state.get('layout') and layout_key(f)!=state['layout']:return False
    for key in ('favorite','traffic'):
        if state.get(key) and bool(f.get(key))!=(state[key]=='yes'):return False
    if state.get('tag') and state['tag'] not in f.get('tags',[]):return False
    if state.get('available') and f.get(state['available']) is not True:return False
    if 'min_laps' in bounds and (number(f.get('valid_laps')) is None or f['valid_laps']<bounds['min_laps']):return False
    outcome=state.get('outcome')
    if outcome:
        if outcome in ('winner','podium','top10','gain'):
            if f.get('phase')!='Race' or f.get('outcome')!='finished' or f.get('trust') not in ('official','telemetry'):return False
            p=f.get('finish_class')
            if outcome=='winner' and p!=1 or outcome=='podium' and p not in (1,2,3) or outcome=='top10' and (p is None or p>10) or outcome=='gain' and (f.get('class_gain') is None or f['class_gain']<=0):return False
        elif f.get('outcome')!=outcome:return False
    for prefix,field,scale in (('fuel','fuel_l',1),('temp','track_temp_c',1),('tc','tc_level',1),('abs','abs_level',1),('duration','race_s',60)):
        low,high=bounds.get(prefix+'_min'),bounds.get(prefix+'_max')
        if low is None and high is None:continue
        a=number(f.get(field+'_min' if prefix!='duration' else field));b=number(f.get(field+'_max' if prefix!='duration' else field))
        if a is None or b is None or low is not None and a<low*scale or high is not None and b>high*scale:return False
    for axle in ('front','rear'):
        wanted=state.get(axle,'')
        if wanted and wanted.casefold() not in [v.casefold() for v in f.get(axle+'_tyres',[])]:return False
    return True

def filtered(values,state,query='',now=None):
    now=now or datetime.now(timezone.utc);bounds=limits(state);start=end=None
    for key in ('start','end'):
        raw=str(state.get(key,'') or '').strip()
        if not raw:continue
        try:d=datetime.strptime(raw,'%Y-%m-%d').date()
        except ValueError:raise ValueError('日期请填写 YYYY-MM-DD') from None
        if key=='start':start=datetime.combine(d,time.min,timezone.utc)
        else:end=datetime.combine(d+timedelta(days=1),time.min,timezone.utc)
    if start and end and start>=end:raise ValueError('开始日期不能晚于结束日期')
    days={1:1,2:7,3:30}.get(state.get('period',0));cutoff=datetime.combine(now.date()-timedelta(days=days-1),time.min,timezone.utc) if days else None
    term=str(query or '').strip().casefold();rows=[]
    for i,e in enumerate(values):
        f=normalize(e);d=stamp(f.get('date'))
        if not matches(f,state,bounds):continue
        if (start or end or cutoff) and (d is None or start and d<start or end and d>=end or cutoff and d<cutoff or d>now):continue
        text=' '.join(str(f.get(k,'')) for k in ('vehicle','vehicle_class','team','phase','date','note','tags'))+' '+search_text(f.get('track'))+' '+search_text(f.get('layout'))+' '+layout(f.get('track'),f.get('layout'),f.get('length_m'))+' '+{'Race':'正赛','Qualify':'排位赛','Practice':'练习赛','Warmup':'热身赛'}.get(f.get('phase'),'')+' '+str((e.get('session') or e).get('driver',''))
        if term and term not in text.casefold():continue
        rows.append((i,e,f))
    rows.sort(key=lambda p:(stamp(p[2].get('date')) or datetime.min.replace(tzinfo=timezone.utc),str(p[1].get('folder',p[1].get('id','')))),reverse=True)
    order=state.get('sort',0);order=order if isinstance(order,int) and 0<=order<len(SORTS) else 0
    if order==1:rows.sort(key=lambda p:(stamp(p[2].get('date')) is None,stamp(p[2].get('date')) or datetime.max.replace(tzinfo=timezone.utc)))
    elif order in (2,3,4,5,6,7):
        key={2:'phase',3:'phase',4:'track',5:'track',6:'vehicle',7:'vehicle'}[order]
        known=[p for p in rows if p[2].get(key)];unknown=[p for p in rows if not p[2].get(key)]
        known.sort(key=lambda p:(display(p[2][key]) if key=='track' else str(p[2][key])).casefold(),reverse=order in (3,5,7));rows=known+unknown
    elif order in (8,9):
        wanted='single' if order==8 else 'online';rows.sort(key=lambda p:0 if p[2].get('mode')==wanted else 2 if p[2].get('mode')=='unknown' else 1)
    elif order>=10:
        key={10:'time_s',11:'finish_class',12:'class_gain',13:'finish',14:'gain',15:'race_s',16:'stability_s',17:'recorded_s'}[order];reverse=order in (12,14,15,17)
        known=[p for p in rows if number(p[2].get(key)) is not None];unknown=[p for p in rows if number(p[2].get(key)) is None]
        known.sort(key=lambda p:p[2][key],reverse=reverse);rows=known+unknown
    return [(i,e) for i,e,_ in rows]
