"""Small metadata-only scan cache and provenance for reusable comparison pages."""
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from pathlib import Path
from threading import RLock
import json

_lock=RLock();_scans=OrderedDict();_pending={}


def stamps(paths):
    result=[]
    for path in paths:
        path=Path(path).resolve()
        try:s=path.stat();value=[s.st_size,s.st_mtime_ns,s.st_ino]
        except FileNotFoundError:value=None
        result.append([str(path),value])
    return result


def source(folder):
    return stamps(Path(folder)/name for name in ('session.json','inputs.csv','inputs.csv.stc','vehicle.csv','vehicle.csv.stc','native_channels.json'))


def scan(folder,reader,*,namespace='lmu',files=(),limit=16,max_file_bytes=None):
    """Coalesce A/B reads; retain only up to 16 small lap inventories, no samples."""
    files=tuple(files);signature=source(folder);key=repr((namespace,signature,stamps(files)))
    with _lock:
        if key in _scans:
            value=_scans.pop(key);_scans[key]=value;return deepcopy(value)
        future=_pending.get(key);owner=future is None
        if owner:future=Future();_pending[key]=future
    if not owner:return deepcopy(future.result())
    try:
        value=reader()
        if source(folder)!=signature:raise OSError('赛事数据已变化，请重新选择并重试')
        with _lock:
            # A reader may publish its derived index. Track its final identity.
            final_files=stamps(files)
            if max_file_bytes is None or sum(s[0] for _,s in final_files if s is not None)<=max_file_bytes:
                _scans[repr((namespace,signature,final_files))]=deepcopy(value)
            while len(_scans)>limit:_scans.popitem(last=False)
        future.set_result(value);return deepcopy(value)
    except BaseException as error:future.set_exception(error);raise
    finally:
        with _lock:_pending.pop(key,None)


class Pair:
    def __init__(self,root,identities,template,page):
        self.root=Path(root).resolve();self.identities=identities;self.template=Path(template);self.page=Path(page);self.receipt=self.page.with_suffix('.cache.json');self.signature=self.current()
    def current(self):
        from paths import app_version,track_catalog_path,data_directory
        from control_theme import T
        from i18n import language
        assets=self.template.parent
        return dict(version=1,app=app_version(),selections=[[str(f),n] for f,n in self.identities],
            sources=[source(f) for f,_ in self.identities],theme=T.mode,language=language,
            assets=stamps([self.template,*sorted(assets.glob('*.js')),track_catalog_path(assets),data_directory()/'interface_settings.json']))
    def read(self):
        try:
            value=json.loads(self.receipt.read_text('utf-8'));result=value['result']
            if value['signature']!=self.signature or result['comparison']!=str(self.page) or len(result['exports'])!=2:return None
            paths=[self.page,*[Path(item[k]) for item in result['exports'] for k in ('json','csv')]]
            if any(not p.resolve().is_relative_to(self.root) for p in paths):return None
            if stamps(paths)!=value['outputs']:return None
            return result
        except (OSError,ValueError,KeyError,TypeError,AttributeError):return None
    def save(self,result):
        if self.current()!=self.signature:raise OSError('赛事数据已变化，请重新选择并重试')
        from storage import atomic_json
        paths=[self.page,*[Path(item[k]) for item in result['exports'] for k in ('json','csv')]]
        atomic_json(self.receipt,dict(signature=self.signature,outputs=stamps(paths),result=result))
