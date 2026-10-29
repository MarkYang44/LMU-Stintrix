"""Small metadata-only scan cache and provenance for reusable comparison pages."""
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
from pathlib import Path
from threading import RLock
import json
import hashlib

_lock=RLock();_scans=OrderedDict();_pending={};_asset_hashes=OrderedDict()


def asset_fingerprints(paths):
    """Static renderer bytes survive packaging timestamps; retain 64 digests only."""
    result=[]
    def identity(path):
        s=path.stat();return s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_ino
    for value in paths:
        path=Path(value).resolve();key=str(path)
        try:signature=identity(path)
        except FileNotFoundError:result.append([key,None]);continue
        with _lock:
            cached=_asset_hashes.pop(key,None)
            if cached is not None:_asset_hashes[key]=cached
        if cached is not None and cached[0]==signature:digest=cached[1]
        else:
            hashed=hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(65536),b''):hashed.update(block)
            if identity(path)!=signature:raise OSError('页面资源已变化，请重试')
            digest=hashed.hexdigest()
            with _lock:
                _asset_hashes[key]=(signature,digest)
                while len(_asset_hashes)>64:_asset_hashes.popitem(last=False)
        result.append([key,digest])
    return result


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


VIEW_REVISION=1  # Bump for Python page/payload semantics; assets are stamped below.
LEGACY_VIEW_APPS=('0.3.27',)  # Complete LMU/EVO pair output equivalence verified.


def view_compatible(saved,expected):
    if saved==expected:return True
    if not isinstance(saved,dict) or set(saved)!={'version','app','selections','sources','theme','language','assets'}:return False
    # Admit only the audited previous envelope, retaining every source, asset,
    # theme and language check. Read-only: do not rewrite historical receipts.
    revision=1 if expected.get('simulator')=='lmu' else 2
    return (expected.get('format')=='stintrix.lap-view' and expected.get('simulator') in ('lmu','ac_evo')
        and saved['version']==1 and saved['app'] in LEGACY_VIEW_APPS and len(expected.get('selections',()))==2
        and expected.get('version')==2 and expected.get('revision')==1 and expected.get('selection_revision')==revision
        and {k:v for k,v in saved.items() if k not in ('version','app')}==
            {k:v for k,v in expected.items() if k not in ('format','version','revision','selection_revision','simulator')})


class View:
    def __init__(self,root,identities,template,page):
        self.root=Path(root).resolve();self.identities=identities;self.template=Path(template);self.page=Path(page);self.receipt=self.page.with_suffix('.cache.json');self.signature=self.current()
    def asset_paths(self):
        from paths import track_catalog_path,data_directory
        assets=self.template.parent
        return [self.template,*sorted(assets.glob('*.js')),track_catalog_path(assets),data_directory()/'interface_settings.json']
    def current(self):
        from simulators import root_identity
        from lap_cache_versions import REVISION
        from control_theme import T
        from i18n import language
        simulator=root_identity(self.root);revision=REVISION
        if simulator=='ac_evo':
            from evo_laps import VERSION
            revision=VERSION
        sources={folder:source(folder) for folder in dict.fromkeys(f for f,_ in self.identities)}
        return dict(format='stintrix.lap-view',version=2,revision=VIEW_REVISION,selection_revision=revision,simulator=simulator,selections=[[str(f),n] for f,n in self.identities],
            sources=[sources[f] for f,_ in self.identities],theme=T.mode,language=language,
            assets=asset_fingerprints(self.asset_paths()))
    def read(self):
        try:
            value=json.loads(self.receipt.read_text('utf-8'));result=value['result']
            expected=self.signature
            if value['signature'].get('version')==1:expected={**expected,'assets':stamps(self.asset_paths())}
            if not view_compatible(value['signature'],expected) or result['comparison']!=str(self.page) or len(result['exports'])!=len(self.identities):return None
            if [item['number'] for item in result['exports']]!=[n for _,n in self.identities]:return None
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


Pair=View
