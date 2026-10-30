"""Small, readable record summaries; full tire telemetry remains in the source."""
import math
from datetime import datetime,timezone
from i18n import tr
from track_names import display,layout


def session_type(value):
    from library import session_label
    known={'practice':'Practice','qualify':'Qualify','qualifying':'Qualify','race':'Race','warmup':'Warmup'}
    kind=known.get(str(value).strip().casefold(),session_label(value)) if not isinstance(value,bool) else 'Unknown'
    return tr({'Practice':'练习','Qualify':'排位','Race':'正赛','Warmup':'暖胎'}.get(kind,'赛事类型未知'))


def number(value,unit='',digits=1):
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):return tr('未知')
    return f'{value:.{digits}f}{unit}'


def tire(conditions,axle):
    name=conditions.get('tyre_'+axle+'_name')
    if name:
        return {'soft':tr('软胎'),'medium':tr('中性胎'),'hard':tr('硬胎'),'wet':tr('雨胎')}.get(str(name).lower(),str(name))
    index=conditions.get('tyre_compound' if axle=='front' else 'tyre_rear_compound')
    return tr('胎种编号 ')+number(index,digits=0) if isinstance(index,(int,float)) and math.isfinite(index) else tr('未知')


def present(entry,detail):
    if entry['session'].get('simulator_id')=='ac_evo':
        from evo_record_presentation import present as evo_present
        return evo_present(entry,detail)
    c=detail.get('conditions',{});session=entry['session'];lap=entry['lap'];duration=entry['time_s']
    try:
        when=datetime.fromisoformat(session.get('started_utc','').replace('Z','+00:00'))
        when=when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when
        date=when.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    except (ValueError,TypeError,AttributeError):date=tr('未知')
    wet=c.get('wetness');rain=c.get('rain')
    road=tr('干燥') if isinstance(wet,(int,float)) and math.isfinite(wet) and wet<=.01 else number(wet*100 if isinstance(wet,(int,float)) else None,' %',0)
    rain_label=tr('无雨') if rain==0 else number(rain*100 if isinstance(rain,(int,float)) else None,' %',0)
    remaining=[]
    for wheel in ('fl','fr','rl','rr'):
        value=detail.get('vehicle_summary',{}).get(wheel+'_wear_fraction',{}).get('start')
        if isinstance(value,(int,float)) and math.isfinite(value) and 0<=value<=1:remaining.append(value)
    return dict(track=display(entry['track']),time=f'{int(duration//60)}:{duration%60:06.3f}',
        car=' · '.join(v for v in (entry['vehicle_class'],str(session.get('vehicle',''))) if v),
        context=tr('第 ')+str(lap['number'])+tr(' 圈')+'   ·   '+date,session_type=session_type(session.get('session')),
        track_metrics={'layout':layout(entry['track'],entry['layout'],entry['length_m']),
            'track_temp':number(c.get('track_temp_c'),' °C'),'air_temp':number(c.get('ambient_temp_c'),' °C'),
            'wetness':road,'rain':rain_label},
        car_metrics={'fuel':number(c.get('fuel_l'),' L'),'front':tire(c,'front'),'rear':tire(c,'rear'),
            'remaining':number(min(remaining)*100 if remaining else None,' %'),
            'assists':'TC '+number(c.get('tc_level'),digits=0)+' / ABS '+number(c.get('abs_level'),digits=0)})
