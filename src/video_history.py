"""Read-only bridge from video estimates to already exported, verified local laps."""
from pathlib import Path
import json, math, tempfile, uuid
from video_alignment import native_header,native_data,crossings
from video_media import Cancelled


def circuit_key(value):
    from track_names import key,LOOKUP
    token=key(value)
    # ASCII aliases share the display identity; unknown non-Latin names must not collapse to ''.
    return LOOKUP.get(token) or token or str(value).strip().casefold()


def identity(header):
    session=header['session'];lap=header['lap']
    value=dict(track=session.get('track',''),track_layout=session.get('track_layout',''),length_m=float(lap['track_length_m']))
    if not value['track'] or not value['track_layout'] or not math.isfinite(value['length_m']) or value['length_m']<=100:
        raise ValueError('历史圈缺少明确的赛道、布局或长度')
    if header.get('format')!='inputscope.fastest-lap' or lap.get('validity')!='verified' or lap.get('lap_invalidated') or lap.get('in_pits'):
        raise ValueError('请选择已验证的有效完整圈，排除进站圈和无效圈')
    return value


def compatible(a,b):
    return (circuit_key(a['track'])==circuit_key(b['track']) and
            str(a['track_layout']).strip().casefold()==str(b['track_layout']).strip().casefold() and
            abs(a['length_m']-b['length_m'])<=2)


def load_video(path):
    path=Path(path)
    if path.stat().st_size>32*1024*1024:raise ValueError('视频结果超过 32 MiB，请选择单圈 curve.json')
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if value.get('format')!='stintrix.video-curves' or not value.get('rows'):raise ValueError('请选择视频提取生成的 curve.json')
    return value


def history_laps(root,video,cancel=None):
    """Only small headers; never scan every session CSV or load their curves."""
    from library import inventory
    root=Path(root).resolve();out=[];seen=set()
    for event in inventory(root):
        if cancel and cancel.is_set():raise Cancelled('已取消')
        if event['source']=='DemoLogs' or event['status'] in ('recording','write_error'):continue
        if circuit_key(event['track'])!=circuit_key(video['identity']['track']):continue
        folder=Path(event['folder']);files=[]
        if event.get('fastest_file'):files.append(folder/event['fastest_file'])
        files.extend((folder/'SelectedLaps').glob('*.lap.json'))
        for path in files:
            path=path.resolve()
            if path in seen or not path.is_relative_to(root) or not path.is_file():continue
            seen.add(path)
            try:
                header=native_header(path);ident=identity(header)
                if circuit_key(ident['track'])!=circuit_key(video['identity']['track']):continue
                session=header['session'];lap=header['lap']
                out.append(dict(file=str(path),identity=ident,date=session.get('started_utc',event['date']),
                    vehicle=session.get('vehicle',event['vehicle']),number=lap['number'],time_s=float(lap['time_s']),
                    exact=compatible(video['identity'],ident)))
            except (OSError,ValueError,KeyError,TypeError):continue
    return sorted(out,key=lambda v:(v['exact'],str(v['date'])),reverse=True)


def reference_curve(path,channel='filtered',cancel=None):
    if channel not in ('raw','filtered'):raise ValueError('未知的历史输入通道')
    path=Path(path)
    if path.stat().st_size>1024*1024*1024:raise ValueError('历史圈文件超过 1 GiB')
    header=native_header(path);ident=identity(header)
    value=native_data(path,cancel,channel);samples=value['data'];duration=float(header['lap']['time_s'])
    if len(samples)<10 or not 0<duration<=1800:raise ValueError('历史圈样本或圈时不足')
    if samples[0][0]>.15 or abs(samples[-1][0]-duration)>.2:raise ValueError('历史圈缺少完整计时边界')
    rows=[dict(lap_time_s=t,distance_m=d,throttle=g,brake=b,status='native') for t,d,g,b in samples]
    coverage=(samples[-1][1]-samples[0][1])/ident['length_m']
    gaps=[samples[i][0]-samples[i-1][0] for i in range(1,len(samples))]
    distance_ready=samples[0][1]<=20 and samples[-1][1]>=ident['length_m']-30 and coverage>=.95 and max(gaps)<=1
    return dict(format='stintrix.history-curve',id=uuid.uuid4().hex[:12],identity=ident,rows=rows,
        duration_s=duration,channel=channel,quality=dict(distance_usable=distance_ready),
        session=header['session'],lap=header['lap'],file=path.name)


def compare_history(video,reference,bind_layout=False,landmarks=()):
    a=video['identity'];b=reference['identity'];exact=compatible(a,b)
    if circuit_key(a['track'])!=circuit_key(b['track']):raise ValueError('只能对比同一赛道的历史圈')
    if not exact:
        if not bind_layout:raise ValueError('布局标签或长度不一致；确认视频采用所选历史布局后，勾选关联布局')
        if video['quality'].get('distance_usable'):raise ValueError('已有距离的视频不能重绑定不同布局或长度，请修正标定后重新提取')
    marks={str(m['name']):float(m['video_s'])-video['start_s'] for m in video.get('landmarks',[])}
    paired=[];seen=set()
    for mark in landmarks:
        name=str(mark['name']).strip();t=float(mark['lap_time_s'])
        if not name or name in seen or name not in marks or not math.isfinite(t) or not 0<=t<=reference['duration_s']:
            raise ValueError('历史地标须使用视频中已有的唯一名称，且时间位于历史圈内')
        seen.add(name);paired.append((marks[name],t,name))
    paired.sort();segments=[]
    for x,y in zip(paired,paired[1:]):
        if y[0]<=x[0] or y[1]<=x[1]:raise ValueError('两圈地标必须按相同顺序递增')
        segments.append(dict(name=x[2]+' → '+y[2],a_s=y[0]-x[0],b_s=y[1]-x[1],delta_s=(y[1]-x[1])-(y[0]-x[0])))
    delta=[]
    if exact and video['quality'].get('distance_usable') and reference['quality'].get('distance_usable'):
        for d in range(0,int(b['length_m'])+1,10):
            ta=crossings(video['rows'],d,1);tb=crossings(reference['rows'],d,1)
            delta.append([d,None if ta is None or tb is None else tb-ta])
    session=reference['session'];lap=reference['lap']
    return dict(format='stintrix.video-history-comparison',version=1,identity=b,a=video['id'],b=reference['id'],
        segments=segments,delta=delta,video_identity=a,layout_bound=not exact,
        video_duration_s=video['end_s']-video['start_s'],reference_duration_s=reference['duration_s'],
        reference=dict(file=reference['file'],vehicle=session.get('vehicle',''),date=session.get('started_utc',''),
                       number=lap['number'],channel=reference['channel']),
        note='A 为视频估算，B 为历史遥测；Δ = B − A，负值表示历史圈更快。时间轴只对齐圈起点，同一秒不代表同一位置。')


def export_comparison(video_path,lap_path,root,channel='filtered',bind_layout=False,landmarks=(),cancel=None):
    video=load_video(video_path);reference=reference_curve(lap_path,channel,cancel)
    comparison=compare_history(video,reference,bind_layout,landmarks)
    output=Path(root).resolve()/'VideoCurves';output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pending-history-',dir=output) as scratch:
        from video_report import write_history_comparison
        folder=Path(scratch)
        (folder/'comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf8')
        write_history_comparison(folder/'report.html',comparison,video,reference)
        if cancel and cancel.is_set():raise Cancelled('已取消')
        target=output/('History-'+uuid.uuid4().hex[:12]);folder.rename(target)
    return dict(folder=str(target),report=str(target/'report.html'))
