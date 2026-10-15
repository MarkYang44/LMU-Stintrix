"""Small analysis sidecars for new reports; stream legacy files without curves."""
from pathlib import Path
from json_store import Reader
from race_model import read_json
from storage import atomic_json

def load(folder):
    folder=Path(folder);path=folder/'session_analysis.json';cached=read_json(folder/'analysis_index.json',{})
    if not path.is_file():return {}
    stat=path.stat()
    if cached.get('source_size')==stat.st_size and cached.get('source_mtime_ns')==stat.st_mtime_ns:return cached.get('headers',{})
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
