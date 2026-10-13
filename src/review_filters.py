"""Stable inventory IDs, combined UTC filters and deterministic sorting."""
from datetime import datetime,time,timedelta,timezone
from track_names import display,search_text

SORTS=('时间：最新优先','时间：最早优先','阶段：升序','阶段：降序','赛道：升序','赛道：降序','车辆：升序','车辆：降序')
PERIODS=('全部时间','今天','最近 7 天','最近 30 天')

def stamp(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return (d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d).astimezone(timezone.utc)
    except (ValueError,TypeError):return None

def filtered(items,state,query='',now=None):
    now=now or datetime.now(timezone.utc);start=end=None
    for key in ('start','end'):
        value=state.get(key,'').strip()
        if value:
            try:d=datetime.strptime(value,'%Y-%m-%d').date()
            except ValueError:raise ValueError('日期请填写 YYYY-MM-DD') from None
            if key=='start':start=datetime.combine(d,time.min,timezone.utc)
            else:end=datetime.combine(d+timedelta(days=1),time.min,timezone.utc)
    if start and end and start>=end:raise ValueError('开始日期不能晚于结束日期')
    days={1:1,2:7,3:30}.get(state.get('period',0))
    cutoff=datetime.combine(now.date()-timedelta(days=days-1),time.min,timezone.utc) if days else None
    term=query.strip().casefold();out=[]
    for i,value in enumerate(items):
        d=stamp(value.get('date'))
        if any(state.get(k) and value.get(field)!=state[k] for k,field in (('phase','session_type'),('track','track'),('car','vehicle'))):continue
        if (start or end or cutoff) and (d is None or start and d<start or end and d>=end or cutoff and d<cutoff or d>now):continue
        if term and term not in (search_text(value.get('track'))+' '+search_text(value.get('track_layout'))+' '+' '.join(str(value.get(k,'')) for k in ('vehicle','session_type','date','driver'))).casefold():continue
        out.append((i,value))
    order=state.get('sort',0);column=('date','date','session_type','session_type','track','track','vehicle','vehicle')[order]
    def key(pair):
        v=pair[1]
        if column=='date':return (stamp(v.get('date')) or datetime.min.replace(tzinfo=timezone.utc),str(v.get('folder','')))
        name=display(v.get(column,'')) if column=='track' else str(v.get(column,''))
        return (name.casefold(),str(v.get('date','')),str(v.get('folder','')))
    out.sort(key=key,reverse=order in (0,3,5,7));return out
