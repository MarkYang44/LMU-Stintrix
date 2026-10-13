"""Shared class-position labels for text and both image renderers."""
from lap_identity import vehicle_class


def inline_positions(model):
    """Only new journals opt in; historical reports keep their original cards."""
    s=model['summary'];flag=s.get('finish_flag')
    place=lambda value:'P'+str(value) if value else '未知'
    start=place(s.get('grid_place'))
    finish={2:'DNF',3:'DQ'}.get(flag) or place(s.get('finish_place'))
    if s.get('position_display_version')!=1:return None,None
    start += ' / 同组 '+place(s.get('grid_class_place'))
    # Do not present a retired car's last observed rank as its finishing place.
    finish += ' / 同组 '+({2:'DNF',3:'DQ'}.get(flag) or place(s.get('finish_class_place')))
    return start,finish


def position(place,size=None):
    return ('P'+str(place)+('/'+str(size) if size else '')) if place else '未知'


def fields(model):
    summary=model['summary'];session=model['session']
    group=vehicle_class({**session,'vehicle_class':summary.get('vehicle_class') or session.get('vehicle_class')})
    grid=summary.get('grid_class_place')
    label='组内发车' if grid else '组内首次观测'
    start=position(grid or summary.get('start_class_place'),summary.get('grid_class_size') if grid else summary.get('start_class_size'))
    finish=position(summary.get('finish_class_place'),summary.get('class_size'))
    outcome={2:'DNF',3:'DQ'}.get(summary.get('finish_flag'))
    # A retired car's last observed position is not a finishing place.
    if outcome:finish=outcome+'（末次 '+finish+'）'
    return group,label,start,'组内结束名次',finish


def description(model):
    group,start_label,start,finish_label,finish=fields(model)
    return f'{group} · {start_label} {start} · {finish_label} {finish}'
