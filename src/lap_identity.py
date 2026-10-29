"""Conservative circuit-layout identity and explicit vehicle class grouping."""
import math


def text(value):
    return str(value or '').strip().casefold()


def same_layout(a, b):
    sa, sb = a['session'], b['session']
    if sa.get('simulator_id','lmu')!=sb.get('simulator_id','lmu'):return False
    if not text(sa.get('track')) or text(sa.get('track')) != text(sb.get('track')):
        return False
    la, lb = text(sa.get('track_layout')), text(sb.get('track_layout'))
    if la and lb and la != lb:
        return False
    try:
        x, y = float(a['lap']['track_length_m']), float(b['lap']['track_length_m'])
        return all(math.isfinite(v) and v > 100 for v in (x, y)) and abs(x-y) <= 1
    except (ValueError, TypeError, KeyError):
        return False


def vehicle_class(session):
    explicit = canonical_class(session.get('vehicle_class'))
    if explicit:
        return explicit
    name = text(session.get('vehicle'))
    for token, label in (('lmgt3', 'LMGT3'), ('lmp2', 'LMP2'), ('gte', 'GTE'), ('hypercar', 'Hypercar')):
        if token in name:
            return label
    import re
    normalized=re.sub(r'[^a-z0-9]','',name)
    matches=[group for car,group in catalog_classes() if car and car in normalized]
    if matches and len(set(matches))==1:
        return matches[0]
    # Unknown cars stay separate instead of being assigned a guessed class.
    return 'Unknown · ' + str(session.get('vehicle') or 'Unknown')


def performance_variant(session):
    """Only explicit evidence separates unrestricted laps; never infer from pace/date."""
    import re
    if text(session.get('vehicle_variant'))=='no_bop':return 'no_bop'
    return 'no_bop' if re.search(r'\(\s*no[\s_-]*bop\s*\)\s*$',str(session.get('vehicle') or ''),re.I) else ''


def canonical_class(value):
    """LMU scoring uses GT3 while older model-based records use LMGT3."""
    import re
    original=str(value or '').strip()
    key=re.sub(r'[^a-z0-9]','',original.casefold())
    return {'gt3':'LMGT3','lmgt3':'LMGT3','gte':'GTE','lmgte':'GTE',
            'lmp2':'LMP2','hypercar':'Hypercar','lmh':'Hypercar','lmdh':'Hypercar'}.get(key,original)


from functools import lru_cache


@lru_cache(maxsize=1)
def catalog_classes():
    import json
    from paths import ASSETS
    try:
        data=json.loads((ASSETS/'guide/catalog.json').read_text(encoding='utf-8'))
        import re
        return [(re.sub(r'[^a-z0-9]','',text(car['name'])),car['car_class']) for car in data['cars'].values()]
    except (OSError,ValueError,KeyError,TypeError):
        return []
