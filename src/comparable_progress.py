"""Observed session medians and consistency, strictly filtered around one anchor lap."""
import json,statistics
from pathlib import Path
from lap_identity import text,same_layout,vehicle_class
from record_history import dated
from training_report import profile_index as profiles
from condition_match import matcher,settings
from training_cache import catalogued

@catalogued
def analyse(root,entry,policy=None):
    root=Path(root).resolve();p=settings(policy);anchor=dict(session=entry['session'],lap=entry['lap']);sessions=[];pool={};conflicts=set();counts=dict(invalid=0,different=0,unknown=0,duplicates=0,conflicts=0);errors=[]
    accept=matcher(entry.get('conditions',{}),p)
    from analysis_scope import check as scope_check
    from race_mode import overlay,annotate
    modes=overlay(root)
    from session_groups import superseded
    hidden=superseded(root)
    for category in ('Logs','ImportedLogs','RecoveredLogs'):
        for metadata in (root/category).glob('*/session.json'):
            folder=metadata.parent.resolve()
            if not folder.is_relative_to(root) or folder in hidden:continue
            try:
                meta=annotate(json.loads(metadata.read_text(encoding='utf-8-sig')),folder,modes);scope=scope_check(entry,meta,p)
                if not scope['allowed']:continue
                when=dated(meta.get('started_utc'))
                if not when or meta.get('status') in ('recording','write_error') or meta.get('demo') or text(meta.get('source'))=='synthetic demo':continue
                if text(meta.get('driver'))!=text(entry['session'].get('driver')):continue
                if text(meta.get('track'))!=text(entry['track']) or text(meta.get('track_layout'))!=text(entry['layout']) or text(meta.get('vehicle'))!=text(entry['session'].get('vehicle')) or vehicle_class(meta)!=entry['vehicle_class']:continue
                value=profiles(root,folder);counts['invalid']+=value['excluded']
                for lap in value['laps']:
                    if not same_layout(anchor,dict(session=meta,lap=dict(track_length_m=lap['length_m']))):continue
                    key=(when.isoformat(),text(meta.get('driver')),text(meta.get('vehicle')),scope['mode'],scope['phase'],lap['number'])
                    signature=(lap['time_s'],json.dumps(lap['conditions'],sort_keys=True))
                    if key in pool:
                        counts['duplicates']+=1
                        if pool[key]['signature']!=signature:conflicts.add(key)
                    else:pool[key]=dict(lap={k:v for k,v in lap.items() if k not in ('data','features')},meta=meta,when=when,folder=str(folder),signature=signature,scope=scope)
            except (OSError,ValueError,KeyError,TypeError) as e:errors.append(metadata.parent.name+': '+str(e))
    counts['conflicts']=len(conflicts);groups={}
    for key,row in pool.items():
        if key in conflicts:continue
        lap=row['lap'];c=accept(lap['conditions'])
        if not c['allowed']:counts['different' if c['different'] else 'unknown']+=1;continue
        group=groups.setdefault(key[:-1],dict(row,accepted=[],unknown=set()));group['accepted'].append(lap);group['unknown'].update(c['unknown'])
    for group in groups.values():
        accepted=group['accepted'];times=[l['time_s'] for l in accepted];fuel=[l['conditions']['fuel_l'] for l in accepted if isinstance(l['conditions'].get('fuel_l'),(int,float))];uncertain=group['unknown']
        qualified=len(times)>=p['min_laps'] and not uncertain and not group['scope']['mixed'] and not group['scope']['unknown']
        sessions.append(dict(entry,session=group['meta'],folder=group['folder'],observed_utc=group['when'].isoformat(),time_s=statistics.median(times),median_s=statistics.median(times),best_s=min(times),std_s=statistics.pstdev(times) if len(times)>1 else None,count=len(times),qualified=qualified,unknown=sorted(uncertain|set(group['scope']['unknown'])|({'跨类别探索'} if group['scope']['mixed'] else set())),fuel_range_l=[min(fuel),max(fuel)] if fuel else None))
    sessions.sort(key=lambda s:s['observed_utc']);reliable=[s for s in sessions if s['qualified']];summary=None
    if len(reliable)>=2:
        a,b=reliable[0],reliable[-1];summary=dict(pace_gain_s=a['median_s']-b['median_s'],consistency_gain_s=a['std_s']-b['std_s'],from_utc=a['observed_utc'],to_utc=b['observed_utc'],sessions=len(reliable))
    return dict(entry=entry,policy=p,sessions=sessions,summary=summary,excluded=counts,errors=errors,anchor_conditions=entry.get('conditions',{}))
