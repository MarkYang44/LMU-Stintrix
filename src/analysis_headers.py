"""Small sidecars and bounded process-local headers; never retain sample tables."""
from collections import OrderedDict
import json
from pathlib import Path
from threading import RLock
from stat import S_ISREG
from json_store import Reader
from race_model import read_json
from storage import atomic_json

_cache=OrderedDict();_lock=RLock()
_MAX_ENTRIES=4;_MAX_BYTES=256*1024


def _signature(folder):
    result=[]
    for name in ('session_analysis.json','analysis_index.json'):
        path=folder/name
        try:
            stat=path.stat();stamp=(stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_ino) if name!='session_analysis.json' or S_ISREG(stat.st_mode) else None
        except FileNotFoundError:stamp=None
        result.append((str(path),stamp))
    return tuple(result)


def _payload(value):
    # Store only bounded JSON bytes, with isolated return values on cache hits.
    # Unsupported objects (including DiskTable) and large headers are not kept.
    chunks=[];size=0
    try:
        for chunk in json.JSONEncoder(ensure_ascii=False,separators=(',',':')).iterencode(value):
            chunk=chunk.encode('utf-8');size+=len(chunk)
            if size>_MAX_BYTES:return None
            chunks.append(chunk)
    except (TypeError,ValueError,UnicodeError):return None
    return b''.join(chunks)


def _metadata_only(value):
    """Only the generated scalar/dictionary header shape may enter sidecar cache."""
    if not isinstance(value,dict) or set(value)-{'laps','recent_stability','stable_reference_file'}:return False
    def plain(item):
        if isinstance(item,dict):return not set(item)&{'profile','trajectory','vehicle_summary','action','data','features'} and all(plain(v) for v in item.values())
        return type(item) in (str,int,float,bool,type(None))
    laps=value.get('laps',[])
    return isinstance(laps,list) and all(isinstance(lap,dict) and plain(lap) for lap in laps) and all(plain(v) for k,v in value.items() if k!='laps')


def load(folder):
    folder=Path(folder).absolute();path=folder/'session_analysis.json'
    signature=_signature(folder)
    if signature[0][1] is None:return {}
    with _lock:
        cached=_cache.pop(signature,None)
        if cached is not None:_cache[signature]=cached
    valid=False
    if cached is not None:value=json.loads(cached)
    else:
        sidecar=read_json(folder/'analysis_index.json',{});source=signature[0][1]
        valid=sidecar.get('source_size')==source[0] and sidecar.get('source_mtime_ns')==source[1]
        value=sidecar.get('headers',{}) if valid else _read(path)
    if _signature(folder)!=signature:raise OSError('赛事分析已变化，请重试')
    if cached is None:
        side=signature[1][1]
        payload=_payload(value) if not valid or side is not None and side[0]<=_MAX_BYTES and _metadata_only(value) else None
        if payload is not None:
            with _lock:
                _cache[signature]=payload
                while len(_cache)>_MAX_ENTRIES:_cache.popitem(last=False)
    return value


def _read(path):
    class Headers(Reader):
        def value(self,key='',depth=0,keep=True):
            return super().value(key,depth,keep and key not in ('profile','trajectory','vehicle_summary','action','data','features'))
    with path.open(encoding='utf-8-sig') as stream:value=Headers(stream,fields=('laps','recent_stability','stable_reference_file')).value()
    if isinstance(value,dict):
        value['laps']=[{k:v for k,v in lap.items() if k not in ('profile','trajectory','vehicle_summary','action','data','features')} for lap in value.get('laps',[]) if isinstance(lap,dict)]
    return value

def save(folder,value):
    folder=Path(folder);stat=(folder/'session_analysis.json').stat()
    headers=dict(laps=[{k:v for k,v in lap.items() if k not in ('profile','trajectory','vehicle_summary','action','features','data')} for lap in value.get('laps',[])],recent_stability=value.get('recent_stability',{}),stable_reference_file=value.get('stable_reference_file'))
    atomic_json(folder/'analysis_index.json',dict(version=1,source_size=stat.st_size,source_mtime_ns=stat.st_mtime_ns,headers=headers))
