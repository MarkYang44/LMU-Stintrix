"""Per-step report receipts; old error markers are evidence, not current status."""
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
from race_model import read_json
from storage import atomic_json
from collections import OrderedDict
from threading import RLock
import shutil
_cache=OrderedDict();_lock=RLock()
DEPENDENCIES=dict(endurance=('analysis',),review=('analysis','endurance','fastest'),compression=('analysis','endurance','fastest','review','images'))
OUTPUTS=dict(analysis=('session_analysis.json','analysis_index.json'),endurance=('endurance_analysis.json',),fastest=('fastest_lap_summary.json','fastest_lap.json','fastest_lap.html'),review=('review.html',),images=('race_images.json','race_log.json','race_log.txt','圈速单.png','比赛日志.png'))

def remember(folder,value):
    with _lock:
        key=str(Path(folder).resolve());_cache[key]=value;_cache.move_to_end(key)
        while len(_cache)>64:_cache.popitem(last=False)
    return value

def latest(folder):
    with _lock:return _cache.get(str(Path(folder).resolve()))

STEPS=('analysis','endurance','fastest','review','images','compression')
ERRORS=dict(analysis='analysis_error.txt',endurance='endurance_error.txt',fastest='fastest_lap_error.txt',images='race_images_error.txt',review='report_error.txt',compression='storage_compression_error.txt')
LABELS=dict(analysis='圈分析',endurance='耐力分析',fastest='最快圈',review='赛事复盘',images='比赛图片',compression='记录压缩')

def plan(folder):
    folder=Path(folder);old=read_json(folder/'report_status.json',{})
    if isinstance(old,dict) and old.get('version')==2 and isinstance(old.get('steps'),dict):
        return {k:dict(old['steps'][k]) if isinstance(old['steps'].get(k),dict) else dict(state='pending') for k in STEPS}
    # Adopt existing outputs without regenerating successful historical reports.
    artifacts=dict(analysis='session_analysis.json',endurance='endurance_analysis.json',fastest='fastest_lap_summary.json',review='review.html',images='比赛日志.png')
    historical=any((folder/name).is_file() for name in ('review.html','比赛日志.png'))
    steps={k:dict(state='error' if k in ERRORS and (folder/ERRORS[k]).is_file() else 'ready' if k=='compression' and historical or k in artifacts and (folder/artifacts[k]).is_file() else 'pending') for k in STEPS}
    if steps['images']['state']=='ready' and not (folder/'圈速单.png').is_file():steps['images']['state']='pending'
    return steps

def save(folder,steps,active=None,reason=None):
    states=[v.get('state','pending') for v in steps.values()]
    state='building' if active else 'deferred' if 'deferred' in states else 'ready' if all(v=='ready' for v in states) else 'partial' if 'ready' in states and 'error' in states else 'error' if 'error' in states else 'incomplete' if 'ready' in states else 'queued'
    value=dict(version=2,state=state,steps=steps,active=active,updated_utc=datetime.now(timezone.utc).isoformat())
    if reason:value['reason']=str(reason)
    atomic_json(Path(folder)/'report_status.json',value);return remember(folder,value)

def current(folder):
    value=read_json(Path(folder)/'report_status.json',{})
    if isinstance(value,dict) and value.get('version')==2:return remember(folder,value)
    steps=plan(folder);states=[v['state'] for v in steps.values()]
    state='deferred' if (Path(folder)/'report_pending.json').exists() else 'partial' if 'error' in states and 'ready' in states else 'error' if 'error' in states else 'ready' if all(v=='ready' for v in states) else 'incomplete' if 'ready' in states else 'queued'
    return remember(folder,dict(version=2,state=state,steps=steps))

def invalidate(steps):
    # Propagate failed or interrupted upstream work before deciding what to skip.
    for name in STEPS:
        if any(steps[d].get('state')!='ready' for d in DEPENDENCIES.get(name,())) and steps[name].get('state')=='ready':
            steps[name].update(state='pending',affected=True)

def begin_step(folder,name,steps):
    folder=Path(folder);marker=folder/ERRORS[name] if name in ERRORS else None
    old=steps.get(name,{})
    if old.get('state') in ('error','building','blocked') or old.get('affected') or old.get('attempts'):
        files=[folder/f for f in OUTPUTS.get(name,()) if (folder/f).is_file()]
        if files:
            backup=folder/'_report_history/retries'/uuid4().hex;backup.mkdir(parents=True)
            for path in files:shutil.copy2(path,backup/path.name)
    if marker and marker.is_file():
        target=folder/'_report_history/errors'/uuid4().hex;target.mkdir(parents=True)
        marker.replace(target/marker.name)
    steps[name]=dict(state='building',attempts=old.get('attempts',0)+1)
    save(folder,steps,active=name)

def deferred(folder,error):
    steps=plan(folder)
    for step in steps.values():
        if step.get('state')!='ready':step['state']='deferred'
    return save(folder,steps,reason=error)
