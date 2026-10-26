"""Conservative metadata-only candidate list. Never auto-merges or deletes."""
from pathlib import Path
from event_filters import stamp
from event_catalog import normalize
from race_model import read_json
from storage import atomic_json
import json


def checked_state(path):
    if not path.exists():return {}
    try:value=json.loads(path.read_text('utf-8-sig'))
    except (OSError,ValueError) as error:raise ValueError('检查标记文件无法读取，原文件已保留') from error
    if not isinstance(value,dict) or not isinstance(value.get('checked',[]),list) or any(not isinstance(key,str) for key in value.get('checked',[])):raise ValueError('检查标记文件无法读取，原文件已保留')
    return value

def candidates(items,checked=()):
    groups={};out=[];checked=set(checked)
    for e in items:
        f=normalize(e)
        if f.get('phase')!='Race' or f.get('source') in ('official','DemoLogs'):continue
        meta=read_json(Path(e['folder'])/'session.json',{});start=stamp(meta.get('started_utc'));end=stamp(meta.get('ended_utc'))
        if not start:continue
        key=tuple(str(v or '').strip().casefold() for v in (f.get('track'),f.get('layout'),f.get('length_m'),f.get('vehicle'),meta.get('driver'),f.get('mode')))
        groups.setdefault(key,[]).append((start,end,e,f,meta))
    for values in groups.values():
        values.sort(key=lambda v:v[0])
        for a,b in zip(values,values[1:]):
            start,end,e,f,meta=a
            if not end or not 0<=(b[0]-end).total_seconds()<=900:continue
            if f.get('outcome') in ('finished','dnf','dq') or meta.get('status')=='recording':continue
            pair=e['folder']+'\n'+b[2]['folder']
            if pair in checked:continue
            out.append(dict(id=pair,first=e,second=b[2],gap_s=(b[0]-end).total_seconds(),reason=meta.get('end_reason','未知')))
    return out

def mark(root,key):
    path=Path(root)/'EventCatalog/split_checks.json';value=checked_state(path);checked=value.get('checked',[])
    if key in checked:return False
    checked.append(key);value.update(version=1,checked=checked[-4096:])
    path.parent.mkdir(parents=True,exist_ok=True);atomic_json(path,value);return True


def unmark(root,key):
    path=Path(root)/'EventCatalog/split_checks.json';value=checked_state(path);checked=value.get('checked',[])
    if key not in checked:return False
    value.update(checked=[item for item in checked if item!=key]);atomic_json(path,value);return True
