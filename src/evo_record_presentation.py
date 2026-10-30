"""Only observed EVO record facts; no inferred LMU conditions or identity edits."""
import math
from datetime import datetime,timezone
from i18n import tr
from track_names import display,layout_label

FIELDS=(('layout','布局 / 长度'),('samples','完整圈采样'),('timing','圈时来源'),
    ('track_temp','赛道温度'),('air_temp','气温'),('wetness','路面湿度'),('rain','降雨强度'),
    ('fuel','圈起点油量'),('front','前轮胎种'),('rear','后轮胎种'),('remaining','最低轮胎余量'),('assists','驾驶辅助'))


def known(value):
    text=str(value or '').strip()
    return bool(text) and text.casefold() not in ('unknown','none','null','n/a','—','-','未知','赛事类型未知') and not text.casefold().startswith(('unknown ·','unknown •'))


def finite(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def car(entry):
    session=entry['session'];vehicle=str(session.get('vehicle') or '').strip()
    group=str(session.get('vehicle_class') or entry.get('vehicle_class') or '').strip()
    parts=[]
    for value in (group,vehicle):
        if known(value) and value.casefold() not in [v.casefold() for v in parts]:parts.append(value)
    return ' · '.join(parts)


def present(entry,detail):
    from record_presentation import session_type,number,tire
    session=entry['session'];lap=entry['lap'];c=detail.get('conditions') or {};facts={}
    length=entry.get('length_m');layout=entry.get('layout')
    place=layout_label(entry['track'],layout) if known(layout) else ''
    distance=f'{length/1000:.3f} km' if finite(length) and length>0 else ''
    if place or distance:facts['layout']=' · '.join(v for v in (place,distance) if v)
    count=lap.get('sample_count')
    if isinstance(count,int) and not isinstance(count,bool) and count>0:facts['samples']=f'{count:,}'+tr(' 个采样')
    timing=lap.get('timing_source')
    if timing=='evo_last_laptime_ms':facts['timing']=tr('游戏毫秒计时')
    for key,source,unit in (('track_temp','track_temp_c',' °C'),('air_temp','ambient_temp_c',' °C'),('fuel','fuel_l',' L')):
        if finite(c.get(source)):facts[key]=number(c[source],unit)
    for key,source,zero in (('wetness','wetness','干燥'),('rain','rain','无雨')):
        value=c.get(source)
        if finite(value):facts[key]=tr(zero) if value==0 else number(value*100,' %',0)
    for key,axle,compound in (('front','front','tyre_compound'),('rear','rear','tyre_rear_compound')):
        name='tyre_'+axle+'_name';has_name=known(c.get(name))
        if has_name or finite(c.get(compound)):
            value=tire(c if has_name else {**c,name:''},axle)
            if known(value):facts[key]=value
    wear=[(detail.get('vehicle_summary') or {}).get(w+'_wear_fraction',{}).get('start') for w in ('fl','fr','rl','rr')]
    wear=[v for v in wear if finite(v) and 0<=v<=1]
    if wear:facts['remaining']=number(min(wear)*100,' %')
    assists=[name+' '+number(c[key],digits=0) for name,key in (('TC','tc_level'),('ABS','abs_level')) if finite(c.get(key))]
    if assists:facts['assists']=' / '.join(assists)
    context=[]
    if lap.get('number') is not None:context.append(tr('第 ')+str(lap['number'])+tr(' 圈'))
    try:
        when=datetime.fromisoformat(session.get('started_utc','').replace('Z','+00:00'));when=when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when
        context.append(when.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
    except (ValueError,TypeError,AttributeError):pass
    phase=session_type(session.get('session'))
    duration=entry['time_s']
    return dict(track=display(entry['track']),time=f'{int(duration//60)}:{duration%60:06.3f}',car=car(entry),
        context=' · '.join(context),session_type=phase if known(phase) else '',facts=facts)
