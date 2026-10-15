"""Small, incremental event facets. Never opens raw CSV or rewrites race evidence."""
import json, math, threading
from pathlib import Path
from storage import atomic_json
from lap_identity import canonical_class, vehicle_class
from race_model import read_json

VERSION=3
FILES=('session.json','fastest_lap_summary.json','race_summary.json','session_analysis.json')
_lock=threading.RLock()

def number(value):
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) else None

def rank(value):
    value=number(value)
    return int(value) if value is not None and value==int(value) and 1<=value<=104 else None

def condition_number(key,value):
    value=number(value);low,high={'fuel_l':(0,2000),'track_temp_c':(-100,150),'tc_level':(0,255),'abs_level':(0,255)}[key]
    return value if value is not None and low<=value<=high and (key not in ('tc_level','abs_level') or value==int(value)) else None

def analysis(path):
    from analysis_headers import load
    try:return load(path.parent)
    except (OSError,ValueError,TypeError):return {}


def weather(conditions):
    wet=number(conditions.get('wetness'));rain=number(conditions.get('rain'))
    if wet is None or rain is None or not 0<=wet<=1 or not 0<=rain<=1:return 'unknown'
    return 'dry' if wet<=.01 and rain==0 else 'wet'

def result(summary,official=False,conflict=False):
    if conflict:return 'unknown','conflict'
    if official:
        status=str(summary.get('finish_status','')).casefold()
        outcome='dq' if 'disqual' in status or status in ('dq','3') else 'dnf' if 'dnf' in status or 'retir' in status or status=='2' else 'finished' if summary.get('finished') is True else 'unknown'
        # Official status strings vary: an unrecognized non-finish is unknown.
        return outcome,'official'
    flag=summary.get('finish_flag')
    if isinstance(flag,bool):flag=None
    if flag in (1,2,3) and summary.get('available') is not False:return {1:'finished',2:'dnf',3:'dq'}[flag],'telemetry'
    return 'unknown','observed' if rank(summary.get('finish_place')) or rank(summary.get('finish_class_place')) else 'unknown'

def build(folder):
    meta=read_json(folder/'session.json',{});best=read_json(folder/'fastest_lap_summary.json',{});s=read_json(folder/'race_summary.json',{})
    meta=meta if isinstance(meta,dict) else {};best=best if isinstance(best,dict) else {};s=s if isinstance(s,dict) else {}
    a=analysis(folder/'session_analysis.json');lap=best.get('lap') or {};lap=lap if isinstance(lap,dict) else {};candidates=best.get('candidates')
    valid=sum(v.get('eligible') is True and v.get('validity')=='verified' for v in candidates if isinstance(v,dict)) if isinstance(candidates,list) else None
    conditions=[v.get('conditions') if isinstance(v.get('conditions'),dict) else {} for v in a.get('laps',[]) if isinstance(v,dict) and v.get('validity')=='verified']
    scope='valid_laps'
    if not conditions and isinstance(best.get('conditions'),dict) and best['conditions']:
        conditions=[best['conditions']];scope='fastest_lap'
    kinds={weather(v) for v in conditions};road='mixed' if {'dry','wet'}<=kinds else next(iter(kinds)) if len(kinds)==1 else 'unknown'
    # One known wet lap plus unknown laps does not prove the whole session wet.
    if 'unknown' in kinds and road!='mixed':road='unknown'
    outcome,trust=result(s)
    stability=a.get('recent_stability');stability=stability if isinstance(stability,dict) else {}
    started=number(s.get('race_started_et'));ended=number(s.get('race_finished_et'))
    race_s=ended-started if started is not None and ended is not None and ended>=started else None
    gaps=number(meta.get('telemetry_gap_count'));gap_known='telemetry_gap_count' in meta or isinstance(meta.get('telemetry_gaps'),list)
    if gaps is None and isinstance(meta.get('telemetry_gaps'),list):gaps=len(meta['telemetry_gaps'])
    has_valid=valid is not None and valid>0 or best.get('status')=='saved' and lap.get('validity')=='verified'
    quality='write_error' if meta.get('status')=='write_error' else 'recording' if meta.get('status')=='recording' else 'gaps' if gaps is not None and gaps>0 else 'valid' if has_valid else 'partial' if valid==0 else 'unknown'
    from library import session_label
    value=dict(track=meta.get('track',''),layout=meta.get('track_layout',''),length_m=lap.get('track_length_m') or meta.get('track_length'),vehicle=meta.get('vehicle',''),vehicle_class=canonical_class(s.get('vehicle_class')) or vehicle_class(meta),team=s.get('team') or meta.get('team',''),phase=session_label(meta.get('session')),date=meta.get('started_utc',''),outcome=outcome,trust=trust,grid=rank(s.get('grid_place')),grid_class=rank(s.get('grid_class_place')),finish=rank(s.get('finish_place')) if outcome=='finished' else None,finish_class=rank(s.get('finish_class_place')) if outcome=='finished' else None,observed_place=rank(s.get('finish_place')),stable_file=a.get('stable_reference_file'),quality=quality,has_valid_lap=bool(has_valid),gap_count=gaps if gap_known else None,valid_laps=valid,race_s=race_s,recorded_s=number(meta.get('duration_s')),time_s=number(lap.get('time_s')),stability_s=None,weather=road,condition_scope=scope,source=folder.parent.name,has_telemetry=(folder/'inputs.csv').is_file(),has_review=(folder/'review.html').is_file(),has_timing=(folder/'圈速单.png').is_file(),has_journal=(folder/'比赛日志.png').is_file())
    for key in ('fuel_l','track_temp_c','tc_level','abs_level'):
        values=[condition_number(key,v.get(key)) for v in conditions if condition_number(key,v.get(key)) is not None]
        known=bool(values) and len(values)==len(conditions)
        value[key+'_min']=min(values) if known else None;value[key+'_max']=max(values) if known else None
    for axle,index in (('front','tyre_compound'),('rear','tyre_rear_compound')):
        value[axle+'_tyres']=sorted({str(v['tyre_'+axle+'_name']).strip() for v in conditions if v.get('tyre_'+axle+'_name')})
        value[axle+'_indices']=sorted({int(v[index]) for v in conditions if number(v.get(index)) is not None and 0<=v[index]<=255 and v[index]==int(v[index])})
    value['gain']=value['grid']-value['finish'] if value['grid'] and value['finish'] else None
    value['class_gain']=value['grid_class']-value['finish_class'] if value['grid_class'] and value['finish_class'] else None
    value['stability_s']=number(stability.get('std')) if (number(stability.get('count')) or 0)>=3 else None
    return value

def snapshot(root):
    root=Path(root).resolve()
    from session_groups import superseded
    hidden=superseded(root)
    with _lock:
        path=root/'EventCatalog/index.json';old=read_json(path,{})
        previous=old.get('entries',{}) if isinstance(old,dict) and old.get('version')==VERSION else {};previous=previous if isinstance(previous,dict) else {};current={}
        for category in ('Logs','ImportedLogs','RecoveredLogs','DemoLogs'):
            for p in (root/category).glob('*/session.json'):
                folder=p.parent.resolve()
                if folder in hidden or not folder.is_relative_to(root):continue
                key=str(folder.relative_to(root));signature=[]
                for name in (*FILES,'inputs.csv','review.html','圈速单.png','比赛日志.png'):
                    try:s=(folder/name).stat();signature.append([name,s.st_size,s.st_mtime_ns])
                    except OSError:pass
                cached=previous.get(key,{})
                if isinstance(cached,dict) and cached.get('signature')==signature and isinstance(cached.get('facets'),dict):current[key]=cached
                else:
                    try:facets=build(folder)
                    except (OSError,ValueError,TypeError,AttributeError):facets=dict(quality='unknown',trust='unknown',source=category)
                    current[key]=dict(signature=signature,facets=facets)
        official_path=root/'OfficialResults/index.json'
        try:s=official_path.stat();official_signature=[s.st_size,s.st_mtime_ns]
        except OSError:official_signature=None
        links=old.get('official_links',{}) if isinstance(old,dict) and old.get('official_signature')==official_signature else None
        if links is None:
            links={}
            from json_store import Reader
            class OfficialHeaders(Reader):
                def value(self,key='',depth=0,keep=True):return super().value(key,depth,keep and key!='laps')
            try:
                with official_path.open(encoding='utf-8-sig') as stream:official=OfficialHeaders(stream,fields=('entries',)).value()
                for e in official.get('entries',[]):
                    linked=e.get('linked_folder')
                    if not linked:continue
                    if e.get('link_status')=='matched':
                        links[linked]={k:e.get(k) for k in ('finish_status','finished','grid_place','grid_class_place','finish_place','finish_class_place')}
                    elif e.get('link_status') in ('conflict','ambiguous'):links[linked]={'conflict':True}
            except (OSError,ValueError,TypeError):pass
        value=dict(version=VERSION,entries=current,official_signature=official_signature,official_links=links)
        if value!=old:
            path.parent.mkdir(parents=True,exist_ok=True);atomic_json(path,value)
    out={str((root/key).resolve()):dict(v['facets']) for key,v in current.items()}
    for folder,s in links.items():
        if folder not in out:continue
        f=out[folder];outcome,trust=result(s,True,bool(s.get('conflict')))
        f.update(outcome=outcome,trust=trust,grid=rank(s.get('grid_place')),grid_class=rank(s.get('grid_class_place')),finish=rank(s.get('finish_place')) if outcome=='finished' else None,finish_class=rank(s.get('finish_class_place')) if outcome=='finished' else None)
        if trust=='conflict':f['quality']='conflict'
        f['gain']=f['grid']-f['finish'] if f['grid'] and f['finish'] else None;f['class_gain']=f['grid_class']-f['finish_class'] if f['grid_class'] and f['finish_class'] else None
    return out

def normalize(entry):
    """Adapt inventory/PB/history/podium/XML without changing their identities."""
    f=dict(weather='unknown',trust='unknown',quality='unknown',source='',has_telemetry=False,has_review=False,has_timing=False,has_journal=False)
    f.update(entry.get('_facets') or {});meta=entry.get('session');meta=meta if isinstance(meta,dict) else entry
    official=entry.get('official_result') or (entry if 'source_xml' in entry else None)
    from race_mode import mode
    f.update(track=entry.get('track',meta.get('track',f.get('track',''))),vehicle=meta.get('vehicle',entry.get('vehicle',f.get('vehicle',''))),date=entry.get('observed_utc') or entry.get('started_utc') or entry.get('date') or meta.get('started_utc') or f.get('date',''),mode=mode(entry))
    f['layout']=entry.get('layout',entry.get('track_layout',meta.get('track_layout',f.get('layout',''))));f['length_m']=entry.get('length_m',entry.get('track_length_m',f.get('length_m')))
    f['vehicle_class']=canonical_class(entry.get('vehicle_class') or f.get('vehicle_class') or meta.get('vehicle_class'))
    f['phase']=entry.get('phase',entry.get('session_type',f.get('phase','')))
    f['time_s']=number(entry.get('time_s',entry.get('fastest_s',entry.get('best_lap_s',f.get('time_s')))))
    if official:
        conflict=official.get('link_status') in ('conflict','ambiguous');outcome,trust=result(official,True,conflict)
        linked=official.get('link_status')=='matched' and f.get('has_telemetry') is True
        f.update(outcome=outcome,trust=trust,team=official.get('team',''),vehicle_class=canonical_class(official.get('vehicle_class','')),phase=official.get('phase',''),source='official',has_telemetry=linked,quality='conflict' if conflict else f.get('quality') if linked else 'xml_only',race_s=f.get('race_s') if linked else None,recorded_s=f.get('recorded_s'),grid=rank(official.get('grid_place')),grid_class=rank(official.get('grid_class_place')),finish=rank(official.get('finish_place')) if outcome=='finished' else None,finish_class=rank(official.get('finish_class_place')) if outcome=='finished' else None)
        f['gain']=f['grid']-f['finish'] if f['grid'] and f['finish'] else None;f['class_gain']=f['grid_class']-f['finish_class'] if f['grid_class'] and f['finish_class'] else None
    c=entry.get('conditions')
    if isinstance(c,dict) and not entry.get('xml_only'):
        f.update(weather=weather(c),condition_scope='fastest_lap')
        for key in ('fuel_l','track_temp_c','tc_level','abs_level'):f[key+'_min']=f[key+'_max']=condition_number(key,c.get(key))
        for axle,index in (('front','tyre_compound'),('rear','tyre_rear_compound')):
            f[axle+'_tyres']=[str(c['tyre_'+axle+'_name'])] if c.get('tyre_'+axle+'_name') else []
            v=number(c.get(index));f[axle+'_indices']=[int(v)] if v is not None and 0<=v<=255 and v==int(v) else []
    for key in ('source','stability_s','note','traffic','favorite','tags'):
        if key in entry:f[key]=entry[key]
    if entry.get('xml_only'):f['source']='official';f['has_telemetry']=False
    return f

def attach(root,entries):
    cache=snapshot(root);out=[]
    notes=read_json(Path(root)/'library_notes.json',{})
    for e in entries:
        folder=Path(e.get('folder') or e.get('linked_folder') or (Path(root)/'OfficialResults/events'/e['id'] if e.get('id') else '')).resolve();f=cache.get(str(folder),{})
        item=dict(e,_facets=f)
        if 'source_xml' in e:item['folder']=str(folder)
        try:
            relative=folder.relative_to(Path(root).resolve());note=notes.get(str(relative),notes.get(relative.as_posix(),{}))
        except ValueError:note={}
        item.update(favorite=bool(note.get('favorite')),tags=note.get('tags',[]),traffic=bool(note.get('traffic')),note=str(note.get('text','')))
        out.append(item)
    return out
