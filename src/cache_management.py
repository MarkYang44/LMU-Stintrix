"""Explicit allowlist: generated caches can be removed; race evidence cannot."""
import shutil,stat
from pathlib import Path
from threading import RLock
LOCK=RLock()
CACHES={'training':('训练曲线缓存','PersonalRecords/TrainingCache'),'records':('派生最快圈缓存','PersonalRecords/Cache'),'catalog':('赛事摘要索引','EventCatalog/index.json')}
READONLY={'video':('视频提取结果（保留）','VideoCurves'),'cards':('用户导出战绩卡','PersonalRecords/AchievementCards'),'curves':('用户导出圈曲线','PersonalRecords/History'),'comparisons':('圈 A / 圈 B 对比','LapComparisons'),'reports':('用户导出训练报告','PersonalRecords/TrainingReports'),'comparable':('用户导出进步报告','PersonalRecords/ComparableReports'),'goals':('训练目标与基准','PersonalRecords/TrainingGoals'),'races':('原始赛事（保留）','Logs'),'imported':('导入赛事（保留）','ImportedLogs'),'recovered':('恢复赛事（保留）','RecoveredLogs')}

def target(root,key):
    root=Path(root).resolve()
    if key not in CACHES:raise ValueError('只能清理明确标为可重建的缓存')
    path=root/CACHES[key][1];resolved=path.resolve()
    if resolved!=path or not resolved.is_relative_to(root) or path.is_symlink():raise ValueError('拒绝清理外部链接')
    return path

def size(path):
    if path.is_symlink():return 0,0
    directory=path.is_dir();base=path.resolve() if directory else path.parent.resolve()
    paths=path.rglob('*') if directory else [path]
    total=count=0
    for p in paths:
        if p.is_symlink() or not p.resolve().is_relative_to(base):continue
        try:
            info=p.stat()
            if stat.S_ISREG(info.st_mode):total+=info.st_size;count+=1
        except OSError:continue
    return total,count

def inventory(root):
    root=Path(root).resolve();out=[]
    for key,(name,relative) in {**CACHES,**READONLY}.items():
        path=root/relative;total,count=size(path)
        out.append(dict(key=key,name=name,path=str(path),bytes=total,files=count,clearable=key in CACHES))
    return out

def clear(root,keys,active=False):
    if active:raise ValueError('请先停止 HUD 并等待分析任务结束，再清理缓存')
    paths=[target(root,key) for key in dict.fromkeys(keys)]
    with LOCK:
        removed=0
        for path in paths:
            # Verify every resolved descendant before a recursive delete.
            if path.is_dir():
                for child in path.rglob('*'):
                    if child.is_symlink() or not child.resolve().is_relative_to(path.resolve()):raise ValueError('缓存内存在外部链接，未清理')
                removed+=size(path)[0];shutil.rmtree(path)
            elif path.is_file():removed+=path.stat().st_size;path.unlink()
    return removed
