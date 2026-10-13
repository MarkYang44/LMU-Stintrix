"""Two independently chosen verified laps, across or within local sessions."""
from pathlib import Path
import hashlib
from json_store import load
from laps import complete_laps,finished_metadata,export_selected_laps,write_compare
from lap_identity import same_layout


def valid_laps(folder):
    scan=complete_laps(folder)
    return [v for v in scan['laps'] if v.get('validity')=='verified'
            and not v.get('lap_invalidated') and not v.get('in_pits')]


def validate_pair(selections):
    if len(selections)!=2:
        raise ValueError('请选择圈 A 和圈 B')
    identities=[];headers=[]
    for folder,number in selections:
        folder=Path(folder).resolve()
        if type(number) is not int:
            raise ValueError('请选择有效圈号')
        meta=finished_metadata(folder)
        lap=next((v for v in valid_laps(folder) if v['number']==number),None)
        if lap is None:
            raise ValueError(f'第 {number} 圈不是已验证的有效完整圈')
        headers.append(dict(session=meta,lap=lap))
        identities.append((folder,number))
    if identities[0]==identities[1]:
        raise ValueError('圈 A 和圈 B 必须选择不同圈')
    if not same_layout(*headers):
        raise ValueError('请选择同一赛道、同一布局的两圈；缺少可靠长度时无法确认布局')
    return identities


def export_pair(root,selections,template):
    root=Path(root).resolve()
    if not isinstance(selections,(list,tuple)) or len(selections)!=2:
        raise ValueError('请选择圈 A 和圈 B')
    if any(not Path(folder).resolve().is_relative_to(root) for folder,_ in selections):
        raise ValueError('只能选择本插件目录中的比赛记录')
    identities=validate_pair(selections)  # Validate both before creating outputs.
    records=[];exports=[]
    for folder,number in identities:
        item=export_selected_laps(folder,[number])['exports'][0]
        value=load(item['json'])
        # Identical folder names in separate import roots must not collide in JS.
        value['id']=hashlib.sha256(str(folder).encode()).hexdigest()[:16]+':'+str(number)
        records.append(value);exports.append(item)
    output=root/'LapComparisons';output.mkdir(exist_ok=True)
    key=hashlib.sha256(repr(identities).encode()).hexdigest()[:16]
    page=output/('Compare_'+key+'.html')
    write_compare(page,template,records,'selected_valid_laps',reference_id=records[0]['id'])
    return dict(folder=str(output),exports=exports,comparison=str(page))
