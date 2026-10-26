"""Streamed ZIP / 7z exports; no content hashing or verification passes."""
from datetime import datetime, timezone
import json
import os
from pathlib import PurePosixPath
from telemetry_file import Path
import re
import shutil
import stat
import tempfile
import uuid
from contextlib import contextmanager
import zipfile
from library import inventory,session_label
from laps import safe_name

from legacy_identity import ARCHIVE_FORMAT
FORMAT='stintrix.session-archive'
COLLECTIONS=('Logs','ImportedLogs','RecoveredLogs','DemoLogs')
LOCAL_FILES={'_archive_receipt.json','_archive_note.json','_exports.json','_fastest_source.json','_lap_scan.json'}
CHUNK=1048576
MAX_FILES=50000
MAX_BYTES=32*1024**3
MAX_MANIFEST=8*1024**2
DEVICE=re.compile(r'^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)',re.I)


def _safe_path(name):
    if not isinstance(name,str) or not name or '\\' in name:
        raise ValueError('比赛包包含无效路径')
    parts=name.split('/')
    if any(not p or p in ('.','..') or p.endswith((' ','.')) or len(p)>180
           or DEVICE.match(p) or any(c in '<>:"|?*' or ord(c)<32 for c in p) for p in parts):
        raise ValueError('比赛包包含不安全的路径：'+name)
    return PurePosixPath(name)


def _identity(files,note):
    return uuid.uuid4().hex+uuid.uuid4().hex


def _session(root,key):
    rel=_safe_path(Path(key).as_posix())
    if len(rel.parts)!=2 or rel.parts[0] not in COLLECTIONS:
        raise ValueError('请选择记录管理中的比赛')
    source=root/str(rel);folder=source.resolve()
    if not folder.is_relative_to(root) or source.is_symlink() or source.is_junction():raise ValueError('记录路径无效')
    if (folder/'.storage_compression.pending').exists():raise ValueError('该赛事正在压缩，请稍后重试')
    meta=json.loads((folder/'session.json').read_text(encoding='utf-8-sig'))
    if not isinstance(meta,dict):raise ValueError('比赛信息无效')
    if meta.get('status')=='recording':raise ValueError('请等录制结束后再导出；中断记录请先恢复')
    if not (folder/'inputs.csv').is_file():raise ValueError('记录缺少 inputs.csv')
    return folder,meta


def _files(folder):
    out=[];total=0
    for p in sorted(folder.rglob('*')):
        if p.is_symlink() or p.is_junction():raise ValueError('比赛目录包含链接，不能打包')
        if not p.is_file():continue
        if p.name in ('inputs.csv.stc','vehicle.csv.stc'):
            from pathlib import Path as NativePath
            raw=NativePath(str(p)[:-4])
            if raw.is_file():continue
            p=Path(raw)
        rel=p.relative_to(folder).as_posix();_safe_path(rel)
        if p.name in LOCAL_FILES or p.name.endswith(('.pending','.tmp')):continue
        size=p.stat().st_size;total+=size;out.append((rel,p,size))
    if len(out)>MAX_FILES or total>MAX_BYTES:raise ValueError('比赛包超过 50000 个文件或 32 GiB 上限')
    return out


def export_session(root,key,destination,format='zip'):
    if format=='7z':return export_7z(root,key,destination)
    if format!='zip':raise ValueError('请选择 ZIP 或 7z')
    root=Path(root).resolve();folder,meta=_session(root,key)
    destination=Path(destination).resolve()
    if destination.is_relative_to(folder):raise ValueError('导出目录不能位于这场比赛内部')
    destination.mkdir(parents=True,exist_ok=True)
    files=_files(folder)
    item=next(v for v in inventory(root) if v['key']==str(folder.relative_to(root)))
    note=dict(text=item['note'],traffic=item['traffic'])
    from export_cache import signature,find,remember
    stamp=signature(files,note,format);existing=find(root,stamp,destination)
    if existing:return existing
    fd,pending=tempfile.mkstemp(prefix='.stintrix-',suffix='.pending',dir=destination);os.close(fd)
    pending=Path(pending);entries={}
    try:
        with zipfile.ZipFile(pending,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as out:
            for name,path,size in files:
                count=0;before=path.stat()
                with path.open('rb') as source,out.open('session/'+name,'w',force_zip64=True) as target:
                    for b in iter(lambda:source.read(CHUNK),b''):target.write(b);count+=len(b)
                after=path.stat()
                if count!=size or before.st_mtime_ns!=after.st_mtime_ns or before.st_size!=after.st_size:
                    raise OSError('记录在导出时发生变化，请稍后重试')
                entries[name]=dict(bytes=count)
            if [n for n,_,_ in _files(folder)]!=[n for n,_,_ in files]:
                raise OSError('记录文件列表发生变化，请稍后重试')
            manifest=dict(format=FORMAT,version=2,archive_id=_identity(entries,note),
                exported_utc=datetime.now(timezone.utc).isoformat(),original_key=str(folder.relative_to(root)),
                session_name=folder.name,files=entries,note=note,
                summary={k:meta.get(k,'') for k in ('track','vehicle','driver','started_utc','status')})
            out.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        label='_'.join((safe_name(meta.get('started_utc','')[:19]),session_label(meta.get('session')),
                        safe_name(meta.get('track','')),safe_name(meta.get('vehicle',''))))
        target=destination/(label+'_'+manifest['archive_id'][:12]+'.stintrix.zip')
        # Unique existing exports are kept. A rename is atomic and fails if the target exists on Windows.
        if target.exists():target=target.with_name(target.stem+'_'+uuid.uuid4().hex[:8]+'.zip')
        pending.rename(target);remember(root,stamp,target,manifest['archive_id'])
        return dict(path=str(target),bytes=target.stat().st_size,source_bytes=sum(e['bytes'] for e in entries.values()))
    finally:
        pending.unlink(missing_ok=True)


def _validate(archive,verify=False):
    infos=archive.infolist();names={};total=0
    if len(infos)>MAX_FILES+1:raise ValueError('比赛包文件数量过多')
    for info in infos:
        _safe_path(info.filename)
        folded=info.filename.casefold()
        mode=info.external_attr>>16
        if folded in names or info.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0,stat.S_IFREG)):
            raise ValueError('比赛包包含重复路径、目录或链接')
        if info.flag_bits&1 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
            raise ValueError('比赛包加密或使用了不支持的压缩格式')
        total+=info.file_size;names[folded]=info
    if total>MAX_BYTES:raise ValueError('比赛包展开后超过 32 GiB')
    info=names.get('manifest.json')
    if info is None or info.filename!='manifest.json' or info.file_size>MAX_MANIFEST:raise ValueError('不是有效的 Stintrix 比赛包')
    manifest=json.loads(archive.read(info).decode('utf-8'))
    if not isinstance(manifest,dict) or manifest.get('format') not in (FORMAT,ARCHIVE_FORMAT) or manifest.get('version') not in (1,2):
        raise ValueError('比赛包格式或版本不支持')
    files=manifest.get('files');note=manifest.get('note')
    if not isinstance(manifest.get('original_key'),str):raise ValueError('比赛包来源路径无效')
    if not isinstance(files,dict) or not files or not isinstance(note,dict) or not isinstance(note.get('text'),str) or len(note['text'])>2000 or not isinstance(note.get('traffic'),bool):
        raise ValueError('比赛包清单或备注无效')
    for name,entry in files.items():
        _safe_path(name)
        if PurePosixPath(name).name in LOCAL_FILES:raise ValueError('比赛包包含保留文件')
        info=names.get(('session/'+name).casefold())
        if (not isinstance(entry,dict) or info is None or info.filename!='session/'+name
                or type(entry.get('bytes')) is not int or entry['bytes']!=info.file_size):
            raise ValueError('比赛包清单与文件不一致')
    if len(names)!=len(files)+1 or not {'inputs.csv','session.json'}.issubset(files):raise ValueError('比赛包缺少记录文件或包含未声明文件')
    if not re.fullmatch('[0-9a-f]{64}',str(manifest.get('archive_id',''))):raise ValueError('比赛包编号无效')
    return manifest


def _verify_member(archive,name,entry,target=None,verify=False):
    with archive.open(name) as source:
        for block in iter(lambda:source.read(CHUNK),b''):
            if target is not None:target.write(block)


def import_session(root,package,verify=False):
    root=Path(root).resolve();collection=root/'ImportedLogs'
    if collection.is_symlink() or collection.is_junction() or not collection.resolve().is_relative_to(root):
        raise ValueError('导入目录不能指向数据目录之外')
    collection.mkdir(parents=True,exist_ok=True)
    with _reader(package,collection) as archive:
        manifest=_validate(archive,verify=False)
        from export_cache import load,signature
        for previous in load(root):
            if previous.get('archive_id')!=manifest['archive_id']:continue
            try:
                origin,_=_session(root,manifest['original_key'])
                if signature(_files(origin),manifest['note'],previous['signature']['format'])==previous['signature']:
                    return dict(status='skipped',folder=str(origin),package=str(package))
            except (OSError,ValueError,KeyError):pass
        # Package identity is provenance, not an assertion of content equality.
        for receipt_path in collection.glob('*/_archive_receipt.json'):
            try:
                receipt=json.loads(receipt_path.read_text(encoding='utf8'))
                if receipt.get('archive_id')==manifest['archive_id']:
                    stamps=receipt.get('files',{})
                    if stamps and all((receipt_path.parent/n).is_file() and [(receipt_path.parent/n).stat().st_size,(receipt_path.parent/n).stat().st_mtime_ns]==v for n,v in stamps.items()):
                        return dict(status='skipped',folder=str(receipt_path.parent),package=str(package))
            except (OSError,ValueError):continue
        # Extract into staging first. Neither mode publishes partially extracted data.
        if shutil.disk_usage(collection).free<sum(e['bytes'] for e in manifest['files'].values())+16*CHUNK:
            raise OSError('可用磁盘空间不足以导入比赛包')
        with tempfile.TemporaryDirectory(prefix='.stintrix-import-',dir=collection) as temporary:
            stage=Path(temporary)/'session';stage.mkdir()
            for name,entry in manifest['files'].items():
                path=stage/name;path.parent.mkdir(parents=True,exist_ok=True)
                with path.open('xb') as target:_verify_member(archive,'session/'+name,entry,target,verify=verify)
            if manifest['files']['session.json']['bytes']>MAX_MANIFEST:raise ValueError('比赛信息文件过大')
            meta=json.loads((stage/'session.json').read_text(encoding='utf-8-sig'))
            if not isinstance(meta,dict) or meta.get('status')=='recording':raise ValueError('比赛包不是已结束的记录')
            if any(not isinstance(meta.get(k,''),str) for k in ('track','vehicle','driver','started_utc','status')):
                raise ValueError('比赛包的基本信息字段无效')
            (stage/'_archive_note.json').write_text(json.dumps(manifest['note'],ensure_ascii=False),encoding='utf-8')
            receipt=dict(archive_id=manifest['archive_id'],imported_utc=datetime.now(timezone.utc).isoformat(),verification='none',files={n:[(stage/n).stat().st_size,(stage/n).stat().st_mtime_ns] for n in manifest['files']})
            (stage/'_archive_receipt.json').write_text(json.dumps(receipt),encoding='utf-8')
            folder=collection/(safe_name(manifest.get('session_name') or 'Session')+'_Imported_'+manifest['archive_id'][:12])
            if folder.exists():folder=folder.with_name(folder.name+'_'+uuid.uuid4().hex[:8])
            stage.rename(folder)
            return dict(status='imported',folder=str(folder),package=str(package))


def transfer_batch(values,operation,progress=None):
    """An invalid package/session does not discard other successful transfers."""
    result=dict(items=[],errors=[])
    for index,value in enumerate(values,1):
        if progress:progress(index,len(values))
        try:result['items'].append(operation(value))
        except Exception as e:
            result['errors'].append(dict(item=str(value),error=str(e)))
    return result


@contextmanager
def _reader(package,collection):
    with Path(package).open('rb') as source:magic=source.read(6)
    if magic==b'7z\xbc\xaf\x27\x1c':
        from sevenzip import Reader
        with tempfile.TemporaryDirectory(prefix='.stintrix-7z-',dir=collection) as work:
            yield Reader(package,work)
    else:
        with zipfile.ZipFile(package) as archive:yield archive


def export_7z(root,key,destination):
    from sevenzip import create,Reader
    root=Path(root).resolve();folder,meta=_session(root,key);destination=Path(destination).resolve()
    if destination.is_relative_to(folder):raise ValueError('导出目录不能位于这场比赛内部')
    destination.mkdir(parents=True,exist_ok=True);files=_files(folder)
    item=next(v for v in inventory(root) if v['key']==str(folder.relative_to(root)))
    note=dict(text=item['note'],traffic=item['traffic']);entries={};stamps={}
    from export_cache import signature,find,remember
    stamp=signature(files,note,'7z');existing=find(root,stamp,destination)
    if existing:return existing
    for name,path,size in files:
        file_stat=path.stat();entries[name]=dict(bytes=size);stamps[name]=(file_stat.st_size,file_stat.st_mtime_ns)
    manifest=dict(format=FORMAT,version=2,archive_id=_identity(entries,note),container_layout='flat',
        exported_utc=datetime.now(timezone.utc).isoformat(),original_key=str(folder.relative_to(root)),
        session_name=folder.name,files=entries,note=note,
        summary={k:meta.get(k,'') for k in ('track','vehicle','driver','started_utc','status')})
    # Place scratch beside the destination; no source copies or hard links.
    with tempfile.TemporaryDirectory(prefix='.stintrix-export-',dir=destination) as temporary:
        work=Path(temporary);pending=work/'session.7z'
        from pathlib import Path as NativePath
        source_folder=folder
        if any(not NativePath(path).is_file() for _,path,_ in files):
            source_folder=work/'materialized';source_folder.mkdir()
            for name,path,_ in files:
                target_file=source_folder/name;target_file.parent.mkdir(parents=True,exist_ok=True)
                if NativePath(path).is_file():
                    try:os.link(path,target_file)
                    except OSError:shutil.copyfile(path,target_file)
                else:
                    with path.open('rb') as src,target_file.open('wb') as dst:shutil.copyfileobj(src,dst,CHUNK)
        create(pending,source_folder,entries,json.dumps(manifest,ensure_ascii=False,indent=2),work)
        if [n for n,_,_ in _files(folder)]!=list(entries):raise OSError('记录文件列表发生变化，请稍后重试')
        for name,path,_ in files:
            file_stat=path.stat()
            if (file_stat.st_size,file_stat.st_mtime_ns)!=stamps[name]:raise OSError('记录在导出时发生变化，请稍后重试')
        label='_'.join((safe_name(meta.get('started_utc','')[:19]),session_label(meta.get('session')),
            safe_name(meta.get('track','')),safe_name(meta.get('vehicle',''))))
        target=destination/(label+'_'+manifest['archive_id'][:12]+'.stintrix.7z')
        if target.exists():target=target.with_name(target.stem+'_'+uuid.uuid4().hex[:8]+'.7z')
        pending.rename(target)
        remember(root,stamp,target,manifest['archive_id'])
    return dict(path=str(target),bytes=target.stat().st_size,source_bytes=sum(e['bytes'] for e in entries.values()))
