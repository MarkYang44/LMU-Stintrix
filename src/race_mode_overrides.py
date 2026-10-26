"""Explicit local participation corrections; original race evidence is untouched."""
import threading
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from preference_error import read_object
from storage import atomic_json

LOCK=threading.RLock()
COLLECTIONS=('Logs','ImportedLogs','RecoveredLogs')


def relative(root,folder):
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root):raise ValueError('请选择本机资料库中的赛事')
    key=folder.relative_to(root).as_posix();parts=PurePosixPath(key).parts
    if len(parts)!=2 or parts[0] not in COLLECTIONS:raise ValueError('请选择本机资料库中的赛事')
    return key


def load(root):
    path=Path(root)/'RaceModes/overrides.json'
    if not path.exists():return dict(version=1,entries={})
    if path.stat().st_size>1048576:raise ValueError('参赛方式修正文件过大，原文件已保留')
    value=read_object(path)
    if type(value.get('version')) is not int or value['version']!=1 or not isinstance(value.get('entries'),dict):raise ValueError('参赛方式修正文件无效，原文件已保留')
    seen=set()
    for key,entry in value['entries'].items():
        parts=key.replace('\\','/').split('/')
        if len(parts)!=2 or parts[0] not in COLLECTIONS or any(not p or p in ('.','..') or ':' in p for p in parts):raise ValueError('参赛方式修正路径无效，原文件已保留')
        if not isinstance(entry,dict) or entry.get('race_mode') not in ('online','single'):raise ValueError('参赛方式修正内容无效，原文件已保留')
        normalized=key.replace('\\','/').casefold()
        if normalized in seen:raise ValueError('参赛方式修正路径重复，原文件已保留')
        seen.add(normalized)
    return value


def apply(root,automatic):
    out=dict(automatic) if isinstance(automatic,dict) else {}
    for key,entry in load(root)['entries'].items():
        folder=Path(root)/key.replace('\\','/')
        relative(root,folder)
        out[str(folder.resolve())]=dict(race_mode=entry['race_mode'],race_mode_source='User confirmed',race_mode_manual=True,race_mode_confirmed_utc=entry.get('confirmed_utc',''))
    return out


def save(root,folders,kind,only_unknown=False):
    if kind not in ('online','single',None):raise ValueError('请选择线上、线下或自动识别')
    root=Path(root).resolve();keys=list(dict.fromkeys(relative(root,folder) for folder in folders))
    if not keys:raise ValueError('请先选择赛事')
    with LOCK:
        from race_mode import annotate,mode
        from race_model import read_json
        value=load(root);entries=value['entries'];now=datetime.now(timezone.utc).isoformat();changes=[]
        automatic=read_json(root/'RaceModes/index.json',{})
        modes=automatic.get('entries',{}) if isinstance(automatic,dict) else {}
        modes={k:v for k,v in modes.items() if isinstance(v,dict)} if isinstance(modes,dict) else {}
        for key,entry in entries.items():modes[str((root/key.replace('\\','/')).resolve())]=dict(race_mode=entry['race_mode'],race_mode_manual=True)
        for key in keys:
            path=root/key/'session.json';meta=read_object(path)
            if not path.is_file() or not meta:raise ValueError('赛事已移动或删除，请刷新记录')
            if only_unknown and mode(annotate(meta,path.parent,modes))!='unknown':continue
            if meta.get('status')=='recording':raise ValueError('请等待当前赛事停止记录后再更正')
            existing=next((old for old in entries if old.replace('\\','/').casefold()==key.casefold()),key)
            if (kind is None and existing not in entries) or (kind is not None and entries.get(existing,{}).get('race_mode')==kind):continue
            changes.append(existing)
        if not changes:return 0
        for existing in changes:
            if kind is None:entries.pop(existing,None)
            else:entries[existing]={**entries.get(existing,{}),**dict(race_mode=kind,confirmed_utc=now,source='user')}
        path=root/'RaceModes/overrides.json';path.parent.mkdir(parents=True,exist_ok=True);atomic_json(path,value)
    return len(changes)
