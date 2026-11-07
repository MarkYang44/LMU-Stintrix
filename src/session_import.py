"""Copy completed Windows session folders into a private, simulator-scoped library."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4
from session_archive import MAX_BYTES, MAX_FILES, MAX_MANIFEST, CHUNK, _safe_path
from storage import atomic_json


def snapshot(folder):
    files={};folded=set();total=0
    for path in sorted(folder.rglob('*')):
        if path.is_symlink() or path.is_junction():raise ValueError('Session contains a link')
        if not path.is_file():continue
        name=path.relative_to(folder).as_posix();_safe_path(name)
        if name=='_folder_import_receipt.json':continue
        if name.casefold() in folded:raise ValueError('Session contains case-colliding filenames')
        folded.add(name.casefold())
        stat=path.stat();total+=stat.st_size
        files[name]=(stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
        if len(files)>MAX_FILES or total>MAX_BYTES:raise ValueError('Session exceeds import limits')
        if path.name.endswith('.pending'):raise ValueError('Session has unfinished writes')
    return files


def import_folder(root, source):
    source=Path(source).expanduser()
    if source.is_symlink() or source.is_junction():raise ValueError('Session folder cannot be a link')
    source=source.resolve();root=Path(root).resolve();collection=root/'ImportedLogs'
    if not source.is_dir():raise ValueError('Select the folder containing session.json')
    if collection.is_relative_to(source) or source.is_relative_to(collection):
        raise ValueError('Import source must be outside the destination collection')
    if collection.is_symlink() or collection.is_junction() or not collection.resolve().is_relative_to(root):
        raise ValueError('Invalid import destination')
    files=snapshot(source)
    if 'session.json' not in files or files['session.json'][0]>MAX_MANIFEST:raise ValueError('Missing or oversized session.json')
    meta=json.loads((source/'session.json').read_text('utf-8-sig'))
    from simulators import accepts
    if not isinstance(meta,dict) or not accepts(root,meta):raise ValueError('Switch to the matching simulator before importing')
    if meta.get('status') not in ('finished','complete','completed','recovered','imported'):
        raise ValueError('Import a completed session; recover unfinished records on Windows first')
    if not {'inputs.csv','inputs.csv.stc'}.intersection(files):raise ValueError('Session has no input telemetry')
    collection.mkdir(parents=True,exist_ok=True)
    identity={name:list(stamp) for name,stamp in files.items()}
    for path in collection.glob('*/_folder_import_receipt.json'):
        if path.is_symlink() or path.parent.is_symlink():continue
        try:
            receipt=json.loads(path.read_text('utf-8'))
            if receipt.get('source')==str(source) and receipt.get('source_files')==identity:
                if all((path.parent/name).is_file() and [(path.parent/name).stat().st_size,(path.parent/name).stat().st_mtime_ns]==stamp for name,stamp in receipt['files'].items()):
                    return dict(status='skipped',folder=str(path.parent))
        except (OSError,ValueError,KeyError):pass
    if shutil.disk_usage(collection).free<sum(v[0] for v in files.values())+16*CHUNK:
        raise OSError('Not enough disk space to import the complete session')
    with tempfile.TemporaryDirectory(prefix='.stintrix-folder-',dir=collection) as work:
        stage=Path(work)/'session';stage.mkdir()
        for name,stamp in files.items():
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);count=0
            # Refuse links introduced after enumeration as well as changed bytes.
            origin=source/name
            ancestors=origin.relative_to(source).parts[:-1]
            if any((source/Path(*ancestors[:i])).is_symlink() or (source/Path(*ancestors[:i])).is_junction() for i in range(len(ancestors)+1)) or origin.is_symlink():
                raise ValueError('Session path changed during import')
            with origin.open('rb') as incoming,target.open('xb') as outgoing:
                for block in iter(lambda:incoming.read(CHUNK),b''):outgoing.write(block);count+=len(block)
            if count!=stamp[0]:raise OSError('Session changed during import')
            shutil.copystat(origin,target)
        if snapshot(source)!=files:raise OSError('Session changed during import; original retained')
        receipt=dict(version=1,source=str(source),source_files=identity,imported_utc=datetime.now(timezone.utc).isoformat(),
            files={name:[(stage/name).stat().st_size,(stage/name).stat().st_mtime_ns] for name in files})
        atomic_json(stage/'_folder_import_receipt.json',receipt)
        from laps import safe_name
        target=collection/(safe_name(source.name)+'_'+uuid4().hex[:12])
        stage.rename(target)
    return dict(status='imported',folder=str(target),files=len(files))
