"""Metadata-only LRU budget for disposable cache directories, never user exports."""
from pathlib import Path
from contextlib import contextmanager
import json,shutil,time,weakref,os
from cache_management import LOCK,target
_pins={};_last={}


def limit(root):
    try:value=json.loads((Path(root)/'storage_settings.json').read_text(encoding='utf8')).get('cache_limit_mb',512)
    except (OSError,ValueError,AttributeError):value=512
    return int(value) if type(value) is int and 32<=value<=8192 else 512


def hold(owner,path):
    key=str(Path(path).resolve())
    with LOCK:_pins[key]=_pins.get(key,0)+1
    weakref.finalize(owner,release,key)


def release(key):
    with LOCK:
        if _pins.get(key,0)>1:_pins[key]-=1
        else:_pins.pop(key,None)


def touch(path):
    path=Path(path)
    try:
        import os
        os.utime(path,None)
    except OSError:pass


def enforce(root,keep=(),force=False):
    if os.environ.get('LMU_STINTRIX_REPORT_WORKER')=='1':return dict(removed_bytes=0)
    root=Path(root).resolve();key=str(root);now=time.monotonic()
    with LOCK:
        if not force and now-_last.get(key,-1e30)<30:return dict(removed_bytes=0)
        _last[key]=now;protected={str(Path(p).resolve()) for p in keep}|set(_pins);units=[];total=0
        for kind in ('training','records'):
            base=target(root,kind)
            if not base.is_dir():continue
            for child in base.iterdir():
                if not child.is_dir() or child.is_symlink() or child.is_junction():continue
                # Only application-generated token directories are disposable.
                if len(child.name) not in (24,32) or any(c not in '0123456789abcdef' for c in child.name):continue
                size=0;safe=True
                for file in child.rglob('*'):
                    if file.is_symlink() or file.is_junction() or not file.resolve().is_relative_to(child.resolve()):safe=False;break
                    if file.is_file():size+=file.stat().st_size
                if not safe:continue
                total+=size;units.append((child.stat().st_mtime_ns,child,size))
        budget=limit(root)*1048576;removed=0
        for _,path,size in sorted(units):
            if total<=budget:break
            if str(path.resolve()) in protected:continue
            shutil.rmtree(path);total-=size;removed+=size
        return dict(removed_bytes=removed,remaining_bytes=total,limit_bytes=budget,pinned=len(protected))
