"""Reuse unchanged exports by provenance and file metadata, without content reads."""
import json
from pathlib import Path
from cache_management import LOCK
from storage import atomic_json


def signature(files,note,format):return dict(files=[[n,s,p.stat().st_mtime_ns] for n,p,s in files],note=note,format=format)


def load(root):
    path=Path(root)/'ExportCache/index.json'
    try:
        if path.stat().st_size>4*1048576:return []
        value=json.loads(path.read_text(encoding='utf8'));return value if isinstance(value,list) else []
    except (OSError,ValueError):return []


def find(root,stamp,destination):
    with LOCK:
        for value in load(root):
            if value.get('signature')!=stamp:continue
            p=Path(value['path'])
            if p.parent!=Path(destination):continue
            try:
                s=p.stat()
                if [s.st_size,s.st_mtime_ns]==value['file_stamp']:return dict(path=str(p),bytes=s.st_size,source_bytes=sum(v[1] for v in stamp['files']),reused=True)
            except OSError:continue


def remember(root,stamp,path,archive_id):
    path=Path(path);s=path.stat();index=Path(root)/'ExportCache/index.json';index.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        values=[v for v in load(root) if v.get('path')!=str(path)]
        values.insert(0,dict(signature=stamp,path=str(path),archive_id=archive_id,file_stamp=[s.st_size,s.st_mtime_ns]))
        bounded=[];used=2
        for item in values[:256]:
            length=len(json.dumps(item,ensure_ascii=False,indent=2).encode('utf8'))+64
            if used+length>3*1048576:continue
            bounded.append(item);used+=length
        atomic_json(index,bounded)
