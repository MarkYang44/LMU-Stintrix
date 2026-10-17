"""Session-best PB chronology; no backfill or modification of source records."""
from datetime import datetime,timezone
from personal_records import entries
from lap_identity import text
from race_mode import mode


def dated(value):
    try:
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError):return None


def history(root,per_vehicle=False):
    ordered=[];missing=0
    for e in entries(root):
        when=dated(e['session'].get('started_utc'))
        if when is None:missing+=1;continue
        ordered.append((when,e))
    # Imported copies of one event are one observation. Conflicting copies are
    # excluded rather than giving a faster copy an invented position in time.
    unique={};conflicts=set()
    for when,e in ordered:
        key=(tuple(e['identity']),when,text(e['session'].get('vehicle')),text(e['session'].get('driver')))
        signature=(e['time_s'],e['lap']['number'])
        if key in conflicts:continue
        if key in unique and signature!=(unique[key][1]['time_s'],unique[key][1]['lap']['number']):
            conflicts.add(key);unique.pop(key);continue
        unique.setdefault(key,(when,e))
    # Same timestamp PBs have no observable internal order: retain one minimum.
    moments={}
    for when,e in unique.values():
        key=(tuple(e['identity']),text(e['session'].get('vehicle')) if per_vehicle else '',when)
        if key not in moments or e['time_s']<moments[key][1]['time_s']:moments[key]=(when,e)
    previous={};result=[]
    for when,e in sorted(moments.values(),key=lambda pair:(pair[0],pair[1]['time_s'])):
        key=tuple(e['identity'])+(mode(e),)+((text(e['session'].get('vehicle')),) if per_vehicle else ());old=previous.get(key)
        if old is not None and e['time_s']>=old['time_s']-.0005:continue
        item=e.copy();item.update(observed_utc=when.isoformat(),improvement_s=None if old is None else old['time_s']-e['time_s']);result.append(item)
        previous[key]=e
    return dict(entries=result,missing_dates=missing,conflicts=len(conflicts))
