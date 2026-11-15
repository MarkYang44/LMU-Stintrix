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


MODEL_IMAGE_ALIASES={
    'Ferrari 296 LMGT3 Evo':'Ferrari 296 LMGT3',
    'Ferrari 296 LMGT3 Evo (No BOP)':'Ferrari 296 LMGT3',
    'Chevrolet Corvette Z06 LMGT3.':'Corvette Z06 LMGT3.R',
    'Chevrolet Corvette Z06 LMGT3.R':'Corvette Z06 LMGT3.R',
    'Chevrolet Corvette Z06 GT3.R':'Corvette Z06 LMGT3.R',
    'Aston Martin Vantage AMR LMGT':'Aston Martin Vantage AMR LMGT3',
}


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


@lru_cache(maxsize=512)
def model_keys(vehicle):
    return tuple(dict.fromkeys(normalized(name) for name in (vehicle,image_model(vehicle) or '') if name))


def guide_car(vehicle):
    from guidebook import catalog
    from paths import ASSETS
    for wanted in model_keys(vehicle):
        for car in catalog()['cars'].values():
            if normalized(car['name'])!=wanted:continue
            path=(ASSETS/'guide'/car['image']).resolve()
            if path.is_relative_to((ASSETS/'guide/media').resolve()) and path.is_file():
                return car,path
    return None


def lmu_art(vehicle,root=None,renderer_cars=None):
    root=Path(root) if root is not None else data_directory()
    directories=[root/'assets/cars']
    if renderer_cars is not None:
        cars=Path(renderer_cars)
        directories.append(cars)
    else:
        from renderer_config import load
        config=load(root)
        if config['mode']=='racecom' and config['executable']:
            directories.append(Path(config['executable']).parent/'Source/Cars')
    for directory in directories:
        calibration=directory.parent.parent/'_customization/car_calibration.json' if directory.name=='Cars' and directory.parent.name=='Source' else None
        match=select_car(vehicle,directory,calibration)
        if match:
            try:
                stamp=match[0].stat()
                if readable_photo(match[0],stamp.st_size,stamp.st_mtime_ns,stamp.st_ctime_ns):return match
            except OSError:pass
    guide=guide_car(vehicle)
    return (guide[1],(0,0,1,1)) if guide else None


@lru_cache(maxsize=64)
def readable_photo(path,size,mtime,ctime):
    from PIL import Image
    try:
        with Image.open(path,formats=('JPEG','PNG','WEBP')) as image:image.verify()
        return True
    except (OSError,ValueError,SyntaxError,Image.DecompressionBombError):return False


def prepare_photo(art,target):
    """Stage a bounded, calibrated PNG for renderers that lack WebP support."""
    from PIL import Image
    path,bounds=art
    with Image.open(path,formats=('JPEG','PNG','WEBP')) as source:
        box=tuple(round(value*axis) for value,axis in zip(bounds,source.size*2))
        with source.crop(box) as photo:
            photo.thumbnail((1800,1200),Image.Resampling.LANCZOS)
            photo.convert('RGBA').save(target,format='PNG')


def select_car(vehicle, directory=None, calibration=None):
    directory=Path(directory or data_directory()/'assets'/'cars').resolve()
    try:catalog=json.loads(Path(calibration or directory/'car_calibration.json').read_text(encoding='utf-8-sig'))['cars']
    except (OSError,ValueError,KeyError,TypeError):return None
    if not isinstance(catalog,dict):return None
    for wanted in model_keys(vehicle):
        matches=[]
        for filename,entry in catalog.items():
            if not isinstance(entry,dict) or not isinstance(entry.get('aliases',[]),list):continue
            names=(Path(filename).stem,*entry.get('aliases',[]))
            if not any(wanted in model_keys(name) for name in names if isinstance(name,str)):continue
            path=(directory/filename).resolve()
            if not path.is_relative_to(directory) or path.suffix.casefold() not in ('.png','.jpg','.jpeg','.webp') or not path.is_file():continue
            bounds=entry.get('subject_bounds')
            if not isinstance(bounds,list) or len(bounds)!=4:continue
            if not all(isinstance(v,(int,float)) and math.isfinite(v) and 0<=v<=1 for v in bounds):continue
            l,t,r,b=bounds
            if not l<r or not t<b:continue
            # Leave breathing room around the calibrated whole vehicle, then fit
            # this rectangle into the card without distorting its aspect ratio.
            margin=.04
            matches.append((any(normalized(name)==wanted for name in names if isinstance(name,str)),path,
                (max(0,l-margin),max(0,t-margin),min(1,r+margin),min(1,b+margin))))
        exact=[match for match in matches if match[0]]
        preferred=exact or matches
        if len(preferred)==1:return preferred[0][1:]
        if preferred:return None
    return None
