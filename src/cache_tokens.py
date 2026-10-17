"""Persistent random IDs for provenance metadata; never hashes file content."""
from pathlib import Path
from uuid import uuid4
from storage import atomic_json
from cache_management import LOCK
import json


def token(root,kind,signature):
    path=Path(root)/'PersonalRecords/cache_tokens.json';path.parent.mkdir(parents=True,exist_ok=True)
    key=json.dumps([kind,signature],ensure_ascii=False,separators=(',',':'))
    with LOCK:
        try:values=json.loads(path.read_text(encoding='utf8'))
        except (OSError,ValueError):values={}
        if not isinstance(values,dict):values={}
        value=values.get(key)
        if isinstance(value,str) and len(value)==32 and all(c in '0123456789abcdef' for c in value):return value
        values[key]=uuid4().hex
        while len(values)>4096:values.pop(next(iter(values)))
        atomic_json(path,values);return values[key]
