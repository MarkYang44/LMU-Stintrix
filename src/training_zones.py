"""User-defined distance zones and bounded measured trace features."""
import hashlib,json,math
from pathlib import Path
from storage import atomic_json
from lap_identity import text
from i18n import tr

def path(root,entry):
    key=(text(entry['track']),text(entry['layout']),round(entry['length_m'],1))
    return Path(root)/'PersonalRecords/TrainingZones'/(hashlib.sha256(repr(key).encode()).hexdigest()[:24]+'.json')

def validate(zones,length):
    if not isinstance(zones,list) or not 1<=len(zones)<=64:raise ValueError(tr('需要 1–64 个分析区间'))
    out=[]
    for i,z in enumerate(zones):
        a=float(z['start']);b=float(z['end']);apex=float(z.get('apex',(a+b)/2));name=str(z.get('name','')).strip()
        if not all(math.isfinite(v) for v in (a,b,apex)) or not 0<=a<apex<b<=length or b-a<5:raise ValueError(tr('区间须满足 0 ≤ 起点 < 弯心 < 终点 ≤ 赛道长度，长度至少 5 m'))
        if not name or len(name)>60:raise ValueError(tr('区间名称须为 1–60 个字符'))
        out.append(dict(name=name,start=a,end=b,apex=apex,source='user_distance'))
    out.sort(key=lambda z:z['start'])
    if any(b['start']<a['end'] for a,b in zip(out,out[1:])):raise ValueError(tr('分析区间不能重叠'))
    return out

def load(root,entry):
    p=path(root,entry)
    if not p.is_file():return None
    value=json.loads(p.read_text(encoding='utf-8-sig'));return validate(value['zones'],entry['length_m'])

def save(root,entry,zones):
    values=validate(zones,entry['length_m']);p=path(root,entry);p.parent.mkdir(parents=True,exist_ok=True)
    saved=json.loads(p.read_text(encoding='utf-8-sig')) if p.is_file() else {}
    if not isinstance(saved,dict):raise ValueError('Invalid zone settings')
    updated={**saved,**dict(version=1,zones=values,length_m=entry['length_m'])}
    if updated!=saved:atomic_json(p,updated)
    return values

def features(rows,start,end,length):
    from analysis_spool import numeric_rows
    rows=numeric_rows(rows,('session_time_s','lap_distance_m','throttle','brake','abs_active','tc_active','world_x_m','world_z_m'))
    intervals={k:[] for k in ('coast','abs','tc')};known={k:0. for k in intervals};coverage={k:[] for k in intervals};geometry=[];last=None;last_d=-1.;step=length/600
    def numeric(v):
        return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
    for r in rows:
        t=r['session_time_s'];d=r['lap_distance_m']
        if t<start or t>end or not 0<=d<=length:continue
        x,z=r.get('world_x_m'),r.get('world_z_m')
        if numeric(x) and numeric(z) and d-last_d>=step and len(geometry)<601:geometry.append([d,x,z]);last_d=d
        if last:
            dt=t-last['session_time_s'];a=last['lap_distance_m']
            if 0<dt<=.5 and 0<=a<=d<=length:
                states={'coast':last['throttle']<.03 and last['brake']<.03}
                for k in ('abs','tc'):
                    v=last.get(k+'_active');states[k]=bool(v) if numeric(v) and v in (0,1) else None
                for k,state in states.items():
                    if state is None:continue
                    known[k]+=dt
                    cov=coverage[k]
                    if cov and abs(cov[-1][1]-a)<.01:cov[-1][1]=d;cov[-1][2]+=dt
                    else:cov.append([a,d,dt])
                    if state:
                        values=intervals[k]
                        if values and abs(values[-1][1]-a)<.01:values[-1][1]=d;values[-1][2]+=dt
                        elif len(values)<8192:values.append([a,d,dt])
                        else:raise ValueError('Too many activation intervals')
        last=r
    return dict(intervals=intervals,known_s=known,coverage=coverage,geometry=geometry)

def feature_time(lap,zone,key,expected=None):
    f=lap.get('features')
    if not f or not f['known_s'].get(key):return None
    def duration(values):
        total=0
        for a,b,dt in values:
            overlap=max(0,min(b,zone['end'])-max(a,zone['start']))
            if b>a:total+=dt*overlap/(b-a)
            elif zone['start']<=a<zone['end']:total+=dt
        return total
    from training_report import interpolate
    if expected is None:expected=interpolate(lap['data'],zone['end'])[1]-interpolate(lap['data'],zone['start'])[1]
    if duration(f.get('coverage',{}).get(key,[]))<expected*.95:return None
    return duration(f['intervals'][key])
