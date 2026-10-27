"""Provenance receipts and immutable same-lap CSV links; no content comparisons."""
import json,os
from pathlib import Path


def signature(folder):
    from lap_cache_versions import signature as data_signature
    return data_signature(folder,'export')


def template_stamp(template):
    from paths import APP_ROOT
    paths=[APP_ROOT/'VERSION',*Path(template).parent.glob('*.js'),Path(template)] if template else [APP_ROOT/'VERSION']
    return [[str(p),p.stat().st_size,p.stat().st_mtime_ns] for p in paths if p.is_file()]


def cached(folder,numbers,template,individual=False):
    path=Path(folder)/'SelectedLaps/_exports.json'
    try:
        value=json.loads(path.read_text(encoding='utf8'));entry=value[('lap:' if individual else '')+'_'.join(map(str,numbers))]
        from lap_cache_versions import compatible
        if not compatible(entry['signature'],signature(folder)):return None
        # Individual JSON/CSV contains no presentation assets. Page exports
        # still depend on the current template, scripts and application version.
        if not (individual and template is None) and entry['template']!=template_stamp(template):return None
        for name,stamp in entry['outputs'].items():
            s=(path.parent/name).stat()
            if [s.st_size,s.st_mtime_ns]!=stamp:return None
        return entry['result']
    except (OSError,ValueError,KeyError,TypeError):return None


def remember(folder,numbers,template,result,individual=False):
    from storage import atomic_json
    path=Path(folder)/'SelectedLaps/_exports.json'
    try:value=json.loads(path.read_text(encoding='utf8'))
    except (OSError,ValueError):value={}
    files=[p for item in result['exports'] for p in (Path(item['json']),Path(item['csv']))]
    if result['comparison']:files.append(Path(result['comparison']))
    value[('lap:' if individual else '')+'_'.join(map(str,numbers))]=dict(signature=signature(folder),template=template_stamp(template),
        outputs={p.name:[p.stat().st_size,p.stat().st_mtime_ns] for p in files},result=result)
    atomic_json(path,value)


def link_fastest(folder,number,target):
    folder=Path(folder);source=folder/'fastest_lap.csv';target=Path(target)
    try:
        receipt=json.loads((folder/'_fastest_source.json').read_text(encoding='utf8'))
        from lap_cache_versions import compatible
        if not compatible(receipt['signature'],signature(folder)) or receipt['number']!=number or not source.is_file():return False
        from uuid import uuid4
        pending=target.with_name(target.name+'.'+uuid4().hex+'.pending')
        try:os.link(source,pending);pending.replace(target)
        finally:pending.unlink(missing_ok=True)
        return True
    except (OSError,ValueError,KeyError):return False
