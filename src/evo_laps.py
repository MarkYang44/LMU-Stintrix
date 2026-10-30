"""EVO lap evidence, streamed after capture. Host time is never a lap clock."""
import json
import math
from telemetry_file import Path

VERSION=4
BOUNDARY_SKEW_MS=100
FIELDS=('time_s','lap','evo_lap_time_ms','evo_last_lap_time_ms','lap_invalidated',
        'in_pits','lap_distance_m','track_length_m','evo_current_pos','evo_total_drivers','evo_is_valid_lap','evo_timing_invalid')


def number(value):
    if value is None or value=='':return None
    try:value=float(value)
    except (TypeError,ValueError):return None
    return value if math.isfinite(value) else None


def _numbers(row):
    # Common complete rows use C numeric conversion. Sparse, nonfinite and
    # unusual tokens retain the original per-field None/finite rules.
    if all(row):
        try:values=list(map(float,row))
        except (TypeError,ValueError):pass
        else:
            if all(map(math.isfinite,values)):return values
    return list(map(number,row))


def stamp(folder):
    from comparison_cache import source
    return dict(version=VERSION,source=source(folder))


def scan(folder):
    """O(laps) memory. Two observed counter boundaries and SDK milliseconds.

    Old input-only records lack last_laptime_ms: retain their observed timer as
    partial evidence, never promote it to a verified personal best.
    """
    folder=Path(folder);result=[];current=None;previous=None;seen=False;positions=[]
    from lap_scan_index import raw_rows
    from lap_validity import evo_flags,finish_evo
    class Cookies(list):
        def append(self,value):
            if len(self)<4096:super().append(value)
    cookies=Cookies()
    reader=raw_rows(folder/'inputs.csv',columns=FIELDS,capture=cookies)
    try:
        for index,row in enumerate(reader):
            values=_numbers(row)
            host,count,timer,last,invalid,pits,distance,length,pos,total,game_positive,game_negative=values
            if host is None or count is None or count<1 or count!=int(count):raise ValueError('EVO record has an invalid capture time or lap counter')
            count=int(count)
            changed=current is not None and count!=current['num']
            if changed:
                contiguous=count==current['num']+1
                boundary_gap=host-previous[0]
                current['max_gap_s']=max(current['max_gap_s'],boundary_gap)
                if boundary_gap<0:current['_reset']=True
                duration=last/1000 if last is not None and last>0 else None
                # Reject a stale last-time field, timer resets, missing boundaries,
                # lost finish samples and sparse/teleported records.
                consistent=bool(duration and current['_max_timer'] is not None and
                    -BOUNDARY_SKEW_MS<=last-current['_max_timer']<=2500 and
                    (last>=current['_max_timer'] or timer is not None and 0<=timer<=BOUNDARY_SKEW_MS))
                current.update(end_index=index,end_capture_s=host,complete=contiguous and duration is not None,
                    time=duration if duration else (current['_max_timer']/1000 if current['_max_timer'] else None),
                    partial=current['partial'] or not contiguous or not consistent or current['_reset'] or current['_start_wrap_pending'] or current['max_gap_s']>2.5 or
                        current['_max_distance']-current['_min_distance']<.8*(current['length_m'] or 1),
                    boundary_timer_delta_ms=last-current['_max_timer'] if last is not None and current['_max_timer'] is not None else None,
                    timing_source='evo_last_laptime_ms' if duration else 'evo_observed_timer_incomplete')
                finish_evo(current)
                result.append(current);seen=contiguous
            if current is None or changed:
                current=dict(num=count,telemetry_lap=count,start=host,observed_start=host,first_index=index,end_index=index+1,
                    time=None,valid=None,s1=None,s2=None,s3=None,partial=not seen or timer is None or not 0<=timer<=500,
                    complete=False,in_pits=False,timing_source='evo_observed_timer_incomplete',samples=0,max_gap_s=0.,
                    length_m=length if length and length>100 else None,_max_timer=None,_reset=False,_invalid=False,_known=True,
                    _min_distance=math.inf,_max_distance=-math.inf,
                    _game_explicit=False,_game_valid=None,_last_invalid=None,_game_disputed=False,
                    _start_wrap_pending=bool(seen and length and distance is not None and .98*length<=distance<=length+1 and timer is not None and 0<=timer<=BOUNDARY_SKEW_MS),
                    boundary_distance_wrap=False)
                previous=None
            if previous is not None:
                gap=host-previous[0]
                if gap<0:current['_reset']=True
                current['max_gap_s']=max(current['max_gap_s'],gap)
                if timer is not None and previous[1] is not None and timer+100<previous[1]:current['_reset']=True
            if timer is not None and timer>=0:current['_max_timer']=max(current['_max_timer'] or 0,timer)
            else:current['_reset']=True
            current['_known'] &= invalid in (0,1)
            current['_invalid'] |= invalid==1
            current['_last_invalid']=invalid
            if game_positive in (0,1) and game_negative in (0,1):
                current['_game_explicit']=True
                current['_game_valid']=evo_flags(game_positive,game_negative)
                current['_game_disputed']=game_positive==game_negative
            elif current['_game_explicit']:
                current['_game_valid']=None;current['_game_disputed']=True
            current['in_pits'] |= pits!=0  # Unknown pit state is excluded as well.
            current['samples']+=1;current['end_index']=index+1
            if length is None or length<=100 or current['length_m'] is None or abs(length-current['length_m'])>1:current['_reset']=True
            if distance is None or length is None or not 0<=distance<=length+1:current['_reset']=True
            elif distance is not None:
                # EVO can publish a new lap counter/timer before npos wraps.
                # Accept only a tightly bounded initial finish-to-start edge.
                # All original rows/coordinates remain in the CSV and curves.
                pending=current['_start_wrap_pending']
                if pending and (timer is None or not 0<=timer<=BOUNDARY_SKEW_MS or not 0<=host-current['start']<=BOUNDARY_SKEW_MS/1000):
                    current['_reset']=True;current['_start_wrap_pending']=False
                elif pending and distance<=.02*length:
                    current['_start_wrap_pending']=False;current['boundary_distance_wrap']=True
                elif pending and distance<.98*length:
                    current['_reset']=True;current['_start_wrap_pending']=False
                if not current['_start_wrap_pending']:
                    if distance<current['_max_distance']-max(100,.02*length):current['_reset']=True
                    current['_min_distance']=min(current['_min_distance'],distance);current['_max_distance']=max(current['_max_distance'],distance)
            if pos is not None and total is not None and 1<=pos<=total<=1000:
                p=(int(pos),int(total))
                if not positions or positions[-1]['data']['to']!=p[0]:positions.append(dict(time=host,event='position',data=dict(to=p[0],**({'from':positions[-1]['data']['to']} if positions else {}))))
            previous=(host,timer)
    finally:reader.close()
    if current:
        current['time']=current['_max_timer']/1000 if current['_max_timer'] else None
        finish_evo(current)
        result.append(current)
    for lap in result:
        for key in tuple(lap):
            if key.startswith('_'):lap.pop(key)
    candidates=[lap for lap in result if lap['complete'] and not lap['partial'] and lap['valid'] is True and not lap['in_pits'] and lap['samples']>=2]
    fastest=min(candidates,key=lambda v:v['time']) if candidates else None
    for lap in result:
        lap['best']=lap is fastest;lap['delta']=lap['time']-fastest['time'] if fastest and lap['time'] else None
    events=[dict(time=lap['end_capture_s'],event='reconstructed_lap',data=lap.copy()) for lap in result if lap['complete']]
    events.extend(positions);events.sort(key=lambda e:e['time'])
    return dict(version=VERSION,laps=result,events=events,fastest=fastest,cookies=cookies)


def index(folder):
    from comparison_cache import scan as cached_scan
    folder=Path(folder)
    return cached_scan(folder,lambda:_index(folder),namespace=('ac_evo',VERSION),files=(folder/'evo_laps_index.json',),limit=4,max_file_bytes=524288)


def _index(folder):
    folder=Path(folder);key=stamp(folder);path=folder/'evo_laps_index.json'
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        if value.get('signature')==key:return value
    except (OSError,ValueError,AttributeError):pass
    from runtime_activity import busy
    if busy():
        from report_worker import ReportDeferred
        raise ReportDeferred('请先停止 HUD，再处理 EVO 圈记录；原始记录已保留')
    from storage import atomic_json
    value=scan(folder)
    if stamp(folder)!=key:raise OSError('EVO record changed during lap analysis; retry after capture stops')
    value['signature']=key;atomic_json(path,value);return value


def model(folder):
    from race_model import read_json
    from library import session_label
    folder=Path(folder);meta=read_json(folder/'session.json',{})
    if meta.get('simulator_id')!='ac_evo' or meta.get('status')=='recording':raise ValueError('Not a completed EVO record')
    value=index(folder);laps=value['laps'];events=value['events']
    return dict(format='stintrix.race-report',version=1,session=meta,session_type=session_label(meta.get('session')),
        summary={},laps=laps,events=events,origin=min((lap['start'] for lap in laps),default=0),fastest=value['fastest'],
        sector_bests=[None,None,None],scoring_available=False,lap_number_source='evo_counter',
        note='AC EVO：圈速来自游戏毫秒计时；只计完整、有效、无进站且连续的圈。分段、碰撞和确认完赛成绩未采集；旧记录不补造圈速。')


def lap_info(best):
    return dict(number=best['num'],time_s=best['time'],validity='verified',timing_source='evo_last_laptime_ms',
        distance_source='EVO npos * track_length_m',cadence_s=None,track_length_m=best['length_m'],
        start_session_time_s=None,end_session_time_s=None,sample_count=best['samples'],boundary_interpolation=False,
        lap_number_source='AC EVO total_lap_count + 1',lap_invalidated=False,in_pits=False)


def read_curve(folder,best,value,target,csv_file=None):
    """Seek the exact observed range; one text pass supplies CSV and float64 channels."""
    from analysis_spool import DiskTable
    from lap_scan_index import raw_rows
    fields=('lap_distance_m','evo_lap_time_ms','throttle','brake','filtered_throttle','filtered_brake','speed_kmh')
    columns=fields;writer=None;paired=False
    if csv_file is not None:
        import csv
        from pathlib import Path as NativePath
        from csv_projection import projector
        from evo_exports import _plain,_csv_lines
        with (Path(folder)/'inputs.csv').open(encoding='utf-8-sig',newline='') as stream:columns=next(csv.reader(stream))
        project=projector(columns,fields);writer=csv.writer(csv_file);writer.writerow(columns)
        paired=_plain(NativePath(folder),columns)
    def rows():
        if paired:
            reader=_csv_lines(NativePath(folder)/'inputs.csv',best['first_index'],best['end_index'],value.get('cookies',()),columns,projected=fields)
        else:reader=raw_rows(Path(folder)/'inputs.csv',start=best['first_index'],end=best['end_index'],cookies=value.get('cookies',()),columns=columns)
        try:
            for row in reader:
                if paired:
                    encoded,row=row;csv_file.write(encoded)
                elif writer is not None:writer.writerow(row);row=project(row)
                numbers=list(map(float,row))
                if not all(map(math.isfinite,numbers)):raise ValueError('Invalid EVO lap input')
                numbers[1]/=1000
                yield numbers
        finally:reader.close()
    data=DiskTable(rows(),7,target)
    if len(data)!=best['end_index']-best['first_index'] or stamp(folder)!=value['signature']:
        data.close();raise OSError('EVO lap source changed; retry after capture stops')
    return data


def export(folder,target=None):
    """Shared personal-record schema; exact input values, no boundary synthesis."""
    from laps import write_json,FORMAT,DATA_COLUMNS
    from storage import atomic_json
    from race_model import read_json
    folder=Path(folder);target=Path(target or folder);target.mkdir(parents=True,exist_ok=True)
    value=index(folder);best=value['fastest'];meta=read_json(folder/'session.json',{})
    summary=dict(status='no_complete_lap',simulator_id='ac_evo',signature=value['signature'])
    if best:
        info=lap_info(best);data=read_curve(folder,best,value,target)
        record=dict(format=FORMAT,version=1,id=folder.name+':'+str(best['num']),session=meta,lap=info,
            data_columns=DATA_COLUMNS,data=data,conditions={},trajectory=None,reference_kind='fastest',
            input_channels=meta.get('input_channels',{}),simulator_id='ac_evo')
        try:
            if len(data)!=best['end_index']-best['first_index'] or stamp(folder)!=value['signature']:raise OSError('EVO lap source changed; retry after capture stops')
            write_json(target/'fastest_lap.json',record)
            write_curve(target/'fastest_lap.html',record,target/'fastest_lap.json')
        finally:data.close()
        summary.update(status='saved',file='fastest_lap.json',session=meta,lap=info,conditions={})
    atomic_json(target/'fastest_lap_summary.json',summary)
    return summary


def write_curve(path,record,source):
    """Single and paired EVO views share exact samples and native clock rules."""
    from runtime_activity import busy
    if busy():
        from report_worker import ReportDeferred
        raise ReportDeferred('请先停止 HUD，再生成 EVO 完整圈曲线；原始记录已保留')
    from paths import ASSETS
    from pathlib import Path as NativePath
    from laps import write_compare
    write_compare(path,ASSETS/'evo_compare.html',[record],'evo_single_valid_lap',
        view_state=dict(source_file=NativePath(source).resolve().as_uri()))
