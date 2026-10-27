"""One private completed-session pointer; never scan all races or rewrite sources."""
from pathlib import Path
import time
import os,threading
from race_model import read_json
from storage import atomic_json


def checked(root,folder):
    if not folder or not isinstance(folder,(str,os.PathLike)):return None
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root) or folder==root:return None
    parts=folder.relative_to(root).parts
    if not parts or parts[0] not in ('Logs','ImportedLogs','RecoveredLogs'):return None
    meta=read_json(folder/'session.json',{})
    from simulators import accepts
    if not accepts(root,meta):return None
    if not isinstance(meta,dict) or meta.get('status')!='complete' or 'demo' in str(meta.get('source','')).lower():return None
    return folder,meta


def remember(root,folder):
    result=checked(root,folder)
    if result:
        path,meta=result;atomic_json(Path(root)/'recent_session.json',dict(version=1,folder=path.relative_to(Path(root).resolve()).as_posix()))
    return result


class RecentSession:
    def __init__(self,root):
        self.root=Path(root);self.folder=None;self.meta={};self.seen=None;self.signature=None;self.value=None;self.probe_at=0;self.artifacts=()
        self.write_lock=threading.Lock()
        pointer=read_json(self.root/'recent_session.json',{})
        if isinstance(pointer,dict) and pointer.get('version')==1:
            result=checked(self.root,self.root/str(pointer.get('folder','')))
            if result:self.folder,self.meta=result
    def adopt(self,entries):
        if self.folder is not None:return
        for entry in sorted(entries,key=lambda e:str(e.get('date') or ''),reverse=True):
            try:result=remember(self.root,entry.get('folder'))
            except OSError:result=checked(self.root,entry.get('folder'))
            if result:self.folder,self.meta=result;self.signature=None;break
    def observe(self,hud,submit=None):
        folder=getattr(hud.engine,'last_folder',None) if hud is not None else None
        if folder and str(folder)!=self.seen:
            self.seen=key=str(folder)
            def work():
                with self.write_lock:
                    if self.seen!=key:return None
                    try:result=remember(self.root,folder)
                    except OSError:result=checked(self.root,folder)
                    if result:
                        from report_state import current
                        current(result[0])
                    return result
            def done(result,error):
                if self.seen==key and result:self.folder,self.meta=result;self.signature=None
            if submit:submit(work,done)
            else:done(work(),None)
    def state(self):
        if self.folder is None:return dict(folder=None,text='记录完成后，可在这里直接复盘',review=False,laps=False,note=False)
        now=time.monotonic()
        if now>=self.probe_at:
            self.probe_at=now+1;self.artifacts=(self.folder.is_dir(),(self.folder/'review.html').is_file(),(self.folder/'圈速单.png').is_file())
            if not self.artifacts[0]:
                self.folder=None;self.signature=None;return self.state()
        from report_state import latest,current
        receipt=latest(self.folder)
        if receipt is None:receipt=current(self.folder)
        signature=(str(self.folder),receipt.get('updated_utc'),receipt.get('state'),str(receipt.get('steps')),self.artifacts)
        if signature==self.signature:return self.value
        self.signature=signature;steps=receipt.get('steps',{})
        ready=lambda step,name:steps.get(step,{}).get('state')=='ready' and (self.folder/name).is_file()
        status='赛事已保存，报告正在生成' if receipt.get('state') in ('building','queued','deferred') else '赛事与报告已保存' if receipt.get('state')=='ready' else '赛事已保存，部分报告待完成'
        self.value=dict(folder=self.folder,text=' · '.join(str(self.meta.get(k,'')) for k in ('track','vehicle','ended_utc')),status=status,
            review=ready('review','review.html'),laps=ready('images','圈速单.png'),note=self.folder.is_dir())
        return self.value
