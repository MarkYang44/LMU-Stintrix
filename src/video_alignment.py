"""Conservative video time maps; no speed-integrated pseudo lap distance."""
import bisect
from array import array
from collections.abc import Sequence
import json
import math
from pathlib import Path
from video_signal import number


class Samples(Sequence):
    """Four numeric columns, avoiding a Python object for every source sample."""
    def __init__(self):self.data=array('d')
    def append(self,row):self.data.extend(row)
    def __len__(self):return len(self.data)//4
    def __getitem__(self,i):
        if i<0:i+=len(self)
        if not 0<=i<len(self):raise IndexError(i)
        return tuple(self.data[i*4:i*4+4])


def native_data(path,cancel=None,channel='filtered'):
    """Read exported lap headers and keep at most 60 Hz for a <=30 Hz video."""
    from json_store import Reader
    from video_media import Cancelled
    class NativeReader(Reader):
        def value(self,key='',depth=0,keep=True):
            if depth==1 and key=='data_columns' and keep:
                value=super().value(key,depth,keep)
                pedals=('filtered_throttle','filtered_brake') if channel=='filtered' else ('throttle','brake')
                self.indices=[value.index(k) for k in ('lap_time_s','distance_m',*pedals)]
                return value
            if depth!=1 or key!='data' or not keep:return super().value(key,depth,keep)
            if not hasattr(self,'indices'):raise ValueError('单圈 JSON 的 data_columns 必须位于 data 前')
            self.require('[');samples=Samples();previous=None;last_kept=-math.inf;count=0
            while True:
                if cancel and cancel.is_set():raise Cancelled('已取消')
                self.space()
                if self.peek()==']':self.pos+=1;break
                raw=self.row(depth+1,True);row=tuple(number(raw[i],0) for i in self.indices)
                if row[0]>1800 or row[2]>1 or row[3]>1:raise ValueError('遥测圈时 / 输入值超出范围')
                if previous and (row[0]<=previous[0] or row[1]<previous[1]-.5):raise ValueError('遥测时间 / 距离倒退')
                if row[0]-last_kept>=1/60-1e-7:samples.append(row);last_kept=row[0]
                previous=row;count+=1
                if count>7200001:raise ValueError('单圈遥测采样过多')
                self.space();char=self.peek();self.pos+=1
                if char==']':break
                if char!=',':raise ValueError('单圈数据分隔符无效')
            if previous and samples[-1][0]!=previous[0]:samples.append(previous)
            return samples
    with Path(path).open(encoding='utf-8-sig') as stream:
        value=NativeReader(stream,fields=('format','lap','session','data_columns','data')).value()
    return value


def native_header(path):
    """Small exported-lap headers for the picker; no curve materialization."""
    from json_store import Reader
    class Ready(Exception):pass
    class Headers(Reader):
        def __init__(self,stream):super().__init__(stream);self.headers={}
        def value(self,key='',depth=0,keep=True):
            if depth==1 and key=='data':raise Ready()
            selected=keep and (depth!=1 or key in ('format','lap','session'))
            value=super().value(key,depth,selected)
            if depth==1 and selected:self.headers[key]=value
            return value
    with Path(path).open(encoding='utf-8-sig') as stream:
        reader=Headers(stream)
        try:reader.value()
        except Ready:pass
        if not {'format','lap','session'}<=reader.headers.keys():raise ValueError('单圈 JSON 头不完整')
        return reader.headers


def native_lap(path, identity, cancel=None):
    path=Path(path)
    if path.stat().st_size>1024*1024*1024:raise ValueError('请选择小于 1 GiB 的单圈 JSON，而非整场记录')
    value=native_data(path,cancel)
    if value.get('format')!='inputscope.fastest-lap' or value.get('lap',{}).get('validity')!='verified':
        raise ValueError('需要插件导出的已验证完整圈 .lap.json；官方 DuckDB 请先通过“导入官方遥测”导入')
    lap=value['lap'];session=value.get('session',{})
    if lap.get('in_pits') or lap.get('lap_invalidated'):raise ValueError('遥测圈不能是无效圈或进站圈')
    for key in ('track','track_layout'):
        if not session.get(key) or str(session[key]).strip().casefold()!=str(identity[key]).strip().casefold():
            raise ValueError('遥测与所选赛道 / 布局不一致；使用相同的原始名称')
    if abs(number(lap.get('track_length_m'),100)-identity['length_m'])>2:
        raise ValueError('遥测赛道长度不一致')
    samples=value['data']
    if len(samples)<10:raise ValueError('遥测样本不足')
    if samples[0][1]>20 or samples[-1][1]<identity['length_m']-30:raise ValueError('遥测缺少完整距离覆盖')
    return dict(samples=samples,duration=number(lap['time_s'],1),file=path.name,
                vehicle=session.get('vehicle',''),channel='filtered_throttle / filtered_brake')


def sync_map(anchors, start, end, duration):
    if len(anchors)<2:raise ValueError('同圈遥测至少需要两个同步点：视频秒数 = 遥测圈内秒数')
    pairs=sorted((number(a,start,end),number(b,0,duration)) for a,b in anchors)
    if any(b[0]<=a[0] or b[1]<=a[1] for a,b in zip(pairs,pairs[1:])):raise ValueError('同步点需要严格递增')
    if pairs[-1][0]-pairs[0][0]<(end-start)*.8:raise ValueError('同步点必须覆盖至少 80% 的单圈时长')
    mx=sum(a for a,b in pairs)/len(pairs);my=sum(b for a,b in pairs)/len(pairs)
    scale=sum((a-mx)*(b-my) for a,b in pairs)/sum((a-mx)**2 for a,b in pairs)
    offset=my-scale*mx
    if not .98<=scale<=1.02:raise ValueError('视频与遥测时钟速率相差超过 2%；不支持变速 / 剪辑视频')
    residual=max(abs(scale*a+offset-b) for a,b in pairs)
    if residual>.1:raise ValueError('同步残差超过 0.1 秒；请检查同步点或视频剪辑')
    if abs(scale*start+offset)>.15 or abs(scale*end+offset-duration)>.2:
        raise ValueError('视频选段与遥测整圈边界不一致')
    return dict(scale=scale,offset=offset,residual_s=residual,anchors=pairs,
                independently_checked=len(pairs)>=3)


def interpolate(samples, target, max_gap=.25):
    # Samples are short numeric tuples. Binary search avoids per-frame time arrays.
    i=bisect.bisect_right(samples,(target,math.inf,math.inf,math.inf))
    if i and abs(samples[i-1][0]-target)<1e-6:return samples[i-1]
    if not 0<i<len(samples):return None
    a,b=samples[i-1],samples[i]
    if b[0]-a[0]>max_gap:return None
    ratio=(target-a[0])/(b[0]-a[0])
    return (target,*(a[j]+(b[j]-a[j])*ratio for j in range(1,len(a))))


def distance_readings(observations, start, length):
    accepted=[];previous=None;rejected=0
    for pts,distance,timer in observations:
        if distance is None or timer is None or not 0<=distance<=length+5 or abs(timer-(pts-start))>.25:
            rejected+=1;continue
        if previous:
            elapsed=pts-previous[0]
            if timer<previous[2] or distance<previous[1] or distance-previous[1]>140*elapsed+10:
                rejected+=1;continue
            if timer==previous[2] or distance==previous[1]:
                # Repeated overlay readings are not independent progress samples.
                rejected+=1;continue
        previous=(pts,distance,timer);accepted.append((pts-start,distance,timer))
    span=accepted[-1][1]-accepted[0][1] if accepted else 0
    gaps=[b[0]-a[0] for a,b in zip(accepted,accepted[1:])]
    quality=dict(readings=len(observations),accepted=len(accepted),rejected=rejected,
                 distance_coverage=span/length,max_gap_s=max(gaps,default=None))
    quality['usable']=len(accepted)>=10 and span/length>=.95 and max(gaps,default=math.inf)<=1.
    return accepted,quality


def distances_for_rows(rows, observations, max_gap=1.):
    for row in rows:
        sample=interpolate(observations,row['lap_time_s'],max_gap)
        if sample:row['distance_m']=sample[1]


def crossings(rows, distance, max_gap):
    valid=[r for r in rows if r.get('distance_m') is not None]
    values=[r['distance_m'] for r in valid]
    if any(b<a for a,b in zip(values,values[1:])):return None
    i=bisect.bisect_left(values,distance)
    if i<len(valid) and values[i]==distance:return valid[i]['lap_time_s']
    if not 0<i<len(valid):return None
    a,b=valid[i-1],valid[i]
    if b['lap_time_s']-a['lap_time_s']>max_gap or values[i]==values[i-1]:return None
    return a['lap_time_s']+(b['lap_time_s']-a['lap_time_s'])*(distance-values[i-1])/(values[i]-values[i-1])


def compare(a,b):
    if a.get('format')!='stintrix.video-curves' or b.get('format')!='stintrix.video-curves':
        raise ValueError('请选择本功能生成的 curve.json')
    if (any(str(a['identity'][k]).casefold()!=str(b['identity'][k]).casefold() for k in ('track','track_layout')) or
            abs(a['identity']['length_m']-b['identity']['length_m'])>2):raise ValueError('比较需要相同赛道、布局和长度')
    if a['id']==b['id']:raise ValueError('请选择两个不同的提取结果')
    marks_a={m['name']:m['video_s']-a['start_s'] for m in a.get('landmarks',[])}
    marks_b={m['name']:m['video_s']-b['start_s'] for m in b.get('landmarks',[])}
    common=[name for name in marks_a if name in marks_b];segments=[]
    for x,y in zip(common,common[1:]):
        if marks_b[y]<=marks_b[x]:raise ValueError('两圈的同名地标顺序不一致')
        ta=marks_a[y]-marks_a[x];tb=marks_b[y]-marks_b[x]
        segments.append(dict(name=x+' → '+y,a_s=ta,b_s=tb,delta_s=tb-ta))
    delta=[]
    if a['quality'].get('distance_usable') and b['quality'].get('distance_usable'):
        for d in range(0,int(a['identity']['length_m'])+1,10):
            ta=crossings(a['rows'],d,1);tb=crossings(b['rows'],d,1)
            delta.append([d,None if ta is None or tb is None else tb-ta])
    if not delta and not segments:raise ValueError('普通视频需要至少两个同名固定地标；距离模式需要通过距离覆盖检查')
    return dict(format='stintrix.video-comparison',version=1,identity=a['identity'],a=a['id'],b=b['id'],
                segments=segments,delta=delta,precision='估算 / 未经实录精度验收',
                note='Δ = B − A；负值表示 B 更快。地标必须是同一物理位置、同一过线判据。')
