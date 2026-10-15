"""Read-only game result import with provenance; no invented telemetry or ranks."""
import hashlib,json,math,re
from pathlib import Path
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
from lap_identity import text,canonical_class
from record_history import dated
from race_model import read_json
from storage import atomic_json
from track_names import display
from library import session_label

MAX_XML=32*1024*1024

def number(value):
    try:n=float(value)
    except (ValueError,TypeError):return None
    return n if math.isfinite(n) else None

def rank(value):
    n=number(value)
    return int(n) if n is not None and n.is_integer() and 1<=n<=104 else None

def positive(value):
    n=number(value);return n if n is not None and n>0 else None

def fingerprint(record):
    return (record['phase'],record['started_utc'],text(record['track']),text(record['layout']),text(record['vehicle']),text(record['driver']))

def parse(path,player_names=None):
    path=Path(path).resolve()
    if path.stat().st_size>MAX_XML:raise ValueError('XML exceeds 32 MiB')
    stat=path.stat()
    # Validate the fixed game prolog, then stream the XML. No checksums and no
    # complete-file byte copies; non-player lap subtrees are released immediately.
    with path.open('rb') as stream:
        header=stream.read(2048);prolog=header.split(b'<rFactorXML',1)[0]
        safe=re.sub(rb'<!DOCTYPE\s+rF\s+\[\s*<!ENTITY\s+rFEnt\s+"rFactor Entity">\s*\]>',b'',prolog)
        if b'<!DOCTYPE' in safe.upper() or b'<!ENTITY' in safe.upper():raise ValueError('XML entity declarations are not accepted')
        stream.seek(0);stack=[];classes={};kept={};iterator=ET.iterparse(stream,events=('start','end'))
        names={text(n) for n in (player_names or ()) if text(n)}
        for event,node in iterator:
            if event=='start':stack.append(node);continue
            if node.tag=='Driver' and len(stack)>=2:
                parent=stack[-2];counter=classes.setdefault(id(parent),{})
                group=canonical_class(node.findtext('CarClass'));counter[group]=counter.get(group,0)+1
                wanted=text(node.findtext('Name')) in names if names else text(node.findtext('isPlayer')) in ('1','true')
                if wanted and kept.get(id(parent),0)<2:kept[id(parent)]=kept.get(id(parent),0)+1
                else:node.clear()
            stack.pop()
        root=iterator.root
    if root.tag!='rFactorXML':raise ValueError('Not an LMU result XML')
    results=root.find('RaceResults')
    if results is None:results=root
    out=[]
    for phase in ('Race','Qualify','Practice','Warmup'):
        for session in (n for n in results if re.fullmatch(phase+r'(?:[1-9][0-9]*)?',n.tag)):
            stamp=number(session.findtext('DateTime'))
            if stamp is None or not 946684800<=stamp<=4133980800:raise ValueError('Result date missing or invalid')
            when=datetime.fromtimestamp(stamp,timezone.utc).isoformat()
            drivers=session.findall('Driver')
            names={text(n) for n in (player_names or ()) if text(n)}
            players=[d for d in drivers if text(d.findtext('Name')) in names] if names else [d for d in drivers if text(d.findtext('isPlayer')) in ('1','true')]
            if len(players)!=1:raise ValueError('Result must identify exactly one player')
            d=players[0]
            field=lambda name:str(d.findtext(name) or '').strip()
            track=results.findtext('TrackVenue') or results.findtext('TrackCourse') or ''
            course=results.findtext('TrackCourse') or track
            length=positive(results.findtext('TrackLength'))
            # The result format reports TrackLength in metres; never assume km.
            if length is not None and not 100<=length<=100000:length=None
            status=field('FinishStatus');finished=status.casefold() in ('finished normally','finished','1')
            place=rank(field('ClassPosition'));total_place=rank(field('Position'));group=canonical_class(field('CarClass'))
            drivers=session.findall('Driver');class_size=classes.get(id(session),{}).get(group) if group else None
            if class_size and place and place>class_size:place=None
            laps=[]
            for lap in d.findall('Lap'):
                duration=positive(lap.text);num=rank(lap.get('num')) or (int(lap.get('num')) if str(lap.get('num','')).isdigit() else None)
                if duration is None or num is None:continue
                laps.append(dict(number=num,time_s=duration,end_s=positive(lap.get('et')),sectors=[positive(lap.get(k)) for k in ('s1','s2','s3')],front_tyre=lap.get('fcompound'),rear_tyre=lap.get('rcompound')))
            from race_mode import xml_mode
            rec=dict(race_mode=xml_mode(results.findtext('Setting')),race_mode_source='LMU XML Setting',phase=phase,started_utc=when,track=track,layout=course,length_m=length,driver=field('Name'),vehicle=field('CarType') or field('VehName'),team=field('TeamName'),vehicle_class=group,
                grid_place=rank(field('GridPos')),grid_class_place=rank(field('ClassGridPos')),finish_place=total_place,finish_class_place=place,class_size=class_size,
                finish_status=status,finished=finished,best_lap_s=positive(field('BestLapTime')),finish_time_s=positive(field('FinishTime')),completed_laps=number(field('Laps')),pit_stops=number(field('Pitstops')),laps=laps,
                source_xml=str(path),source_size=stat.st_size,source_mtime_ns=stat.st_mtime_ns,source='LMU result XML')
            if not rec['track'] or not rec['vehicle'] or not rec['driver']:raise ValueError('Missing track, vehicle or driver')
            rec['id']=hashlib.sha256(repr(fingerprint(rec)).encode()).hexdigest()[:24];out.append(rec)
    if not out:raise ValueError('No supported session in result XML')
    return out

def local_sessions(root):
    root=Path(root).resolve();values=[]
    from session_groups import superseded
    hidden=superseded(root)
    for category in ('Logs','ImportedLogs','RecoveredLogs'):
        for p in (root/category).glob('*/session.json'):
            if p.parent.resolve() in hidden:continue
            if not p.parent.resolve().is_relative_to(root):continue
            m=read_json(p,{})
            if not isinstance(m,dict) or m.get('demo') or m.get('status') in ('recording','write_error'):continue
            if text(m.get('source'))=='synthetic demo':continue
            when=dated(m.get('started_utc'))
            if when:values.append((p.parent.resolve(),m,when))
    return values

def link(record,sessions):
    matches=[];when=dated(record['started_utc'])
    for folder,m,dt in sessions:
        if session_label(m.get('session'))!=record['phase'] or text(m.get('driver'))!=text(record['driver']) or text(m.get('vehicle'))!=text(record['vehicle']):continue
        if display(m.get('track'),'zh')!=display(record['track'],'zh'):continue
        # Full layout names must agree. A base circuit alias cannot prove a layout.
        if text(m.get('track_layout'))!=text(record['layout']):continue
        ml=positive(m.get('track_length'))
        if ml and record['length_m'] and abs(ml-record['length_m'])>1:continue
        delta=abs((dt-when).total_seconds())
        if delta<=180:matches.append((delta,str(folder),m))
    if not matches:return dict(link_status='unmatched',linked_folder=None,match_candidates=[])
    matches.sort(key=lambda p:p[0]);best=matches[0]
    same=[x for x in matches if abs(x[0]-best[0])<1]
    # Imported byte-identical event copies are allowed; distinct starts are ambiguous.
    starts={x[2].get('started_utc') for x in same}
    if len(starts)>1:return dict(link_status='ambiguous',linked_folder=None,match_candidates=[x[1] for x in matches])
    summary=read_json(Path(best[1])/'race_summary.json',{})
    conflicts={k:dict(telemetry=summary.get(k),official=record[v]) for k,v in (('finish_place','finish_place'),('finish_class_place','finish_class_place'),('grid_place','grid_place'),('grid_class_place','grid_class_place')) if rank(summary.get(k)) and record[v] and summary[k]!=record[v]}
    return dict(link_status='conflict' if conflicts else 'matched',linked_folder=best[1],match_candidates=[x[1] for x in matches],position_conflicts=conflicts)

def load(root):
    value=read_json(Path(root)/'OfficialResults/index.json',{})
    return value if isinstance(value,dict) and value.get('version')==1 else dict(version=1,entries=[],errors=[],conflicts=[],scanned_files=0)

def refresh(root,source,player_name=None):
    root=Path(root).resolve();source=Path(source).resolve()
    if not source.is_dir():raise ValueError('Results directory does not exist')
    (root/'OfficialResults').mkdir(parents=True,exist_ok=True)
    sessions=local_sessions(root);previous=load(root)
    saved=read_json(root/'OfficialResults/preferences.json',{})
    chosen=player_name or saved.get('player_name')
    names={chosen} if chosen else {m.get('driver') for _,m,_ in sessions if m.get('driver')}
    errors=[];records=[];scanned=0;reused=0;successful_sources=set()
    cached={}
    if previous.get('parser_version')==3 and previous.get('player_names')==sorted(names):
        for entry in previous['entries']:cached.setdefault(entry.get('source_xml'),[]).append(entry)
    for path in sorted(source.glob('*.xml')):
        if not path.resolve().is_relative_to(source):errors.append(dict(file=path.name,error='External link rejected'));continue
        scanned+=1
        try:
            resolved=str(path.resolve());stamp=path.stat();old=cached.get(resolved,[])
            if old and all(e.get('source_size')==stamp.st_size and e.get('source_mtime_ns')==stamp.st_mtime_ns for e in old):
                records.extend(old);reused+=1
            else:records.extend(parse(path,names))
            successful_sources.add(resolved)
        except (OSError,ValueError,ET.ParseError) as e:errors.append(dict(file=path.name,error=str(e)))
    # Keep previous read-only imports when users move or archive game files.
    records.extend(e for e in previous['entries'] if e.get('source_xml') not in successful_sources or names and text(e.get('driver')) not in {text(n) for n in names})
    unique={};conflicts=set()
    fact=lambda e:tuple(json.dumps(e.get(k),sort_keys=True) for k in ('finish_place','finish_class_place','finish_status','best_lap_s','grid_place','grid_class_place','completed_laps','laps'))
    for e in records:
        key=e['id']
        if key in unique and fact(unique[key])!=fact(e):conflicts.add(key)
        else:unique.setdefault(key,e)
    entries=[]
    for key,e in unique.items():
        if key in conflicts:continue
        e=dict(e,**link(e,sessions));e.pop('source_hash',None);entries.append(e)
        folder=root/'OfficialResults/events'/key;folder.mkdir(parents=True,exist_ok=True)
        if read_json(folder/'result.json',{})!=e:atomic_json(folder/'result.json',e)
    entries.sort(key=lambda e:e['started_utc'],reverse=True)
    value=dict(version=1,parser_version=3,reused_files=reused,entries=entries,errors=errors,conflicts=sorted(conflicts),scanned_files=scanned,source_directory=str(source),player_names=sorted(names),updated_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(root/'OfficialResults/index.json',value)
    from race_mode import build as mode_build
    mode_build(root,entries,sessions,source)
    if player_name:atomic_json(root/'OfficialResults/preferences.json',dict(player_name=player_name))
    return value

def podium_entries(root):
    root=Path(root).resolve();out=[]
    for r in load(root)['entries']:
        if r['phase']!='Race' or not r['finished'] or r['finish_class_place'] not in (1,2,3) or not r['vehicle_class'] or r.get('link_status') in ('conflict','ambiguous'):continue
        linked=r.get('linked_folder');folder=Path(linked) if linked else root/'OfficialResults/events'/r['id']
        if linked and not folder.resolve().is_relative_to(root):continue
        meta=read_json(folder/'session.json',{}) if linked else {}
        meta=dict(meta,race_mode=r.get('race_mode','unknown'),race_mode_source='LMU XML Setting',track=r['track'],track_layout=r['layout'],vehicle=r['vehicle'],driver=r['driver'],started_utc=r['started_utc'],session=10,source='LMU result XML')
        summary=dict(grid_place=r['grid_place'],grid_class_place=r['grid_class_place'],finish_place=r['finish_place'],finish_class_place=r['finish_class_place'],finish_flag=1,class_size=r['class_size'],class_position_available=True,vehicle_class=r['vehicle_class'])
        out.append(dict(folder=str(folder),session=meta,summary=summary,place=r['finish_class_place'],vehicle_class=r['vehicle_class'],track=r['track'],layout=r['layout'],length_m=r['length_m'],fastest_s=r['best_lap_s'],started_utc=r['started_utc'],team=r['team'],official_result=r,xml_only=not linked))
    return out

def xml_detail(entry):
    r=entry['official_result'];pace=[]
    for l in r['laps']:
        if l.get('end_s') is not None:pace.append(dict(time_s=l['end_s'],lap=l['number'],lap_s=l['time_s'],eligible=False,best=bool(r['best_lap_s'] and abs(l['time_s']-r['best_lap_s'])<.001)))
    return dict(start={},end={},recorded_s=None,race_s=None,fastest_s=r['best_lap_s'],completed_laps=r['completed_laps'],pace=pace,inputs=[],partial=False,xml_only=True)
