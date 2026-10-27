"""Simulator identity and process-scoped data roots; legacy records belong to LMU."""
import json
import os
from pathlib import Path

from simulator_profiles import PROFILES,profile,InputReader
GAMES={key:value.name for key,value in PROFILES.items()}
SHORT={key:value.short for key,value in PROFILES.items()}


def validate(value):
    return profile(value).id


def selected(base):
    override=os.environ.get('STINTRIX_SIMULATOR')
    if override:return validate(override)
    try:
        value=json.loads((Path(base)/'simulator_settings.json').read_text('utf-8-sig'))
        return validate(value.get('simulator','lmu'))
    except FileNotFoundError:return 'lmu'


def root_for(base,simulator):
    base=Path(base).resolve();validate(simulator)
    if simulator=='lmu':return base
    target=base/'Simulators'/'ac_evo'
    if any(p.is_symlink() or p.is_junction() for p in (target.parent,target)):
        raise ValueError('Simulator data directories must not be links')
    return target


def initialize(base,simulator):
    """First EVO launch copies presentation preferences only, never sessions/caches."""
    import shutil
    base=Path(base).resolve();root=root_for(base,simulator)
    if simulator=='lmu':return root
    root.mkdir(parents=True,exist_ok=True)
    marker=root/'.preferences-initialized'
    if not marker.exists():
        for name in ('interface_settings.json','settings.json','hud_layouts.json','hotkey_settings.json',
                     'recording_visibility.json','storage_settings.json','archive_settings.json'):
            source=base/name;target=root/name
            if source.is_file() and not source.is_symlink() and not target.exists():
                if name=='settings.json':
                    settings=json.loads(source.read_text('utf-8-sig'))
                    if not isinstance(settings,dict):raise ValueError('Sampling preferences must be an object')
                    settings.update(draw_mode='manual',draw_hz=60)
                    from storage import atomic_json
                    atomic_json(target,settings)
                else:shutil.copy2(source,target)
        if not (root/'settings.json').exists():
            from sampling import DEFAULTS,save_settings
            save_settings(root/'settings.json',dict(DEFAULTS,draw_mode='manual',draw_hz=60))
        marker.write_text('presentation preferences only\n',encoding='utf-8')
    return root


def identity(meta):
    """Untagged historical sessions are LMU, never implicitly EVO."""
    return meta.get('simulator_id','lmu')


def root_identity(root):
    root=Path(root).resolve()
    if root.name=='ac_evo' and root.parent.name=='Simulators':return 'ac_evo'
    return 'lmu'


def accepts(root,meta):
    return isinstance(meta,dict) and identity(meta)==root_identity(root)


def reader_factory(simulator) -> type[InputReader]:
    return profile(simulator).reader_type()


def launch(base,simulator):
    """Called after orderly GUI/worker shutdown. A fresh process cannot retain old roots."""
    import subprocess,sys
    from storage import atomic_json
    simulator=validate(simulator);base=Path(base).resolve()
    path=base/'simulator_settings.json'
    previous=path.read_bytes() if path.exists() else None
    atomic_json(path,dict(version=1,simulator=simulator))
    environment=dict(os.environ,STINTRIX_SIMULATOR=simulator,LMU_STINTRIX_DATA_DIR=str(base))
    environment.pop('LMU_STINTRIX_REPORT_WORKER',None)
    command=[sys.executable]
    if not getattr(sys,'frozen',False):command.append(str(Path(__file__).with_name('inputscope.py')))
    options={}
    if os.name=='nt':options['creationflags']=subprocess.CREATE_NO_WINDOW
    try:return subprocess.Popen(command,env=environment,**options)
    except OSError:
        if previous is None:path.unlink(missing_ok=True)
        else:path.write_bytes(previous)
        raise
