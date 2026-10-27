"""Portable assets and private local data; game discovery is read-only."""
import json
import os
from pathlib import Path
import re
import sys

APP_ROOT=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
ASSETS=Path(getattr(sys,'_MEIPASS',APP_ROOT))/'src' if getattr(sys,'frozen',False) else Path(__file__).resolve().parent

def app_version():
    if getattr(sys,'frozen',False):
        try:return json.loads((ASSETS/'build-version.json').read_text('utf-8'))['version']
        except (OSError,ValueError,KeyError,TypeError):pass
    try:return (APP_ROOT/'VERSION').read_text('utf-8').strip()
    except OSError:return '?'

def local_settings():
    try:return json.loads((APP_ROOT/'local_settings.json').read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return {}

def base_data_directory():
    from legacy_identity import DATA_ENV
    configured=os.environ.get('LMU_STINTRIX_DATA_DIR') or os.environ.get(DATA_ENV) or local_settings().get('data_directory')
    path=Path(configured).expanduser() if configured else APP_ROOT/'data'
    return (path if path.is_absolute() else APP_ROOT/path).resolve()

def data_directory():
    base=base_data_directory()
    # Workers receive an already scoped root, independently of the launcher selection.
    if os.environ.get('LMU_STINTRIX_REPORT_WORKER')=='1':return base
    from simulators import root_for,selected
    return root_for(base,selected(base))

def track_catalog_path(assets=None):
    """Private legacy maps override the public catalog only at runtime."""
    private=data_directory()/'assets'/'tracks'/'catalog.json'
    return private if private.is_file() else Path(assets or ASSETS)/'tracks'/'catalog.json'

def discover_game(simulator='lmu'):
    from simulators import GAMES,validate
    validate(simulator);settings=local_settings();directories=settings.get('game_directories',{})
    specified=(directories.get(simulator) if isinstance(directories,dict) else None) or (settings.get('game_directory') if simulator=='lmu' else None)
    if specified and Path(specified).is_dir():return Path(specified)
    roots=[]
    if sys.platform=='win32':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
                roots.append(Path(winreg.QueryValueEx(key,'SteamPath')[0]))
        except OSError:pass
    roots.extend(Path(os.environ.get(k,'C:/Program Files (x86)'))/'Steam' for k in ('ProgramFiles(x86)','ProgramFiles'))
    libraries=list(roots)
    for root in roots:
        try:
            vdf=(root/'steamapps'/'libraryfolders.vdf').read_text(encoding='utf-8')
            libraries.extend(Path(v.replace('\\\\','\\')) for v in re.findall(r'"path"\s*"([^"]+)"',vdf))
        except OSError:pass
    for library in libraries:
        candidate=library/'steamapps'/'common'/('Le Mans Ultimate' if simulator=='lmu' else 'Assetto Corsa EVO')
        if candidate.is_dir():return candidate
    return None

def telemetry_directory():
    game=discover_game()
    candidate=game/'UserData'/'Telemetry' if game else None
    return candidate if candidate and candidate.is_dir() else data_directory()/'ImportedLogs'
