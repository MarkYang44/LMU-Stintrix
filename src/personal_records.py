"""Metadata-only personal best index, separated by layout and vehicle class."""
import json,math
from telemetry_file import Path
from json_store import load
from lap_identity import text,vehicle_class,performance_variant

class CacheRecord(dict):
    __slots__=('__weakref__',)
    def copy(self):
        result=CacheRecord(self)
        from cache_budget import hold
        hold(result,Path(self['file']).parent)
        return result


def summary_for(root,folder,metadata=None):
    meta=load(folder/'session.json') if metadata is None else metadata
    if meta.get('simulator_id')=='ac_evo':
        from evo_laps import export,stamp
        path=folder/'fastest_lap_summary.json'
        try:
            value=json.loads(path.read_text(encoding='utf-8'))
            if value.get('signature')==stamp(folder):return value,folder
        except (OSError,ValueError,AttributeError):pass
        # Historical raw data stays untouched. Only derived EVO lap artifacts
        # are created; the streaming index is reused by images and reviews.
        return export(folder),folder
    path=folder/'fastest_lap_summary.json'
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(value,dict):return value,folder
    except (OSError,ValueError):pass
    # Missing reports must not hide a valid record. Derive only in a private cache.
    files=[folder/name for name in ('inputs.csv','session.json','vehicle.csv','native_channels.json')]
    signature=[(str(p),p.stat().st_size,p.stat().st_mtime_ns) for p in files if p.exists()]
    from cache_tokens import token
    key=token(root,'record-cache',signature)
    cache=root/'PersonalRecords'/'Cache'/key;cached=cache/'summary.json'
    try:
        value=json.loads(cached.read_text(encoding='utf-8'))
        if isinstance(value,dict):
            from cache_budget import touch
            touch(cache);return value,cache
    except (OSError,ValueError):pass
    from laps import extract_best,lap_record,write_json
    best,candidates,error=extract_best(folder/'inputs.csv')
    summary=dict(status='no_complete_lap')
    if best and best['validity']=='verified' and sum(v['number']==best['number'] for v in candidates)==1:
        record=lap_record(folder,best)
        cache.mkdir(parents=True,exist_ok=True);write_json(cache/'record.lap.json',record)
        summary=dict(status='saved',file='record.lap.json',session=record['session'],lap=record['lap'],conditions=record['conditions'])
    cache.mkdir(parents=True,exist_ok=True);write_json(cached,summary)
    from cache_budget import enforce
    enforce(root,keep=[cache]);return summary,cache


def entries(root):
    """All verified session bests, also used for chronological PB history."""
    root=Path(root).resolve();result=[]
    from race_mode import overlay,annotate,mode
    modes=overlay(root)
    from session_groups import superseded
    hidden=superseded(root)
    for category in ('Logs','ImportedLogs','RecoveredLogs'):
        for path in (root/category).glob('*/session.json'):
            try:
                if path.parent.resolve() in hidden:continue
                if not path.parent.resolve().is_relative_to(root):continue
                meta=json.loads(path.read_text(encoding='utf-8'))
                if isinstance(meta,dict):meta=annotate(meta,path.parent,modes)
                if not isinstance(meta,dict):continue
                from simulators import accepts
                if not accepts(root,meta):continue
                if meta.get('status') in ('recording','write_error'):continue
                if text(meta.get('source')).startswith('synthetic demo') or meta.get('demo') is True:continue
                summary,base=summary_for(root,path.parent,meta)
                if summary.get('status')!='saved':continue
                lap=summary['lap'];duration=float(lap['time_s']);length=float(lap['track_length_m'])
                if lap.get('validity')!='verified' or lap.get('lap_invalidated') or lap.get('in_pits'):continue
                if not math.isfinite(duration) or duration<=0 or not math.isfinite(length) or length<=100:continue
                file=(base/summary['file']).resolve()
                if not file.is_relative_to(root) or not file.is_file():continue
                session={**summary.get('session',{}),**meta};track=str(session.get('track') or '').strip()
                if not track:continue
                layout=str(session.get('track_layout') or '').strip()
                group=vehicle_class(session)
                # Include the recorded length even when names are identical.
                # EVO road cars do not share a performance class; keep model PBs separate.
                key=(text(track),text(layout or track),round(length),text(group))
                if session.get('simulator_id')=='ac_evo':key+=('ac_evo',text(session.get('vehicle')))
                elif performance_variant(session):key+=('variant',performance_variant(session),text(session.get('vehicle')))
                entry=dict(race_mode=mode(session),session=session,lap=lap,conditions=summary.get('conditions',{}),
                    track=track,layout=layout,vehicle_class=group,file=str(file),folder=str(path.parent),
                    time_s=duration,length_m=length)
                entry['identity']=key
                if base!=path.parent:
                    from cache_budget import hold
                    entry=CacheRecord(entry);hold(entry,base)
                result.append(entry)
            except (OSError,ValueError,KeyError,TypeError):continue
    return result


def records(root,race_mode=''):
    return select_records(entries(root),race_mode)

def select_records(values,race_mode=''):
    from race_mode import mode
    winners={}
    for entry in values:
        if race_mode and mode(entry)!=race_mode:continue
        key=entry['identity']
        if key not in winners or entry['time_s']<winners[key]['time_s']:winners[key]=entry
    return sorted(winners.values(),key=lambda v:(text(v['track']),text(v['layout']),text(v['vehicle_class'])))


def detail(entry,curve=True):
    value=load(entry['file'],**({} if curve else dict(fields=('conditions',))))
    if not curve:return dict(conditions=value.get('conditions',{}))
    try:
        # Fixed-size drawing envelope retains pedal spikes; source stays full resolution.
        buckets={};length=value['lap']['track_length_m']
        for row in value['data']:
            index=min(599,int(row[0]/length*599))
            low,high=buckets.setdefault(index,([row[2],row[3]],[row[2],row[3]]))
            for i in range(2):low[i]=min(low[i],row[2+i]);high[i]=max(high[i],row[2+i])
        return dict(conditions=value.get('conditions',{}),
            vehicle_summary=(value.get('vehicle_telemetry') or {}).get('summary',{}),
            curve=[(index,low,high) for index,(low,high) in sorted(buckets.items())])
    finally:
        close=getattr(value.get('data'),'close',None)
        if close:close()
