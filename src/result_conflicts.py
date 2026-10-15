"""Plain provenance rows; conflict display never chooses a replacement result."""
from i18n import tr
FIELDS={'grid_place':'总发车名次','grid_class_place':'同组发车名次','finish_place':'总完赛名次','finish_class_place':'同组完赛名次'}

def rows(entry):
    out=[]
    for key,values in (entry.get('position_conflicts') or {}).items():
        if key not in FIELDS or not isinstance(values,dict):continue
        fmt=lambda v:'P'+str(v) if isinstance(v,int) and not isinstance(v,bool) and 1<=v<=104 else tr('未知')
        out.append((key,(tr(FIELDS[key]),fmt(values.get('telemetry')),fmt(values.get('official')),tr('需要核对'))))
    return out

def provenance(entry):
    lines=[tr('官方结果时间（UTC）')+': '+str(entry.get('started_utc') or tr('未知')),tr('官方文件')+': '+str(entry.get('source_xml') or tr('未知')),tr('关联遥测')+': '+str(entry.get('linked_folder') or tr('无'))]
    if entry.get('linked_folder'):
        from pathlib import Path
        from race_model import read_json
        folder=Path(entry['linked_folder']);meta=read_json(folder/'session.json',{});summary=read_json(folder/'race_summary.json',{})
        lines.append(tr('遥测记录区间（UTC）')+': '+str(meta.get('started_utc') or tr('未知'))+' → '+str(meta.get('ended_utc') or tr('未知')))
        lines.append(tr('遥测终点名次为最后观测值；可能早于官方最终成绩。')+' / '+tr('完赛标记')+': '+str(summary.get('finish_flag',tr('未知'))))
    return '\n'.join(lines)
