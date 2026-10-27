"""Frozen reference/zone targets with observed follow-up measurements only."""
import statistics
import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
from storage import atomic_json
from race_model import read_json
from lap_identity import text,same_layout,vehicle_class
from record_history import dated
from training_report import selected_profiles,profile_index,measure
from condition_match import matcher,settings
from analysis_scope import check as scope_check
from training_cache import catalogued

def create(root,report,zone):
    root=Path(root).resolve();reference=report['reference'];entry=report['entry']
    curve=next(selected_profiles(root,Path(reference['folder']),{reference['number']}))
    frozen=deepcopy({k:curve[k] for k in ('number','time_s','length_m','conditions','data','features') if k in curve})
    value=dict(version=1,id=uuid4().hex,created_utc=datetime.now(timezone.utc).isoformat(),status='active',entry={k:entry[k] for k in ('session','track','layout','length_m','vehicle_class')},policy=report.get('policy',settings()),zone={k:zone[k] for k in ('name','start','end','apex','source') if k in zone},reference=frozen,baseline=dict(median_loss_s=zone['median_loss_s'],std_s=zone['std_s'],count=zone['count']),unknown=report.get('unknown',[]),baseline_samples=report.get('samples',[]))
    folder=root/'PersonalRecords/TrainingGoals';folder.mkdir(parents=True,exist_ok=True);atomic_json(folder/(value['id']+'.json'),value);return value

def goals(root):
    values=[]
    for path in (Path(root)/'PersonalRecords/TrainingGoals').glob('*.json'):
        if path.is_symlink():continue
        from json_store import Reader
        try:
            with path.open(encoding='utf-8-sig') as stream:v=Reader(stream,fields=('version','id','created_utc','status','entry','zone','baseline')).value()
        except (OSError,ValueError):continue
        if v.get('version')==1 and v.get('status')=='active':values.append(v)
    return sorted(values,key=lambda v:v['created_utc'],reverse=True)

@catalogued
def evaluate(root,goal):
    from race_mode import overlay,annotate
    from session_groups import superseded
    root=Path(root).resolve()
    if 'reference' not in goal:
        base=(root/'PersonalRecords/TrainingGoals').resolve();path=(base/(goal['id']+'.json')).resolve()
        if path.parent!=base:raise ValueError('Invalid goal')
        goal=read_json(path,{})
    entry=goal['entry'];p=settings(goal['policy']);modes=overlay(root);hidden=superseded(root);after=dated(goal['created_utc']);reference=goal['reference'];target=measure(reference,goal['zone']);groups=[];errors=[];seen={};conflicts=set()
    accept=matcher(reference['conditions'],p)
    for category in ('Logs','ImportedLogs','RecoveredLogs'):
        for path in (root/category).glob('*/session.json'):
            folder=path.parent.resolve()
            if folder in hidden or not folder.is_relative_to(root):continue
            meta=annotate(read_json(path,{}),folder,modes);when=dated(meta.get('started_utc'))
            if when is None or after is None or when<=after or meta.get('status') in ('recording','write_error') or meta.get('demo') or text(meta.get('source'))=='synthetic demo':continue
            if any(text(meta.get(k))!=text(entry['session'].get(k)) for k in ('driver','vehicle','track','track_layout')):continue
            if vehicle_class(meta)!=entry['vehicle_class']:continue
            scope=scope_check(entry,meta,p)
            if not scope['allowed']:continue
            try:
                allowed={};unknown=set(scope['unknown'])
                for lap in profile_index(root,folder)['laps']:
                    if not same_layout(dict(session=entry['session'],lap=dict(track_length_m=entry['length_m'])),dict(session=meta,lap=dict(track_length_m=lap['length_m']))):continue
                    c=accept(lap['conditions'])
                    if c['allowed']:allowed[lap['number']]=lap;unknown.update(c['unknown'])
                values=[]
                for lap in selected_profiles(root,folder,set(allowed)):
                    identity=(when.isoformat(),text(meta.get('driver')),text(meta.get('vehicle')),scope['mode'],scope['phase'],lap['number'])
                    observed=measure(lap,goal['zone'])['time_s'];signature=(lap['time_s'],observed,json.dumps(lap['conditions'],sort_keys=True))
                    if identity in seen:
                        if seen[identity]!=signature:conflicts.add(identity)
                        continue
                    seen[identity]=signature;values.append((identity,observed))
                if values:groups.append(dict(meta=meta,when=when,values=values,scope=scope,unknown=sorted(unknown),folder=str(folder)))
            except (OSError,ValueError,KeyError,TypeError) as error:errors.append(folder.name+': '+str(error))
    sessions=[]
    for group in groups:
        times=[t for identity,t in group['values'] if identity not in conflicts]
        if not times:continue
        losses=[t-target['time_s'] for t in times];median=statistics.median(losses);qualified=len(times)>=p['min_laps'] and goal['baseline']['count']>=3 and not goal.get('unknown') and not group['unknown'] and not group['scope']['mixed']
        sessions.append(dict(observed_utc=group['when'].isoformat(),session=group['meta'],folder=group['folder'],time_s=statistics.median(times),median_loss_s=median,std_s=statistics.pstdev(losses) if len(losses)>1 else None,count=len(times),qualified=qualified,gain_s=goal['baseline']['median_loss_s']-median if qualified else None,unknown=group['unknown']))
    sessions.sort(key=lambda e:e['observed_utc'])
    return dict(goal=goal,sessions=sessions,errors=errors,conflicts=len(conflicts))

def close(root,goal):
    path=(Path(root)/'PersonalRecords/TrainingGoals'/(goal['id']+'.json')).resolve();base=(Path(root)/'PersonalRecords/TrainingGoals').resolve()
    if path.parent!=base:raise ValueError('Invalid goal')
    value=read_json(path,{})
    if value.get('id')!=goal['id']:raise ValueError('Goal changed')
    value.update(status='closed',closed_utc=datetime.now(timezone.utc).isoformat());atomic_json(path,value)
