"""Offline fastest-lap export. Never runs on the telemetry polling thread."""
import bisect
import csv
import html
import json
from json_store import load as load_json
import math
from telemetry_file import Path
import statistics
import threading
from buffers import CompactRow
from array import array
from analysis_spool import LapRows,DiskTable,median

FORMAT = 'inputscope.fastest-lap'
DATA_COLUMNS = ['distance_m','lap_time_s','throttle','brake','filtered_throttle','filtered_brake','speed_kmh']


def safe_name(value):
    return ''.join('_' if c in '<>:"/\\|?*' or ord(c)<32 else c for c in str(value)).strip(' .')[:40] or 'Unknown'


def write_json(path, value):
    from reporting import json_chunks
    path = Path(path)
    pending = path.with_name(path.name+'.'+str(threading.get_ident())+'.pending')
    try:
        with pending.open('wb') as f:
            for chunk in json_chunks(value):f.write(chunk)
        pending.replace(path)
    finally:
        if pending.exists():pending.unlink()


def read_rows(path,start=0,end=None,cookies=(),capture=None):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        numbers = {'time_s','session_time_s','lap','lap_distance_m','throttle','brake',
                   'steering','filtered_throttle','filtered_brake','filtered_steering','speed_kmh',
                   'lap_start_s','lap_invalidated','in_pits','track_length_m',
                   'world_x_m','world_y_m','world_z_m','fuel_l','tyre_compound','track_temp_c',
                   'wetness','tc_level','abs_level','tc_active','abs_active','gear',
                   'tyre_rear_compound','ambient_temp_c','rain','track_grip'}
        layout={k:i for i,k in enumerate(dict.fromkeys(k for k in reader.fieldnames or () if k in numbers))}
        last_utc=None
        from lap_scan_index import raw_rows
        for row in raw_rows(path,start,end,cookies,capture):
            try:
                numeric=[]
                for key in layout:
                    value=row.get(key)
                    if value in ('',None):numeric.append(math.nan)
                    else:
                        number=float(value)
                        if not math.isfinite(number):raise ValueError('Non-finite telemetry')
                        numeric.append(number)
                utc=row['utc']
                if utc!=last_utc:last_utc=utc
                values=CompactRow(layout,numeric,last_utc)
                if not {'session_time_s','lap','lap_distance_m','throttle','brake',
                        'filtered_throttle','filtered_brake','speed_kmh'}.issubset(values):
                    raise ValueError('Required telemetry columns missing')
                yield values
            except (ValueError,TypeError,KeyError) as error:
                raise ValueError('CSV contains an incomplete or invalid telemetry row') from error


def lap_key(row):
    start = row.get('lap_start_s')
    if start is not None and 0<=start<=row['session_time_s']+.1:
        return ('timer',start)
    return ('counter',int(row['lap']))


def _distances(path):
    """The length pass needs two exact fields, not every numeric channel."""
    from pathlib import Path as NativePath
    path=NativePath(path)
    if not path.is_file():
        from column_store import rows
        pairs=((r['lap_distance_m'],r['track_length_m']) for r in rows(path,('lap_distance_m','track_length_m')))
        yield from _distance_values(pairs);return
    with path.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.reader(stream);positions={key:i for i,key in enumerate(next(reader,[]))}
        def field(row,key):
            i=positions.get(key);return row[i] if i is not None and i<len(row) else ''
        yield from _distance_values((field(row,'lap_distance_m'),field(row,'track_length_m')) for row in reader if row)


def _distance_values(pairs):
    for distance,length in pairs:
        try:
            distance=float(distance);length=float(length) if length else 0.
            if not math.isfinite(distance) or not math.isfinite(length):raise ValueError('Non-finite telemetry')
        except (ValueError,TypeError) as error:raise ValueError('CSV contains an incomplete or invalid telemetry row') from error
        yield distance,length


def extract_best(csv_path,on_candidate=None,include_flagged=False,retain_best=True,_index=None):
    """Require two observed boundaries, or an exact recorded first-lap start.

    Legacy CSVs use successive lap-counter transitions and never promote the
    first or last partial group. Scoring distance can lag the telemetry timer;
    discard the previous lap's leading tail and interpolate its staircase.
    """
    inferred_length = 0
    known_lengths = []
    for distance,length in _distances(csv_path):
        inferred_length = max(inferred_length,distance)
        if length>100 and len(known_lengths)<1000:
            known_lengths.append(length)
        if len(known_lengths)>=1000:break
    length = statistics.median(known_lengths) if known_lengths else inferred_length
    if length<=100:
        return None,[], 'No usable track distance'
    best = None
    candidates = []
    group = LapRows(Path(csv_path).parent)
    key = None
    seen_boundary = False
    first_row=0

    def complete(next_row):
        nonlocal best
        timer = key[0]=='timer' and lap_key(next_row)[0]=='timer'
        start = key[1] if timer else group[0]['session_time_s']
        end = lap_key(next_row)[1] if timer else next_row['session_time_s']
        duration = end-start
        number = int(group[0]['lap'])
        reason = None
        positive=array('d');nonmonotonic=False;checked=True;invalidated=False;in_pits=False
        beginning=None;maximum=-math.inf;backwards=False;previous_time=None;previous_distance=None
        # These facts used to reread the disk-backed lap in several full passes.
        # Collect the same facts once; keep all source samples and float64 times.
        for index,row in enumerate(group):
            when=row['session_time_s'];distance=row['lap_distance_m']
            if previous_time is not None:
                dt=when-previous_time
                if dt>0:positive.append(dt)
                else:nonmonotonic=True
            previous_time=when
            checked=checked and 'lap_invalidated' in row and 'in_pits' in row
            invalidated=invalidated or row.get('lap_invalidated',0)>0
            in_pits=in_pits or row.get('in_pits',0)>0
            if beginning is None and -20<=distance<=min(80,length*.05):beginning=index
            if beginning is not None:
                maximum=max(maximum,distance)
                if previous_distance is not None and distance<previous_distance-20:backwards=True
                previous_distance=distance
        largest=max(positive,default=0)
        cadence = median(positive) if positive else 0
        threshold = min(2.5,max(1.5,cadence*3))
        tolerance = max(.05,min(1.5,cadence*1.5))
        if duration<=0 or end>next_row['session_time_s']+.1:
            reason = 'timing reset'
        elif not seen_boundary and (not timer or abs(group[0]['session_time_s']-start)>tolerance):
            reason = 'start of lap missing'
        elif len(group)<3 or not positive or nonmonotonic:
            reason = 'insufficient or nonmonotonic samples'
        elif max(largest,next_row['session_time_s']-group[-1]['session_time_s'])>threshold:
            reason = 'telemetry gap'
        elif not include_flagged and invalidated:
            reason = 'invalidated lap'
        elif not include_flagged and in_pits:
            reason = 'pit lane lap'
        # Initial high distances may belong to the preceding lap's stale scoring
        # update. Only a genuine near-zero section followed by near-full distance
        # constitutes a recorded complete circuit.
        if reason is None and (beginning is None or maximum<length*.95):
            reason = 'incomplete distance coverage'
        if reason is None and backwards:
            reason = 'distance moved backwards or reset'
        info = dict(number=number,time_s=round(duration,6),track_length_m=length,eligible=reason is None,
                    exclusion=reason,validity='verified' if checked else 'unverified_legacy',
                    lap_invalidated=invalidated,in_pits=in_pits)
        candidates.append(info)
        indexed_reason=reason
        if _index is not None:
            if reason in ('invalidated lap','pit lane lap'):
                indexed_reason=('incomplete distance coverage' if beginning is None or maximum<length*.95 else
                                'distance moved backwards or reset' if backwards else None)
            indexed_info={**info,'eligible':indexed_reason is None,'exclusion':indexed_reason}
            _index['candidates'].append(indexed_info)
        if reason is None or _index is not None and indexed_reason is None:
            value = dict(**info,start_s=start,end_s=end,rows=group,
                        next_row=dict(next_row),length_m=length,
                        timing_source='game_lap_start' if timer else 'lap_counter_estimate',
                        distance_source='game_track_length' if known_lengths else 'recorded_maximum_estimate',
                        first_distance_index=beginning,cadence_s=cadence)
            if _index is not None:_index['groups'].append({k:(dict(v) if k=='next_row' else v) for k,v in value.items() if k!='rows'}|indexed_info|{'_range':[first_row,ordinal]})
            if reason is None:
                if on_candidate:on_candidate(value)
                if retain_best and (best is None or duration<best['time_s']):best=value

    previous_time=None
    from lap_scan_index import STEP
    for ordinal,row in enumerate(read_rows(csv_path,capture=_index['cookies'] if _index is not None else None)):
        if _index is not None and ordinal%STEP==0:_index['clocks'].append([ordinal,row['session_time_s']])
        if _index is not None and previous_time is not None and row['session_time_s']<previous_time:_index['monotonic']=False
        previous_time=row['session_time_s']
        next_key = lap_key(row)
        if group and next_key!=key:
            group.seal()
            complete(row)
            group = LapRows(Path(csv_path).parent)
            seen_boundary = True
            first_row=ordinal
        key = next_key
        group.append(row)
    if group:
        candidates.append(dict(number=int(group[0]['lap']),eligible=False,exclusion='end of lap missing'))
        if _index is not None:_index['candidates'].append(dict(candidates[-1]))
    return best,candidates,None


def comparison_data(best):
    rows = best['rows']
    start,end,length = best['start_s'],best['end_s'],best['length_m']
    times=array('d',[start]);distances=array('d',[0])
    for r in rows[best['first_distance_index']:]:
        t,d=r['session_time_s'],max(0,min(length,r['lap_distance_m']))
        if start<t<end and d>distances[-1]+.01:times.append(t);distances.append(d)
    times.append(end);distances.append(length)
    names=('throttle','brake','filtered_throttle','filtered_brake','speed_kmh')
    def boundary(t,a,b,d):
        f=max(0,min(1,(t-a['session_time_s'])/max(1e-9,b['session_time_s']-a['session_time_s'])))
        return [round(d,3),round(t-start,6),*[round(a[n]+f*(b[n]-a[n]),6) for n in names]]
    def records():
        yield boundary(start,rows[0],rows[min(1,len(rows)-1)],0)
        index=0
        for row in rows:
            t=row['session_time_s']
            if not start<t<end:continue
            index=min(max(index,bisect.bisect_right(times,t)-1),len(times)-2)
            d=distances[index]+(distances[index+1]-distances[index])*(t-times[index])/(times[index+1]-times[index])
            yield [round(d,3),round(t-start,6),*[round(row[n],6) for n in names]]
        yield boundary(end,rows[-1],best['next_row'],length)
    return DiskTable(records(),7,rows.directory if isinstance(rows,LapRows) else None)



def curve_svg(lap):
    meta,info,data = lap['session'],lap['lap'],lap['data']
    title = f"{meta['track']} · {meta['vehicle']} · 第 {info['number']} 圈 · {info['time_s']:.3f} s"
    output = ['<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="620" viewBox="0 0 1600 620">',
              '<rect width="1600" height="620" fill="#0c111a"/>',
              '<g font-family="Arial,Microsoft YaHei,sans-serif" fill="#dce6f7">',
              '<text x="65" y="44" font-size="25">'+html.escape(title)+'</text>',
              '<text x="65" y="73" font-size="15">'+html.escape(f"{meta.get('driver','')} · {meta.get('started_utc','')} · "+('已记录有效性' if info['validity']=='verified' else '旧日志：有效性未验证')+' · 原始输入 / 距离对齐')+'</text>']
    for column,name,color,top in ((2,'THROTTLE / 油门','#34e59a',125),(3,'BRAKE / 刹车','#ff596b',365)):
        output.append(f'<text x="65" y="{top-15}" font-size="18" fill="{color}">{name}</text>')
        for percent in (0,50,100):
            y = top+170*(1-percent/100)
            output.append(f'<path d="M65 {y}H1545" stroke="#27354b"/><text x="18" y="{y+5}" font-size="13">{percent}%</text>')
        # Per-pixel extrema retain braking spikes in the exported full-lap image.
        buckets = {}
        for row in data:
            x = 65+round(row[0]/info['track_length_m']*1480)
            low,high = buckets.get(x,(row[column],row[column]))
            buckets[x] = min(low,row[column]),max(high,row[column])
        path = []
        for x,(low,high) in sorted(buckets.items()):
            path.extend((f'{x},{top+170*(1-low):.2f}',f'{x},{top+170*(1-high):.2f}'))
        output.append(f'<polyline points="{" ".join(path)}" fill="none" stroke="{color}" stroke-width="1.8"/>')
        for i in range(6):
            x = 65+i*1480/5
            output.append(f'<text x="{x-10}" y="{top+196}" font-size="13">{info["track_length_m"]*i/5:.0f} m</text>')
    output.append('</g></svg>')
    return ''.join(output)


def trajectory_data(best, data):
    """A bounded 50 Hz map track; full XYZ samples remain in the source CSV."""
    start,end = best['start_s'],best['end_s']
    times = [r[1] for r in data]
    points = []
    def add(t,x,z,force=False):
        t = max(0,min(end-start,t))
        if points and (t<=points[-1][0] or not force and t-points[-1][0]<.02-1e-8):
            return
        index = min(len(data)-1,bisect.bisect_left(times,t))
        a,b = data[max(0,index-1)],data[index]
        f = max(0,min(1,(t-a[1])/max(1e-9,b[1]-a[1])))
        d = a[0]+f*(b[0]-a[0])
        points.append([round(t,6),round(d,3),round(x,3),round(z,3)])
    rows = best['rows']
    for row in rows:
        if all(k in row for k in ('world_x_m','world_z_m')) and start<=row['session_time_s']<end:
            add(row['session_time_s']-start,row['world_x_m'],row['world_z_m'])
    a,b = rows[-1],best['next_row']
    if all(k in row for row in (a,b) for k in ('world_x_m','world_z_m')) and 0<b['session_time_s']-a['session_time_s']<=1.5:
        f = max(0,min(1,(end-a['session_time_s'])/(b['session_time_s']-a['session_time_s'])))
        add(end-start,a['world_x_m']+f*(b['world_x_m']-a['world_x_m']),
            a['world_z_m']+f*(b['world_z_m']-a['world_z_m']),True)
    if len(points)<3 or max(max(p[k] for p in points)-min(p[k] for p in points) for k in (2,3))<10:
        return None
    return dict(columns=['lap_time_s','distance_m','world_x_m','world_z_m'],points=points,
                source='recorded_world_xz',max_gap_s=1.5,sample_target_hz=50)


def write_compare(path, template, laps=(), status=None,reference_id=None,view_state=None,local=False):
    import reporting
    value = dict(laps=list(laps),status=status)
    if reference_id is not None:value['reference_id']=reference_id
    if view_state:
        for key,item in view_state.items():
            if key not in ('laps','status','reference_id'):value[key]=item
    template = Path(template)
    from control_theme import web_script
    source = template.read_text(encoding='utf-8').replace('/*INTERFACE_THEME_JS*/',web_script(template.parent)).replace('/*LAP_DATA*/null','await StintrixData.jsonBlock("stintrix-laps")')
    source = source.replace('/*DATA_VIEW_JS*/',reporting.script(template.parent))
    if '/*TRACK_VIEW_JS*/' in source:
        source = source.replace('/*TRACK_VIEW_JS*/',track_script(template.parent))
    if '/*VEHICLE_VIEW_JS*/' in source:
        from vehiclelab import script
        source=source.replace('/*VEHICLE_VIEW_JS*/',script(template.parent))
    if local:
        from report_assets import prepare
        source=prepare(path,source,template.parent,Path(path).parent.parent.parent)
    reporting.write_page(path,source,[('stintrix-laps',reporting.json_chunks(value))])


def track_script(folder):
    folder = Path(folder)
    from paths import track_catalog_path
    catalog = track_catalog_path(folder).read_text(encoding='utf-8-sig').replace('<','\\u003c')
    return (folder/'laplab.js').read_text(encoding='utf-8')+'\n'+(folder/'trackview.js').read_text(encoding='utf-8').replace('/*TRACK_CATALOG*/null',catalog)


def library_laps(root, current=None):
    """Only embed two compatible sessions. Further laps can be imported locally."""
    summaries = []
    root=Path(root)
    roots=[root]
    if root.name in ('Logs','ImportedLogs','RecoveredLogs'):
        roots=[root.parent/n for n in ('Logs','ImportedLogs','RecoveredLogs')]
    from session_groups import superseded
    hidden=superseded(root.parent) if root.name in ('Logs','ImportedLogs','RecoveredLogs','DemoLogs') else set()
    for path in (p for folder in roots for p in folder.glob('*/fastest_lap_summary.json')):
        try:
            if path.parent.resolve() in hidden:continue
            value = json.loads(path.read_text(encoding='utf-8'))
            if value.get('status')=='saved':
                summaries.append((path.parent/value['file'],value))
        except (OSError,ValueError):
            continue
    if current is None and summaries:
        newest = max(summaries,key=lambda pair:pair[1]['session'].get('started_utc',''))[0]
        current = load_json(newest)
    if current is None:
        return []
    compatible = [(path,v) for path,v in summaries if path.parent.name+':'+str(v['lap']['number'])!=current['id']
                  and all(v['session'].get(k)==current['session'].get(k) for k in ('track','vehicle'))]
    previous = load_json(min(compatible,key=lambda pair:pair[1]['lap']['time_s'])[0]) if compatible else None
    return [current,previous] if previous else [current]


def finished_metadata(folder):
    folder = Path(folder)
    metadata = json.loads((folder/'session.json').read_text(encoding='utf-8'))
    if metadata.get('status')=='recording':
        raise ValueError('Wait until this session has finished recording')
    if metadata.get('status')=='write_error':
        raise ValueError('Recording has a writer error; no reliable reference can be exported')
    return metadata


def lap_record(folder,best,metadata=None,native=None,kind='fastest',vehicle_bundle=...):
    """Common full-resolution payload for fastest and explicitly selected laps."""
    folder=Path(folder)
    if metadata is None:metadata=finished_metadata(folder)
    from processing_context import current
    shared=current(folder);reused=shared.values if shared is not None and shared.values.get('best') is best else {}
    info = {k:best[k] for k in ('number','time_s','validity','timing_source','distance_source','cadence_s')}
    info.update(track_length_m=round(best['length_m'],3),start_session_time_s=best['start_s'],
                end_session_time_s=best['end_s'],sample_count=sum(best['start_s']<=r['session_time_s']<best['end_s'] for r in best['rows']),
                boundary_interpolation=True,lap_number_source='LMU mLapNumber / inputs.csv',
                lap_invalidated=bool(best.get('lap_invalidated')),in_pits=bool(best.get('in_pits')))
    result = dict(format=FORMAT,version=1,id=folder.name+':'+str(info['number']),
                  session={k:metadata.get(k,'') for k in ('track','vehicle','driver','started_utc',
                           'ended_utc','session','source','end_reason','track_layout','vehicle_class')},lap=info,
                  data_columns=DATA_COLUMNS,data=reused['best_curve'] if 'best_curve' in reused else comparison_data(best),reference_kind=kind)
    result['trajectory'] = trajectory_data(best,result['data'])
    from sessionlab import lap_conditions,actions
    if native is None and (folder/'native_channels.json').exists():native=load_json(folder/'native_channels.json')
    result['conditions']=dict(reused['best_conditions']) if 'best_conditions' in reused else lap_conditions(best['rows'],native,best['start_s'],native.get('event_offset_s',0) if native else 0)
    # Text channels stay in CSV, outside the float64 scratch matrix.
    with (folder/'inputs.csv').open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if 'tyre_front_name' in (reader.fieldnames or ()):
            from lap_scan_index import raw_rows
            span=best.get('_text_range');text_rows=raw_rows(folder/'inputs.csv',*span[:2],cookies=span[2]) if span else reader
            for row in text_rows:
                if best['start_s']<=float(row['session_time_s'])<best['end_s']:
                    result['conditions'].update({k:row[k] for k in ('tyre_front_name','tyre_rear_name') if row.get(k)})
                    break
    result['actions']=reused['best_actions'] if 'best_actions' in reused else actions(best['rows'])
    from vehiclelab import lap_telemetry,load_recording
    result['vehicle_telemetry']=lap_telemetry(best,load_recording(folder) if vehicle_bundle is ... else vehicle_bundle)
    if result['trajectory'] and metadata.get('position_source'):result['trajectory']['source'] = metadata['position_source']
    if native:
        result['native_context'] = dict(metadata=metadata.get('native_metadata',{}),source=metadata.get('native_source',{}),channels={})
        for channel,series in native['channels'].items():
            offset = native.get('event_offset_s',0) if series['event'] else 0
            from analysis_spool import Column,DiskTable
            rows = series['data'];times = Column(rows,offset=offset)
            first = max(0,bisect.bisect_right(times,best['start_s'])-1)
            last = bisect.bisect_right(times,best['end_s'])
            result['native_context']['channels'][channel] = dict(unit=series['unit'],event=series['event'],
                frequency_hz=series['frequency_hz'],data=DiskTable(([round(r[0]-offset-best['start_s'],6),*r[1:]] for r in rows[first:last]),len(rows[0]),folder) if rows else [])
    return result


def _write_lap_csv(path,best,metadata,source=None):
    if source is not None:
        with Path(source).open(encoding='utf-8-sig',newline='') as stream,Path(path).open('w',encoding='utf-8',newline='') as output:
            reader=csv.DictReader(stream);basic={k:metadata.get(k,'') for k in ('track','vehicle','driver','started_utc')}
            writer=csv.DictWriter(output,fieldnames=list(dict.fromkeys([*basic,'lap_time_s',*(reader.fieldnames or ())])))
            writer.writeheader()
            from lap_scan_index import raw_rows
            span=best.get('_range');rows=raw_rows(source,*span[:2],cookies=span[2]) if span else reader
            for row in rows:
                when=float(row['session_time_s'])
                if best['start_s']<=when<best['end_s'] and int(float(row['lap']))==best['number']:
                    writer.writerow({**row,**basic,'lap_time_s':round(when-best['start_s'],6)})
        return
    with Path(path).open('w',encoding='utf-8',newline='') as stream:
        fields=list(dict.fromkeys(k for r in best['rows'] for k in r))
        basic={k:metadata.get(k,'') for k in ('track','vehicle','driver','started_utc')}
        writer=csv.DictWriter(stream,fieldnames=[*basic,'lap_time_s',*fields]);writer.writeheader()
        for row in best['rows']:
            if best['start_s']<=row['session_time_s']<best['end_s']:
                writer.writerow(dict(**basic,lap_time_s=round(row['session_time_s']-best['start_s'],6),**row))


def write_lap_csv(path,best,metadata,source=None):
    path=Path(path);pending=path.with_name(path.name+'.'+str(threading.get_ident())+'.pending')
    try:_write_lap_csv(pending,best,metadata,source);pending.replace(path)
    finally:pending.unlink(missing_ok=True)


def complete_laps(folder):
    """Only structurally complete laps; racing validity flags remain explicit."""
    folder=Path(folder);finished_metadata(folder)
    from comparison_cache import scan
    return scan(folder,lambda:_complete_laps(folder))


def _complete_laps(folder):
    from lap_scan_index import load,builder,save
    indexed=load(folder)
    if indexed is not None:return indexed['inventory']
    index=builder(folder)
    _,candidates,error=extract_best(folder/'inputs.csv',include_flagged=True,retain_best=False,_index=index)
    result=_lap_inventory(candidates,error);save(folder,result,index);return result


def _lap_inventory(candidates,error):
    counts={}
    for v in candidates:counts[v['number']]=counts.get(v['number'],0)+1
    for v in candidates:
        if v['eligible'] and counts[v['number']]>1:v.update(eligible=False,exclusion='ambiguous repeated lap number')
    return dict(laps=[v for v in candidates if v['eligible']],candidates=candidates,error=error)


def export_selected_laps(folder,numbers,template=None):
    """Extract one or two specified complete laps; never rewrites original exports."""
    if (not isinstance(numbers,(list,tuple)) or not 1<=len(numbers)<=2 or
            any(isinstance(n,bool) or not isinstance(n,int) or n<0 for n in numbers)):
        raise ValueError('请选择一个或两个非负整数圈号')
    if len(set(numbers))!=len(numbers):raise ValueError('圈 A 和圈 B 必须选择不同圈')
    folder=Path(folder);finished_metadata(folder)
    from lap_exports import cached
    existing=cached(folder,numbers,template)
    if existing:return existing
    metadata,selected=_select_laps(folder,numbers)
    return _export_laps(folder,numbers,metadata,selected,template)[0]


def _select_laps(folder,numbers):
    folder=Path(folder);metadata=finished_metadata(folder);selected={};counts={}
    from lap_scan_index import load,builder,restore,save,ranges
    indexed=load(folder)
    if indexed is not None:
        selected=restore(folder,numbers,indexed);candidates=indexed['inventory']['candidates'];error=indexed['inventory']['error']
    else:
        index=builder(folder)
        def collect(best):
            if best['number'] in numbers:selected[best['number']]=best
        _,candidates,error=extract_best(folder/'inputs.csv',collect,include_flagged=True,retain_best=False,_index=index)
        save(folder,_lap_inventory(candidates,error),index)
        if index['monotonic']:
            for best in selected.values():
                group=next(value for value in index['groups'] if value['number']==best['number'] and value['start_s']==best['start_s'])
                ranges(best,*group['_range'],index)
    for v in candidates:counts[v['number']]=counts.get(v['number'],0)+1
    for n in numbers:
        if counts.get(n,0)>1:raise ValueError(f'第 {n} 圈的圈号重复，无法唯一提取')
        if n not in selected:
            item=next((v for v in candidates if v['number']==n),None)
            reason={'start of lap missing':'缺少圈起点','end of lap missing':'缺少圈终点','telemetry gap':'遥测存在缺口',
                'incomplete distance coverage':'距离覆盖不完整','timing reset':'计时重置',
                'insufficient or nonmonotonic samples':'采样不足或时间倒退','distance moved backwards or reset':'距离倒退或重置'}.get(item.get('exclusion') if item else '',error or '记录中没有该圈')
            raise ValueError(f'第 {n} 圈不是可提取的完整圈：{reason}')
    return metadata,selected


def _export_laps(folder,numbers,metadata,selected,template=None):
    from lap_exports import remember,link_fastest
    native=load_json(folder/'native_channels.json') if (folder/'native_channels.json').exists() else None
    from vehiclelab import load_recording
    vehicle=load_recording(folder)
    records=[lap_record(folder,selected[n],metadata,native,'selected',vehicle) for n in numbers]
    output=folder/'SelectedLaps';output.mkdir(exist_ok=True);exports=[]
    for n,value in zip(numbers,records):
        stem=f"Selected_Lap_{n}_{safe_name(metadata.get('vehicle'))}_{safe_name(metadata.get('track'))}"
        json_path=output/(stem+'.lap.json');csv_path=output/(stem+'.csv')
        write_json(json_path,value)
        if not link_fastest(folder,n,csv_path):write_lap_csv(csv_path,selected[n],metadata,folder/'inputs.csv')
        exports.append(dict(number=n,json=str(json_path),csv=str(csv_path)))
    page=None
    if template is not None:
        page=output/('Compare_Laps_'+('_'.join(map(str,numbers)))+'.html')
        write_compare(page,template,records,'selected_complete_laps',reference_id=records[0]['id'])
    result=dict(folder=str(output),exports=exports,comparison=str(page) if page else None)
    remember(folder,numbers,template,result)
    for item in exports:remember(folder,[item['number']],None,dict(folder=str(output),exports=[item],comparison=None),individual=True)
    return result,records


def export_fastest(folder, template, library=None):
    folder=Path(folder);metadata=finished_metadata(folder)
    from processing_context import current
    shared=current(folder)
    if shared is not None and shared.values.get('analysed'):
        best=shared.values.get('best');candidates=shared.values['candidates'];error=shared.values['error']
    else:best,candidates,error = extract_best(folder/'inputs.csv')
    summary = dict(status='saved' if best else 'no_complete_lap',candidates=candidates,error=error)
    result = None
    if best:
        result=lap_record(folder,best,metadata,native=shared.values.get('native') if shared is not None else None);info=result['lap']
        name = f"Fastest_Lap_{info['number']}_{safe_name(metadata['vehicle'])}_{safe_name(metadata['track'])}.lap.json"
        write_json(folder/name,result)
        write_lap_csv(folder/'fastest_lap.csv',best,metadata,folder/'inputs.csv')
        from lap_exports import signature
        from storage import atomic_json
        atomic_json(folder/'_fastest_source.json',dict(number=info['number'],signature=signature(folder)))
        (folder/'fastest_lap.svg').write_text(curve_svg(result),encoding='utf-8')
        summary.update(file=name,lap=info,session=result['session'],conditions=result['conditions'])
    write_json(folder/'fastest_lap_summary.json',summary)
    selection = library_laps(library,result) if library and result else ([result] if result else [])
    write_compare(folder/'fastest_lap.html',template,selection,summary['status'],local=True)
    return result,summary
