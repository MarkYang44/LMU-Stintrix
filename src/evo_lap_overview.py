"""Read-only EVO lap facts; statistics use the same eligible laps as exports."""
from pathlib import Path
import math,statistics
from collections import deque
from evo_comparison import available


def summary(value):
    usable=available(value);times=[lap['time'] for lap in usable.values()]
    return dict(total=len(value['laps']),valid=len(times),fastest=min(times) if times else None,
        median=statistics.median(times) if times else None,std=statistics.pstdev(times) if len(times)>1 else None)


def selection_summary(rows):
    """Observed usable laps only; no condition correction or source reads."""
    rows=list(rows);times=[row['lap']['time'] for row in rows if row['usable']]
    return dict(total=len(rows),valid=len(times),mean=statistics.fmean(times) if times else None,
        fastest=min(times) if times else None,slowest=max(times) if times else None,
        std=statistics.pstdev(times) if len(times)>1 else None)


def fastest_runs(rows):
    """Best observed 3/5-lap windows, within the current eligible selection only."""
    result={};tail=deque(maxlen=5);previous=None
    ordered=sorted(((key,row['lap']) for key,row in rows.items() if row['usable']),key=lambda pair:pair[1]['first_index'])
    for key,lap in ordered:
        if previous is not None and (lap['num']!=previous['num']+1 or lap['first_index']!=previous['end_index']):tail.clear()
        tail.append((key,lap));previous=lap
        for count in (3,5):
            if len(tail)<count:continue
            group=list(tail)[-count:];mean=math.fsum(item['time'] for _,item in group)/count
            if count not in result or mean<result[count]['mean_s']:
                result[count]=dict(keys=tuple(k for k,_ in group),first=group[0][1]['num'],last=lap['num'],mean_s=mean)
    return result


def load(root,folder):
    from comparison_cache import source
    from laps import finished_metadata
    from simulators import accepts,root_identity
    from evo_laps import index
    root=Path(root).resolve();folder=Path(folder).resolve()
    if root_identity(root)!='ac_evo' or not folder.is_relative_to(root):raise ValueError('只能选择当前 AC EVO 目录中的赛事')
    signature=source(folder);meta=finished_metadata(folder)
    if not accepts(root,meta) or meta.get('simulator_id')!='ac_evo':raise ValueError('只能选择当前 AC EVO 目录中的赛事')
    value=index(folder)
    if source(folder)!=signature:raise OSError('赛事数据已变化，请重新选择并重试')
    return dict(folder=folder,session=meta,index=value,summary=summary(value))


def timing_csv(root,folder,destination,result,indices):
    """Current displayed lap facts only; no index rebuild, curves or raw samples."""
    import csv,os,re,tempfile
    from uuid import uuid4
    from evo_laps import stamp
    from simulators import accepts,root_identity
    from runtime_activity import busy
    from report_worker import ReportDeferred
    root=Path(root).resolve();folder=Path(folder).resolve()
    if root_identity(root)!='ac_evo' or not folder.is_relative_to(root) or Path(result['folder']).resolve()!=folder:raise ValueError('只能选择当前 AC EVO 目录中的赛事')
    if busy():raise ReportDeferred('请先停止 HUD，再导出圈速清单；原始记录已保留')
    meta=result['session'];value=result['index'];indices=tuple(indices)
    if not accepts(root,meta) or meta.get('simulator_id')!='ac_evo':raise ValueError('只能选择当前 AC EVO 目录中的赛事')
    if not indices or any(type(i) is not int or not 0<=i<len(value['laps']) for i in indices) or len(set(indices))!=len(indices):raise ValueError('请选择圈速清单中的有效行')
    signature=value['signature']
    if stamp(folder)!=signature:raise OSError('赛事数据已变化，请刷新圈速后重试')
    eligible=available(value);best=min((lap['time'] for lap in eligible.values()),default=None)
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    track=re.sub(r'[^\w.-]+','_',str(meta.get('track') or 'AC_EVO'))[:80]
    target=destination/f'{track}-Lap-Times-{uuid4().hex[:12]}.csv'
    fd,name=tempfile.mkstemp(prefix='.evo-times-',suffix='.pending',dir=destination);pending=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf-8-sig',newline='') as out:
            writer=csv.writer(out)
            writer.writerow(('simulator','track','layout','vehicle','session_started_utc','lap','time_s','delta_to_session_best_s','eligible_for_export','complete','partial','valid','in_pits','samples','timing_source'))
            for i in indices:
                lap=value['laps'][i];usable=eligible.get(lap['num']) is lap
                writer.writerow(('ac_evo',meta.get('track'),meta.get('track_layout'),meta.get('vehicle'),meta.get('started_utc'),lap['num'],lap['time'],
                    lap['time']-best if usable and best is not None else None,usable,lap['complete'],lap['partial'],lap['valid'],lap['in_pits'],lap['samples'],lap.get('timing_source')))
        if stamp(folder)!=signature:raise OSError('赛事数据已变化，请刷新圈速后重试')
        if target.exists():raise FileExistsError(str(target))
        pending.rename(target)
    finally:pending.unlink(missing_ok=True)
    return dict(path=str(target),rows=len(indices))
