"""Comparable-condition policy. Unknowns stay unknown; no corrected lap predictions."""
import math
from functools import partial
from types import MappingProxyType
from lap_identity import text
from i18n import tr

DEFAULTS=dict(fuel_l=2.,track_temp_c=5.,ambient_temp_c=5.,wetness=.1,rain=.05,include_unknown=False,min_laps=3,cross_mode=False,cross_phase=False)
_NUMERIC=(('fuel_l',0,2000),('track_temp_c',-100,150),('ambient_temp_c',-100,100),('wetness',0,1),('rain',0,1),('track_grip',0,255),('tc_level',0,255),('abs_level',0,255))

def settings(value=None):
    out=dict(DEFAULTS);out.update(value or {})
    for key,limit in (('fuel_l',20),('track_temp_c',20),('ambient_temp_c',20),('wetness',.5),('rain',.5)):
        v=float(out[key])
        if not math.isfinite(v) or not 0<=v<=limit:raise ValueError('Invalid condition tolerance: '+key)
        out[key]=v
    out['min_laps']=int(out['min_laps'])
    if not 3<=out['min_laps']<=20:raise ValueError(tr('至少需要 3 个有效圈评价稳定性'))
    for key in ('include_unknown','cross_mode','cross_phase'):
        if not isinstance(out[key],bool):raise ValueError(key+' must be a boolean')
    return out

def match(a,b,policy=None):
    return _match(a,b,settings(policy))


def matcher(reference,policy=None):
    """One job's frozen reference/config; every candidate still gets full checks."""
    return partial(_match,dict(reference),p=MappingProxyType(settings(policy)))


def _match(a,b,p):
    unknown=[];different=[];known=[]
    for key,low,high in _NUMERIC:
        x,y=a.get(key),b.get(key)
        if not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or not isinstance(y,(int,float)) or isinstance(y,bool) or not math.isfinite(y):unknown.append(key);continue
        if not (low<=x<=high and low<=y<=high):unknown.append(key);continue
        known.append(key)
        if abs(x-y)>p.get(key,0):different.append(key)
    for name,index in (('tyre_front_name','tyre_compound'),('tyre_rear_name','tyre_rear_compound')):
        if a.get(name) and b.get(name):
            known.append(name)
            if text(a[name])!=text(b[name]):different.append(name)
        elif all(isinstance(o.get(index),(int,float)) and math.isfinite(o[index]) and 0<=o[index]<=255 and float(o[index]).is_integer() for o in (a,b)):
            known.append(index)
            if a[index]!=b[index]:different.append(index)
        else:unknown.append(name)
    return dict(allowed=not different and (p['include_unknown'] or not unknown),unknown=unknown,different=different,known=known)
