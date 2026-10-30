"""Presentation-only circuit names; telemetry identities are never translated."""
import re,unicodedata
import i18n

NAMES=(
    ('巴林国际赛道',('Bahrain','Bahrain International Circuit','Sakhir')),
    ('巴塞罗那-加泰罗尼亚赛道',('Circuit de Barcelona-Catalunya','Barcelona','Barcelona Catalunya')),
    ('勒芒·萨尔特赛道',('Circuit de la Sarthe','Le Mans','Le Mans Circuit')),
    ('保罗·里卡尔赛道',('Circuit Paul Ricard','Paul Ricard')),
    ('美洲赛道',('Circuit of the Americas','COTA')),
    ('代托纳国际赛道',('Daytona International Speedway','Daytona')),
    ('富士赛车场',('Fuji Speedway','Fuji')),
    ('伊莫拉赛道',('Imola','Autodromo Enzo e Dino Ferrari')),
    ('英特拉格斯赛道',('Interlagos','Autódromo José Carlos Pace')),
    ('卢赛尔国际赛道',('Lusail International Circuit','Lusail','Losail International Circuit')),
    ('蒙扎国家赛车场',('Monza','Autodromo Nazionale Monza')),
    ('波尔蒂芒赛道',('Portimão','Portimao','Autódromo Internacional do Algarve','Algarve International Circuit','Algarve International','Algarve')),
    ('赛百灵国际赛道',('Sebring International Raceway','Sebring')),
    ('银石国际布局',('Silverstone International','Silverstone International Circuit')),
    ('银石赛道',('Silverstone','Silverstone Circuit','Silverstone Grand Prix')),
    ('斯帕-弗朗科尔尚赛道',('Spa-Francorchamps','Circuit de Spa-Francorchamps','Spa')),
    ('拉古纳塞卡赛道',('WeatherTech Raceway Laguna Seca','Laguna Seca')),
    ('亚特兰大之路赛道',('Road Atlanta','Michelin Raceway Road Atlanta')),
    ('长滩街道赛道',('Long Beach','Grand Prix of Long Beach')),
)


def key(name):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',str(name or '')).encode('ascii','ignore').decode().lower())


LOOKUP={key(alias):zh for zh,aliases in NAMES for alias in aliases}
_PREFIXES=tuple((key(alias),zh) for zh,aliases in NAMES for alias in aliases)


def display(name,language=None):
    original=str(name or '').strip()
    if (language or i18n.language)=='en':return original
    token=key(original);found=LOOKUP.get(token)
    if found:return found
    for prefix,zh in _PREFIXES:
        if prefix and token.startswith(prefix):return zh
    return original


def search_text(name):
    return str(name or '')+' '+display(name,'zh')


def layout(track,name,length):
    distance=f'{length/1000:.3f} km' if isinstance(length,(int,float)) and length>0 else i18n.tr('长度未知')
    label=layout_label(track,name)
    return label+' · '+distance


def layout_label(track,name):
    if not name:return i18n.tr('布局未记录')
    original=str(name).strip();variant=original
    if '无减速弯' in original:return i18n.tr('无减速弯布局')
    if '减速弯' in original:return i18n.tr('减速弯布局')
    for _,aliases in NAMES:
        for alias in sorted(aliases,key=len,reverse=True):
            if variant.casefold().startswith(alias.casefold()):
                variant=variant[len(alias):].strip(' -_()');break
        else:continue
        break
    token=key(variant)
    if 'monza' in key(track) and token in ('gp','grandprix','grandprixcircuit'):return i18n.tr('大奖赛布局（减速弯）')
    aliases={'gp':'大奖赛布局','grandprix':'大奖赛布局','grandprixcircuit':'大奖赛布局','short':'短布局','shortcircuit':'短布局',
        'international':'国际布局','national':'国家布局','endurance':'耐力布局','oval':'椭圆布局',
        'nochicane':'无减速弯布局','withoutchicane':'无减速弯布局','withchicane':'减速弯布局','chicane':'减速弯布局'}
    if token in aliases:return i18n.tr(aliases[token])
    if variant:return variant
    # A complete game layout name remains visible even when it equals the track.
    return display(original)
