"""Explicit participation modes; unknowns are never inferred from field size."""
import csv,json,math
from telemetry_file import Path
from datetime import datetime,timezone,timedelta
from race_model import read_json
from storage import atomic_json
from lap_identity import text
from track_names import display
def dated(value):
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'));return (d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d).astimezone(timezone.utc)
    except (ValueError,TypeError):return None
LABELS={'single':'线下','online':'线上','unknown':'未知'}

def mode(value):
    meta=value.get('session');meta=meta if isinstance(meta,dict) else value;v=value.get('race_mode',meta.get('race_mode'))
    if v=='offline' and meta.get('simulator_id')=='ac_evo':return 'single'
    return v if v in LABELS else 'unknown'

def xml_mode(setting):
    return {'multiplayer':'online','race weekend':'single','singleplayer':'single'}.get(text(setting),'unknown')

def overlay(root):
    value=read_json(Path(root)/'RaceModes/index.json',{})
    if not isinstance(value,dict):value={}
    source=value.get('source_directory')
    try:
        if source and Path(source).is_dir() and Path(source).stat().st_mtime_ns!=value.get('source_mtime_ns'):
            from official_results import refresh
            refresh(root,source)
            value=read_json(Path(root)/'RaceModes/index.json',{})
    except (OSError,ValueError):pass
    from race_mode_overrides import apply
    return apply(root,value.get('entries',{}))

def annotate(meta,folder,modes):
    return apply_annotation(meta,modes.get(str(Path(folder).resolve()),{}))


def apply_annotation(meta,extra):
    """One pure decision rule; callers may already own a canonical source key."""
    value=dict(meta)
    if extra.get('race_mode_manual') is True and extra.get('race_mode') in ('online','single'):
        value.update(extra);return value
    known=mode(meta);other=extra.get('race_mode','unknown')
    if known=='unknown' and other in LABELS:value.update(extra)
    elif other!='unknown' and known!=other:value.update(race_mode='unknown',race_mode_source='Conflicting evidence')
    return value

def build(root,results,sessions,source=None):
    """Link explicit result Setting to session epoch, not just nearby dates."""
    root=Path(root).resolve();out={};by={}
    for r in results:
        if r.get('race_mode','unknown')=='unknown':continue
        key=(r['phase'],text(r['driver']),text(r['vehicle']),display(r['track'],'zh'),text(r['layout']))
        by.setdefault(key,[]).append(r)
    from library import session_label
    for folder,m,when in sessions:
        key=(session_label(m.get('session')),text(m.get('driver')),text(m.get('vehicle')),display(m.get('track'),'zh'),text(m.get('track_layout')))
        try:
            with (folder/'inputs.csv').open(encoding='utf-8-sig',newline='') as stream:row=next(csv.DictReader(stream),{})
            et=float(row.get('session_time_s','nan'))
            if not math.isfinite(et) or et<0:continue
        except (OSError,ValueError):continue
        epoch=when-timedelta(seconds=et)
        matched=[r for r in by.get(key,[]) if abs((dated(r['started_utc'])-epoch).total_seconds())<=3]
        kinds={r['race_mode'] for r in matched}
        if len(kinds)==1:out[str(folder)]=dict(race_mode=next(iter(kinds)),race_mode_source='LMU XML Setting',race_mode_xml=matched[0]['source_xml'])
    (root/'RaceModes').mkdir(parents=True,exist_ok=True);atomic_json(root/'RaceModes/index.json',dict(version=1,entries=out,source_directory=str(source) if source else None,source_mtime_ns=Path(source).stat().st_mtime_ns if source and Path(source).is_dir() else None));return out

def pairs(entries,kind='',order=0):
    values=[(i,e) for i,e in enumerate(entries) if not kind or mode(e)==kind]
    def date(e):return e.get('observed_utc',e.get('started_utc',e.get('date',e.get('session',{}).get('started_utc','')))) or ''
    if order in (1,2):values.sort(key=lambda p:date(p[1]),reverse=order==1)
    elif order in (3,4):
        values.sort(key=lambda p:date(p[1]),reverse=True)
        wanted='single' if order==3 else 'online';values.sort(key=lambda p:0 if mode(p[1])==wanted else 2 if mode(p[1])=='unknown' else 1)
    return values
