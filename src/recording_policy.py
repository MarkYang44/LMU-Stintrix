"""Persistent opt-in practice recording; no file reads in the sampling loop."""
import json
from pathlib import Path
from storage import atomic_json


def load(root):
    try:
        value=json.loads((Path(root)/'recording_settings.json').read_text(encoding='utf-8'))
        return value.get('practice_enabled') is True
    except (OSError,ValueError,AttributeError):
        return False


def save(root,enabled):
    from preference_error import read_object
    path=Path(root)/'recording_settings.json';value=read_object(path);value.update(practice_enabled=bool(enabled));atomic_json(path,value)


def should_record(session,demo=False,practice_enabled=False):
    return bool(demo) or isinstance(session,int) and not isinstance(session,bool) and (
        5<=session<=8 or 10<=session<=13 or practice_enabled and 0<=session<=4)
