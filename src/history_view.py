"""Pure history classification and graph series; layouts never share a line."""
from lap_identity import text
from record_history import dated
from race_mode import mode,pairs

SORTS=('最新优先','最早优先','按赛道分类','按车辆分类','线下优先','线上优先')


def filtered(entries,track='',car='',layout_key=None,sort=0,query='',race_mode=''):
    from track_names import search_text,layout
    rows=[];term=query.strip().casefold()
    for i,e in enumerate(entries):
        if race_mode and mode(e)!=race_mode:continue
        if track and text(e['track'])!=text(track):continue
        if car and text(e['session'].get('vehicle'))!=text(car):continue
        if layout_key is not None and tuple(e['identity'])!=tuple(layout_key):continue
        if term and term not in ' '.join((search_text(e['track']),layout(e['track'],e['layout'],e['length_m']),e['vehicle_class'],e['session'].get('vehicle',''))).casefold():continue
        rows.append((i,e))
    rows.sort(key=lambda pair:dated(pair[1]['observed_utc']),reverse=sort!=1)
    if sort==2:rows.sort(key=lambda pair:(text(pair[1]['track']),tuple(pair[1]['identity']),text(pair[1]['session'].get('vehicle'))))
    elif sort==3:rows.sort(key=lambda pair:(text(pair[1]['session'].get('vehicle')),tuple(pair[1]['identity'])))
    if sort in (4,5):
        wanted='single' if sort==4 else 'online';rows.sort(key=lambda p:0 if mode(p[1])==wanted else 2 if mode(p[1])=='unknown' else 1)
    return rows


def series(entries,selected):
    if not selected:return []
    identity=tuple(selected['identity']);car=text(selected['session'].get('vehicle'))
    values=[e for e in entries if tuple(e['identity'])==identity and text(e['session'].get('vehicle'))==car and mode(e)==mode(selected)]
    return sorted(values,key=lambda e:dated(e['observed_utc']))
