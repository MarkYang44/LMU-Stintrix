"""Two independently chosen verified laps, across or within local sessions."""
from pathlib import Path
import hashlib
from json_store import load
from laps import complete_laps,finished_metadata,export_selected_laps,write_compare
from lap_identity import same_layout


def valid_laps(folder):
    if finished_metadata(folder).get('simulator_id')=='ac_evo':
        from evo_comparison import valid_laps as evo_valid
        return evo_valid(folder)
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


def _cached_lap(folder,number):
    from lap_exports import cached
    result=cached(folder,[number],None,individual=True)
    if not result:return None
    try:
        item,=result['exports']
        if item['number']!=number or any(Path(item[k]).resolve().parent!=folder/'SelectedLaps' for k in ('json','csv')):return None
        value=load(item['json'])
        if value['lap']['number']!=number or value.get('reference_kind')!='selected':return None
        from lap_scan_index import load as scan_index
        index=scan_index(folder)
        if index is None:return None
        # Compatibility uses the original unrounded length, just like extraction.
        lap=next(v for v in index['inventory']['laps'] if v['number']==number)
        return item,value,dict(session=finished_metadata(folder),lap=lap)
    except (OSError,ValueError,TypeError,KeyError,StopIteration):return None


def export_pair(root,selections,template):
    root=Path(root).resolve()
    if not isinstance(selections,(list,tuple)) or len(selections)!=2:
        raise ValueError('请选择圈 A 和圈 B')
    if any(not Path(folder).resolve().is_relative_to(root) for folder,_ in selections):
        raise ValueError('只能选择本插件目录中的比赛记录')
    identities=[(Path(folder).resolve(),number) for folder,number in selections]
    if any(type(number) is not int or number<0 for _,number in identities):raise ValueError('请选择有效圈号')
    if identities[0]==identities[1]:raise ValueError('圈 A 和圈 B 必须选择不同圈')
    metadata=[finished_metadata(folder) for folder,_ in identities]
    from simulators import accepts
    if any(not accepts(root,meta) for meta in metadata):raise ValueError('只能对比当前游戏的赛事记录')
    if any(meta.get('simulator_id')=='ac_evo' for meta in metadata):
        from evo_comparison import export_pair as evo_pair
        return evo_pair(root,identities)
    output=root/'LapComparisons';key=hashlib.sha256(repr(identities).encode()).hexdigest()[:16];page=output/('Compare_'+key+'.html')
    from comparison_cache import Pair
    cache=Pair(root,identities,template,page);existing=cache.read()
    if existing:return existing
    # Read each source once, retaining both chosen laps for validation and export.
    from laps import _select_laps,_export_laps
    groups={};prepared={};headers=[];generated={};reused_headers={}
    for folder,number in identities:
        reused=_cached_lap(folder,number)
        if reused:generated[folder,number]=reused[:2];reused_headers[folder,number]=reused[2]
        else:groups.setdefault(folder,[]).append(number)
    for folder,numbers in groups.items():prepared[folder]=_select_laps(folder,numbers)
    for folder,number in identities:
        if (folder,number) in generated:
            header=reused_headers[folder,number];meta,lap=header['session'],header['lap']
        else:meta,selected=prepared[folder];lap=selected[number]
        if lap.get('validity')!='verified' or lap.get('lap_invalidated') or lap.get('in_pits'):raise ValueError(f'第 {number} 圈不是已验证的有效完整圈')
        headers.append(dict(session=meta,lap=lap))
    if not same_layout(*headers):raise ValueError('请选择同一赛道、同一布局的两圈；缺少可靠长度时无法确认布局')
    for folder,numbers in groups.items():
        result,values=_export_laps(folder,numbers,*prepared[folder])
        generated.update({(folder,n):(item,value) for n,item,value in zip(numbers,result['exports'],values)})
    records=[];exports=[]
    for folder,number in identities:
        item,value=generated[folder,number]
        # Identical folder names in separate import roots must not collide in JS.
        value['id']=hashlib.sha256(str(folder).encode()).hexdigest()[:16]+':'+str(number)
        records.append(value);exports.append(item)
    output.mkdir(exist_ok=True)
    write_compare(page,template,records,'selected_valid_laps',reference_id=records[0]['id'])
    result=dict(folder=str(output),exports=exports,comparison=str(page));cache.save(result);return result
