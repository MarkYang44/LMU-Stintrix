"""Exact-model official artwork, downloaded explicitly into private local data."""
import json
import re
from functools import lru_cache
from pathlib import Path
from paths import ASSETS,data_directory
from race_art import normalized


@lru_cache(maxsize=1)
def catalog():return json.loads((ASSETS/'evo_art_sources.json').read_text('utf-8'))


def local_asset(entry,root=None):
    if not entry.get('file'):return None
    base=(Path(root or data_directory())/'assets/evo').resolve();path=(base/entry['file']).resolve()
    if not path.is_relative_to(base) or not path.is_file():return None
    return dict(entry,local_image=str(path))


def resources():
    value=catalog()
    return [e for e in [*value['cars'],*value['tracks'],*[c for t in value['tracks'] for c in t.get('configurations',[])],*value.get('branding',[])] if e.get('file') and e.get('url')]


def item(kind,name,layout='',root=None):
    wanted=normalized(name);layout_key=normalized(layout)
    values=catalog()[kind];exact=[]
    for entry in values:
        if wanted not in {normalized(v) for v in (entry['name'],*entry.get('aliases',[]))}:continue
        exact.append(entry)
    if kind=='tracks':
        specific=[e for e in exact if layout_key and layout_key in {normalized(v) for v in e.get('layouts',[])}]
        exact=specific or [e for e in exact if not e.get('layouts')]
    if not exact:return None
    value=dict(exact[0]);path=(Path(root or data_directory())/'assets/evo'/value['file']).resolve()
    base=(Path(root or data_directory())/'assets/evo').resolve()
    if not path.is_relative_to(base) or not path.is_file():return None
    value['local_image']=str(path);return value


def download(root,progress=None):
    """User-triggered only. No network calls from telemetry, pages or HUD draw."""
    import hashlib
    import urllib.request
    from concurrent.futures import ThreadPoolExecutor
    from storage import atomic_json
    from PIL import Image
    root=Path(root);base=root/'assets/evo';base.mkdir(parents=True,exist_ok=True)
    entries=resources()
    def fetch(entry):
        target=base/entry['file']
        if not target.resolve().is_relative_to(base.resolve()):raise ValueError('Invalid official asset target')
        raw=None
        if entry.get('type')=='svg':
            raw=base/entry['raw_file']
            if not raw.resolve().is_relative_to(base.resolve()):raise ValueError('Invalid official vector target')
            if not raw.exists():
                request=urllib.request.Request(entry['url'],headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(request,timeout=30) as response:data=response.read(2*1024*1024+1)
                if len(data)>2*1024*1024:raise ValueError('Official vector exceeds size limit')
                validate_svg(data);pending=raw.with_suffix('.pending')
                try:pending.write_bytes(data);pending.replace(raw)
                finally:pending.unlink(missing_ok=True)
            if not target.exists():
                import resvg_py
                data=raw.read_bytes();validate_svg(data);text=data.decode('utf-8-sig')
                if entry.get('light_logo'):text=text.replace('fill="#fff"','fill="#182232"')
                png=resvg_py.svg_to_bytes(svg_string=text,width=1000,skip_system_fonts=True)
                pending=target.with_suffix('.pending')
                try:pending.write_bytes(png);pending.replace(target)
                finally:pending.unlink(missing_ok=True)
        if target.exists():
            with Image.open(target) as image:image.verify()
        else:
            request=urllib.request.Request(entry['url'],headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(request,timeout=30) as response:data=response.read(12*1024*1024+1)
            if len(data)>12*1024*1024:raise ValueError('Official image exceeds size limit')
            pending=target.with_suffix('.pending')
            try:
                pending.write_bytes(data)
                with Image.open(pending) as image:image.verify()
                pending.replace(target)
            finally:pending.unlink(missing_ok=True)
        receipt=dict(file=entry['file'],url=entry['url'],source=entry.get('source',catalog()['source']),sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        if raw:receipt.update(raw_file=raw.name,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest())
        return receipt
    ok=[];errors=[]
    with ThreadPoolExecutor(max_workers=3,thread_name_prefix='EVO-official-art') as pool:
        futures=[(e,pool.submit(fetch,e)) for e in entries]
        for entry,future in futures:
            try:ok.append(future.result())
            except Exception as error:errors.append(dict(file=entry['file'],error=str(error)))
            if progress:progress(len(ok)+len(errors),len(entries))
    atomic_json(base/'sources.json',dict(source=catalog()['source'],downloaded=ok,errors=errors))
    return dict(downloaded=len(ok),errors=errors)


def validate_svg(data):
    """Only self-contained static official diagrams; no external resource reads."""
    import xml.etree.ElementTree as ET
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('External SVG declarations are unsupported')
    tree=ET.fromstring(data)
    for element in tree.iter():
        if element.tag.rsplit('}',1)[-1].lower() in ('script','image','foreignobject'):raise ValueError('External SVG content is unsupported')
        for key,value in element.attrib.items():
            if key.rsplit('}',1)[-1].lower() in ('href','src') and not value.startswith('#'):raise ValueError('External SVG resources are unsupported')
            for reference in re.findall(r'url\((.*?)\)',value,re.I):
                if not reference.strip(' \"\'').startswith('#'):raise ValueError('External SVG resources are unsupported')
        if element.tag.rsplit('}',1)[-1].lower()=='style' and element.text:
            if '@import' in element.text.lower():raise ValueError('External SVG styles are unsupported')
            for reference in re.findall(r'url\((.*?)\)',element.text,re.I):
                if not reference.strip(' \"\'').startswith('#'):raise ValueError('External SVG resources are unsupported')


def prepare_renderer(root,source):
    """Separate EVO resources with the user's existing, unchanged RaceCom engine.

    Immutable files may be hard-linked. Config, hooks, branding and artwork are
    independent copies; neither LMU resources nor original game files are edited.
    """
    import os,shutil
    from storage import atomic_json
    from PIL import Image,ImageDraw,ImageFont
    root=Path(root).resolve();source=Path(source).resolve();base=source.parent;target=root/'RaceComRenderer'
    target.mkdir(parents=True,exist_ok=True)
    same=target.resolve()==base
    if same:
        refresh_branding(root,target)
        return source
    for path in base.rglob('*'):
        if not path.is_file():continue
        rel=path.relative_to(base)
        if rel.parts[0] in ('Source','_customization') or path.name=='image_generate_config.json':continue
        out=target/rel
        if out.exists():continue
        out.parent.mkdir(parents=True,exist_ok=True)
        try:os.link(path,out)
        except OSError:shutil.copy2(path,out)
    for rel in ('_customization/racecom_hooks.py','image_generate_config.json'):
        out=target/rel
        if not out.exists():out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base/rel,out)
    for path in (base/'Source').rglob('*'):
        if not path.is_file() or 'Cars' in path.relative_to(base/'Source').parts or path.name=='LMU Logo.png':continue
        out=target/'Source'/path.relative_to(base/'Source')
        if not out.exists():out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,out)
    refresh_branding(root,target)
    cars=target/'Source/Cars';cars.mkdir(parents=True,exist_ok=True);calibration={}
    for entry in catalog()['cars']:
        art=root/'assets/evo'/entry['file']
        if not art.is_file():continue
        out=cars/entry['file']
        if not out.exists():shutil.copy2(art,out)
        calibration[entry['file']]=dict(aliases=[entry['name'],*entry.get('aliases',[])],subject_bounds=[0,0,1,1])
    calibration_path=target/'_customization/car_calibration.json';value=dict(cars=calibration)
    try:previous=json.loads(calibration_path.read_text('utf-8'))
    except (OSError,ValueError):previous=None
    if previous!=value:atomic_json(calibration_path,value)
    return target/source.name


def refresh_branding(root,target):
    """Promote the full official logo, retaining any previous local report mark."""
    import hashlib,shutil
    from storage import atomic_json
    logo=Path(target)/'Source/LMU Logo.png';logo.parent.mkdir(parents=True,exist_ok=True)
    official=Path(root)/'assets/evo/brand-evo-light.png'
    if official.is_file():
        wanted=hashlib.sha256(official.read_bytes()).hexdigest()
        if logo.is_file() and hashlib.sha256(logo.read_bytes()).hexdigest()==wanted:return
        if logo.is_file():
            prior=hashlib.sha256(logo.read_bytes()).hexdigest()[:16];backup=Path(target)/'_stintrix_branding_history';backup.mkdir(exist_ok=True)
            shutil.copy2(logo,backup/(prior+'.png'))
        shutil.copy2(official,logo)
        atomic_json(Path(target)/'_stintrix_branding.json',dict(version=2,sha256=wanted,source=catalog()['source']))
    elif not logo.exists():
        from PIL import Image,ImageDraw,ImageFont
        image=Image.new('RGBA',(1200,240));draw=ImageDraw.Draw(image)
        draw.polygon([(30,60),(55,60),(5,180),(0,180)],fill='#e52421')
        draw.text((85,38),'ASSETTO CORSA',font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',94),fill='#182232')
        draw.text((85,140),'E V O',font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',70),fill='#e52421');image.save(logo)
