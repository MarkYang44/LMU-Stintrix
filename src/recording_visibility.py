"""Persist HUD visibility independently of recording and telemetry preferences."""
from race_model import read_json
from storage import atomic_json


def load(path):
    value=read_json(path,{})
    return isinstance(value,dict) and value.get('silent_recording') is True


def save(path,enabled):
    atomic_json(path,dict(version=1,silent_recording=bool(enabled)))


def apply(app,enabled):
    """Do not replace the engine, recorder, or any panel enable preferences."""
    app.silent_recording=bool(enabled)
    if app.silent_recording:app.root.withdraw()
    else:app.root.deiconify()
    for name in ('vehicle_panels','endurance_panels'):
        panels=getattr(app,name,None)
        if panels is not None:panels.refresh_visibility()
