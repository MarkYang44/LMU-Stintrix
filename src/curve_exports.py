"""Reusable standalone curve pages; cache only filenames, never full telemetry."""
from pathlib import Path
from threading import RLock
import hashlib,json
from comparison_cache import stamps,asset_fingerprints

CURVE_REVISION=1  # Bump for Python payload/page semantics, independently of UI releases.
_lock=RLock()


def signature(entry):
    from paths import ASSETS,track_catalog_path
    from control_theme import T,web_script
    from i18n import language
    evo=entry['session'].get('simulator_id')=='ac_evo'
    assets=[ASSETS/('evo_compare.html' if evo else 'compare.html'),ASSETS/'interface_theme.js',ASSETS/'dataview.js']
    if not evo:assets.extend([ASSETS/'laplab.js',ASSETS/'trackview.js',ASSETS/'vehicleview.js',track_catalog_path(ASSETS)])
    return dict(format='stintrix.personal-curve',version=3,revision=CURVE_REVISION,record=stamps([entry['file']]),metadata=stamps([Path(entry['folder'])/'session.json']),session=dict(entry['session']),assets=asset_fingerprints(assets),
        simulator=entry['session'].get('simulator_id','lmu'),lap=entry['lap']['number'],time=entry['time_s'],theme=T.mode,theme_payload=hashlib.sha256(web_script(ASSETS).encode('utf-8')).hexdigest(),language=language)


def save(root,entry):
    from simulators import accepts
    from storage import atomic_json
    from paths import ASSETS
    from json_store import load
    from laps import write_compare
    root=Path(root).resolve();source=Path(entry['file']).resolve()
    if not source.is_relative_to(root) or not accepts(root,entry['session']):raise ValueError('只能打开当前游戏目录中的圈记录')
    with _lock:
        key=signature(entry);token=hashlib.sha256(json.dumps(key,sort_keys=True).encode()).hexdigest()[:24]
        folder=root/'PersonalRecords/History'
        if not folder.resolve().is_relative_to(root):raise ValueError('Curve output outside data directory')
        folder.mkdir(parents=True,exist_ok=True)
        page=folder/('Curve_'+token+'.html');receipt=page.with_suffix('.cache.json')
        if page.is_symlink() or receipt.is_symlink():raise ValueError('Linked curve output is not supported')
        try:
            value=json.loads(receipt.read_text('utf-8'))
            if value['signature']==key and value['output']==stamps([page]) and page.is_file():return str(page)
        except (OSError,ValueError,KeyError,TypeError):pass
        record=load(source)
        try:
            # A corrected session caption must not inherit stale metadata from an old lap export.
            record['session']={**record.get('session',{}),**entry['session']}
            if key['simulator']=='ac_evo':
                from evo_laps import write_curve
                write_curve(page,record,source)
            else:write_compare(page,ASSETS/'compare.html',[record])
        finally:
            close=getattr(record.get('data'),'close',None)
            if close:close()
        if signature(entry)!=key:raise OSError('圈记录或素材已变化，请重新打开')
        atomic_json(receipt,dict(signature=key,output=stamps([page])))
        return str(page)
