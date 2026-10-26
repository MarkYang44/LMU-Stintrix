"""Portable private archive choices; fast import is the menu default."""
import json
from pathlib import Path
from storage import atomic_json

def load(root):
    try:value=json.loads((Path(root)/'archive_settings.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):value={}
    if not isinstance(value,dict):value={}
    return dict(format=value.get('format') if value.get('format') in ('zip','7z') else 'zip',verify=False)
def save(root,format,verify):
    if format not in ('zip','7z'):raise ValueError('请选择 ZIP 或 7z')
    from preference_error import read_object
    path=Path(root)/'archive_settings.json';value=read_object(path);value.update(format=format,verify=False)
    atomic_json(path,value)
