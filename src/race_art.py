"""Optional, private car artwork. No third-party artwork ships with Stintrix."""
import json
import math
from pathlib import Path
import re
from functools import lru_cache
from paths import data_directory


def normalized(value):
    value=str(value)
    return _short_normalized(value) if len(value)<=256 else _normalize(value)


def _normalize(value):return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', value.casefold())


@lru_cache(maxsize=512)
def _short_normalized(value):return _normalize(value)


MODEL_IMAGE_ALIASES={'Ferrari 296 LMGT3 Evo':'Ferrari 296 LMGT3','Ferrari 296 LMGT3 Evo (No BOP)':'Ferrari 296 LMGT3'}


def image_model(vehicle):
    wanted=normalized(vehicle)
    return next((base for alias,base in MODEL_IMAGE_ALIASES.items() if normalized(alias)==wanted),None)


def prepare_renderer_aliases(calibration,directory):
    """Add only known image aliases, preserving private calibration and its first backup."""
    calibration=Path(calibration);directory=Path(directory).resolve()
    if not calibration.is_file():return 0
    if calibration.is_symlink() or calibration.stat().st_size>2*1024*1024:raise ValueError('车辆图片校准文件无法安全更新，原文件已保留')
    blob=calibration.read_bytes();value=json.loads(blob.decode('utf-8-sig'));cars=value.get('cars')
    if not isinstance(cars,dict):raise ValueError('车辆图片校准文件格式无效，原文件已保留')
    occupied={}
    for filename,entry in cars.items():
        if not isinstance(entry,dict) or not isinstance(entry.get('aliases',[]),list):raise ValueError('车辆图片别名格式无效，原文件已保留')
        for name in (Path(filename).stem,*entry.get('aliases',[])):occupied.setdefault(normalized(name),set()).add(filename)
    changed=0
    for alias,base in MODEL_IMAGE_ALIASES.items():
        if normalized(alias) in occupied:continue
        owners=occupied.get(normalized(base),set())
        if len(owners)!=1:continue
        filename=next(iter(owners));path=(directory/filename).resolve()
        if not path.is_relative_to(directory) or not path.is_file():continue
        cars[filename].setdefault('aliases',[]).append(alias);occupied[normalized(alias)]={filename};changed+=1
    if not changed:return 0
    if calibration.read_bytes()!=blob:raise OSError('车辆图片校准文件已变化，请重试')
    backup=calibration.with_name(calibration.stem+'.stintrix-aliases-v1.backup.json')
    try:
        with backup.open('xb') as stream:stream.write(blob)
    except FileExistsError:pass
    from storage import atomic_json
    atomic_json(calibration,value);return changed


def select_car(vehicle, directory=None):
    directory=Path(directory or data_directory()/'assets'/'cars').resolve()
    try:catalog=json.loads((directory/'car_calibration.json').read_text(encoding='utf-8-sig'))['cars']
    except (OSError,ValueError,KeyError,TypeError):return None
    wanted=normalized(vehicle)
    if not wanted:return None
    # Prefer an exact calibration; only these explicitly known models may use a same-series image.
    candidates=[wanted];base=image_model(vehicle)
    if base:candidates.append(normalized(base))
    for wanted in candidates:
        for filename,entry in catalog.items():
            # Match a model/explicit alias. A brand match could show the wrong car.
            if wanted not in {normalized(Path(filename).stem),*[normalized(v) for v in entry.get('aliases',[])]}:continue
            path=(directory/filename).resolve()
            if not path.is_relative_to(directory) or not path.is_file():continue
            bounds=entry.get('subject_bounds')
            if not isinstance(bounds,list) or len(bounds)!=4:continue
            if not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in bounds):continue
            l,t,r,b=bounds
            if not l<r or not t<b:continue
            # Leave breathing room around the calibrated whole vehicle, then fit
            # this rectangle into the card without distorting its aspect ratio.
            margin=.04
            return path,(max(0,l-margin),max(0,t-margin),min(1,r+margin),min(1,b+margin))
    return None
