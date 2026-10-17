"""Per-lap curve files and a lightweight index, keyed by metadata without hashing."""
import json
from functools import wraps
from telemetry_file import Path
from uuid import uuid4
from race_model import read_json
from storage import atomic_json
from cache_management import LOCK as _lock

def serialized(function):
    @wraps(function)
    def run(*args,**kwargs):
        with _lock:return function(*args,**kwargs)
    return run

def path(root,folder):
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root):raise ValueError('Training source outside data directory')
    signature=[]
    for name in ('inputs.csv','session.json','vehicle.csv','native_channels.json'):
        p=folder/name
        if p.is_file():s=p.stat();signature.append([name,s.st_size,s.st_mtime_ns])
    if not (folder/'inputs.csv').is_file():raise ValueError('Missing telemetry')
    base=root/'PersonalRecords/TrainingCache'
    with _lock:
        base.mkdir(parents=True,exist_ok=True)
        index=base/'sources.json';value=read_json(index,{});key=folder.relative_to(root).as_posix();old=value.get(key,{})
        if old.get('signature')!=signature or old.get('version')!=6:
            value[key]=dict(version=6,signature=signature,token=uuid4().hex);atomic_json(index,value)
        token=value[key]['token']
        if len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('Invalid training cache identifier')
    return base/token/'profiles.json'

class Laps:
    def __init__(self,base,headers):
        self.base=base.resolve();self.headers=headers
        from cache_budget import hold,touch
        hold(self,self.base);touch(self.base)
    def __len__(self):return len(self.headers)
    def __iter__(self):return self.selected()
    def selected(self,numbers=None):
        for header in self.headers:
            if numbers is not None and header['number'] not in numbers:continue
            path=(self.base/header['file']).resolve()
            if not path.is_relative_to(self.base):raise ValueError('Invalid cached lap path')
            with _lock:
                with path.open(encoding='utf-8') as stream:lap=json.load(stream)
            yield lap

def read(path):
    value=read_json(path,{})
    return dict(value,laps=Laps(path.parent,value.get('laps',[])))
