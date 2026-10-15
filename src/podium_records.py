"""Verified class podiums and bounded race-time charts; historical data is read-only."""
import csv,json,math
from pathlib import Path
from library import session_label
from lap_identity import canonical_class,text
from race_model import read_json,build_model

CATEGORIES=('Logs','ImportedLogs','RecoveredLogs')

def rank(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and 1<=value<=104 else None

def numeric(value):
    if isinstance(value,bool):return None
    try:value=float(value)
    except (ValueError,TypeError):return None
    return value if math.isfinite(value) else None

def events(folder):
    path=folder/'race_events.csv'
    if not path.is_file() or not path.resolve().is_relative_to(folder):return
    with path.open(encoding='utf-8-sig',newline='') as stream:
        for row in csv.DictReader(stream):
            payload=json.loads(row.get('payload_json','{}'))
            if isinstance(payload,dict):yield dict(time=numeric(row.get('session_time_s')),event=row.get('event'),data=payload)

def result_summary(folder):
    summary=read_json(folder/'race_summary.json',{})
    if not isinstance(summary,dict):summary={}
    if summary and not summary.get('recovered'):return summary
    # Recovery is accepted only if an explicit journal end confirms a finish.
    restored=dict(summary)
    for e in events(folder):
        p=e['data']
        if e['event']=='recording_start':restored.update(start_class_place=p.get('class_place'),start_class_size=p.get('class_size'),vehicle_class=p.get('vehicle_class',''))
        if e['event']=='recording_end':restored.update(finish_flag=p.get('finish_flag'),finish_class_place=p.get('class_place'),class_size=p.get('class_size'),vehicle_class=p.get('vehicle_class',''),class_position_available=rank(p.get('class_place')) is not None)
    return restored

def index(root):
    root=Path(root).resolve();winners={};conflicts=set();missing=0
    from race_mode import overlay,annotate,mode
    modes=overlay(root)
    from session_groups import superseded
    hidden=superseded(root)
    for category in CATEGORIES:
        for path in (root/category).glob('*/session.json'):
            folder=path.parent.resolve()
            if folder in hidden:continue
            if not folder.is_relative_to(root):continue
            try:
                meta=read_json(path,{})
                if isinstance(meta,dict):meta=annotate(meta,folder,modes)
                if not isinstance(meta,dict) or session_label(meta.get('session'))!='Race':continue
                if meta.get('demo') is True or text(meta.get('source'))=='synthetic demo':continue
                if meta.get('status') not in ('complete','completed','finished','imported','recovered'):continue
                s=result_summary(folder);place=rank(s.get('finish_class_place'))
                group=canonical_class(s.get('vehicle_class') or meta.get('vehicle_class'))
                if s.get('finish_flag')!=1 or isinstance(s.get('finish_flag'),bool):continue
                if place is None or not group or s.get('class_position_available') is False:
                    missing+=1;continue
                size=rank(s.get('class_size'))
                if size is not None and place>size:continue
                key=(meta.get('started_utc') or str(folder),text(meta.get('track')),text(meta.get('track_layout')),text(meta.get('vehicle')),text(meta.get('driver')),group)
                if key in conflicts:continue
                if key in winners:
                    if winners[key]['place']!=place:conflicts.add(key);winners.pop(key)
                    continue
                fastest=read_json(folder/'fastest_lap_summary.json',{})
                if not isinstance(fastest,dict):fastest={}
                lap=fastest.get('lap',{})
                if not isinstance(lap,dict):lap={}
                best=numeric(lap.get('time_s')) if fastest.get('status')=='saved' and lap.get('validity')=='verified' else None
                winners[key]=dict(race_mode=mode(meta),folder=str(folder),session=meta,summary=s,place=place,vehicle_class=group,
                    track=meta.get('track',''),layout=meta.get('track_layout') or meta.get('track',''),
                    length_m=numeric(meta.get('track_length')) or numeric(lap.get('track_length_m')),fastest_s=best,
                    started_utc=meta.get('started_utc',''),team=s.get('team') or meta.get('team',''))
            except (OSError,ValueError,TypeError,AttributeError):continue
    from official_results import podium_entries,load as official_load
    blocked={r.get('linked_folder') for r in official_load(root)['entries'] if r.get('link_status')=='conflict'}
    entries=[v for v in winners.values() if v['place'] in (1,2,3) and v['folder'] not in blocked]
    for official in podium_entries(root):
        copies=set(official['official_result'].get('match_candidates',[]))
        entries=[e for e in entries if e['folder'] not in copies]
        entries.append(official)
    conflicts.update(('official',p) for p in blocked if p)
    entries.sort(key=lambda e:e['started_utc'],reverse=True);entries.sort(key=lambda e:e['place'])
    return dict(entries=entries,counts={p:sum(e['place']==p for e in entries) for p in (1,2,3)},missing_class_results=missing,conflicts=len(conflicts))

ALIASES={'tyre_front_index':'tyre_compound','tyre_rear_index':'tyre_rear_compound','rain_severity':'rain'}
CONDITIONS=('fuel_l','tyre_compound','tyre_rear_compound','track_temp_c','ambient_temp_c','wetness','rain','track_grip','tc_level','abs_level','battery_soc_pct','virtual_energy_pct')
STRINGS=('tyre_front_name','tyre_rear_name')

def samples(path):
    if not path.is_file():return
    with path.open(encoding='utf-8-sig',newline='') as stream:
        yield from csv.DictReader(stream)

def detail(entry):
    if entry.get('xml_only'):
        from official_results import xml_detail
        return xml_detail(entry)
    folder=Path(entry['folder']).resolve();start={};end={};first=None;last=None;wear_start={};wear_end={}
    for filename in ('inputs.csv','vehicle.csv'):
        path=folder/filename
        if not path.resolve().is_relative_to(folder):raise ValueError('Invalid race data path')
        for row in samples(path):
            if filename=='inputs.csv':
                et=numeric(row.get('session_time_s'))
                if et is not None:first=et if first is None else min(first,et);last=et if last is None else max(last,et)
            for key in CONDITIONS:
                source=next((alias for alias,target in ALIASES.items() if target==key and row.get(alias) not in ('',None)),key)
                value=numeric(row.get(source))
                if value is not None:start.setdefault(key,value);end[key]=value
            for key in STRINGS:
                if row.get(key):start.setdefault(key,row[key]);end[key]=row[key]
            for wheel in ('fl','fr','rl','rr'):
                v=numeric(row.get(wheel+'_wear_fraction'))
                if v is not None and 0<=v<=1:wear_start.setdefault(wheel,v);wear_end[wheel]=v
    if len(wear_start)==4:start['remaining']=min(wear_start.values())*100
    if len(wear_end)==4:end['remaining']=min(wear_end.values())*100
    recorded_s=last-first if first is not None and last is not None else numeric(entry['session'].get('duration_s'))
    model=None;pace=[];best=entry.get('fastest_s');count=None;green=None;finish=None
    if (folder/'inputs.csv').is_file():
        model=build_model(folder)
        if model['fastest']:best=model['fastest']['time']
        completed=[lap for lap in model['laps'] if lap.get('complete') and numeric(lap.get('time')) is not None and lap['time']>0]
        count=len(completed)
        for lap in completed:
            t=(numeric(lap.get('start')) or 0)+lap['time']-(first if first is not None else model['origin'])
            pace.append(dict(time_s=t,lap=lap['num'],lap_s=lap['time'],eligible=bool(lap['best'] or lap['valid'] is True and not lap['partial'] and not lap['in_pits']),best=lap['best']))
        for e in model['events']:
            if green is None and e['event']=='phase' and e['data'].get('to')==5:green=e['time']
            if e['event']=='recording_end' and e['data'].get('finish_flag')==1:finish=e['time']
    s=entry['summary'];green=numeric(s.get('race_started_et')) if numeric(s.get('race_started_et')) is not None else green
    finish=numeric(s.get('race_finished_et')) if numeric(s.get('race_finished_et')) is not None else finish
    race_s=finish-green if green is not None and finish is not None and finish>=green else None
    buckets={}
    if first is not None and recorded_s is not None and recorded_s>0:
        for row in samples(folder/'inputs.csv'):
            et=numeric(row.get('session_time_s'));values=[numeric(row.get(k)) for k in ('throttle','brake')]
            if et is None or any(v is None or not 0<=v<=1 for v in values):continue
            i=max(0,min(599,int((et-first)/recorded_s*599)));lo,hi=buckets.setdefault(i,(values.copy(),values.copy()))
            for k in range(2):lo[k]=min(lo[k],values[k]);hi[k]=max(hi[k],values[k])
    return dict(start=start,end=end,recorded_s=recorded_s,race_s=race_s,fastest_s=best,completed_laps=count,
        pace=pace,inputs=[(i,lo,hi) for i,(lo,hi) in sorted(buckets.items())],partial=bool(s.get('recording_started_mid_session')))
