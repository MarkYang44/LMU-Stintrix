"""Small local HUD drafts: fixed-anchor matching, no media or file-content hashes."""
from pathlib import Path
import json,re,copy


def load(root):
    path=Path(root)/'video_preferences.json'
    try:
        if path.stat().st_size>32768:return []
        value=json.loads(path.read_text(encoding='utf8'))
        profiles=value.get('profiles',[]) if isinstance(value,dict) else []
        return [p for p in profiles if isinstance(p,dict)][:6] if isinstance(profiles,list) else []
    except (OSError,ValueError,TypeError):return []


def preview_box(box,image,media):
    return [round(v*image.size[i%2]/media[('width','height')[i%2]]) for i,v in enumerate(box)]


def match(profiles,image,media):
    from video_signal import arc_points,visible
    for profile in profiles:
        try:
            if profile['frame_size']!=[media['width'],media['height']]:continue
            x0,y0,x1,y1=profile['anchor']
            if not (0<=x0<x1<=media['width'] and 0<=y0<y1<=media['height']):continue
            for key in ('throttle','brake'):
                if any(not 0<=x<media['width'] or not 0<=y<media['height'] for group in arc_points(profile[key]) for x,y in group):raise ValueError('geometry')
            if len(profile['signature'])!=512:continue
            if visible(image,preview_box(profile['anchor'],image,media),profile['signature']):return copy.deepcopy(profile)
        except (KeyError,ValueError,TypeError,IndexError,OverflowError,ZeroDivisionError):continue
    return None


def remember(root,config,image,media):
    from video_signal import anchor_signature
    from storage import atomic_json
    profile={k:copy.deepcopy(config[k]) for k in ('frame_size','throttle','brake','anchor')}
    for key in ('distance_box','timer_box'):
        if key in config:profile[key]=copy.deepcopy(config[key])
    profile['signature']=anchor_signature(image,preview_box(profile['anchor'],image,media))
    profiles=[p for p in load(root) if p.get('frame_size')!=profile['frame_size'] or p.get('anchor')!=profile['anchor']]
    value=dict(version=1,profiles=[profile,*profiles][:6])
    while len(json.dumps(value,ensure_ascii=False,indent=2).encode('utf8'))>32768:value['profiles'].pop()
    atomic_json(Path(root)/'video_preferences.json',value)


def infer_identity(filename,choices):
    """Suggest only a unique recorded layout for a circuit explicitly named in the filename."""
    from track_names import NAMES,key
    name=Path(filename).stem.casefold();hits=set()
    for zh,aliases in NAMES:
        short=re.sub(r'(?:国家赛车场|国际赛道|赛车场|赛道)$','',zh)
        tokens=[zh,*aliases,*([short] if len(short)>=2 else [])]
        if any((token.casefold() in name if re.search('[\u4e00-\u9fff]',token) else
                re.search(r'(?<![a-z])'+re.escape(token.casefold())+r'(?![a-z])',name)) for token in tokens):
            hits.update(key(alias) for alias in aliases)
    matches=[label for label,identity in choices.items() if key(identity[0]) in hits]
    return matches[0] if len(matches)==1 else None
