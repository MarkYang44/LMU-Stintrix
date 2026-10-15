"""Explicit participation and phase partitions for every derived analysis."""
from library import session_label
from race_mode import mode

def phase(value):
    meta=value.get('session')
    if isinstance(meta,dict):return session_label(meta.get('session'))
    return value.get('phase') or value.get('session_type') or session_label(meta)

def check(anchor,candidate,policy):
    a,b=mode(anchor),mode(candidate);pa,pb=phase(anchor),phase(candidate)
    different=[];unknown=[]
    if a!=b:different.append('mode')
    if pa!=pb:different.append('phase')
    if 'unknown' in (a,b):unknown.append('参赛方式')
    if 'Unknown' in (pa,pb):unknown.append('阶段')
    allowed=(a==b or policy.get('cross_mode',False)) and (pa==pb or policy.get('cross_phase',False))
    return dict(allowed=allowed,mixed=bool(different),unknown=unknown,mode=b,phase=pb)
