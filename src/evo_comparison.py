"""Selected EVO laps: reuse selection/cache/storage, keep native clock semantics."""
import hashlib
from collections import Counter
from pathlib import Path
from contextlib import ExitStack

from evo_laps import index,lap_info,read_curve,stamp
from laps import finished_metadata,write_json,write_compare,FORMAT,DATA_COLUMNS


def available(value):
    counts=Counter(lap['num'] for lap in value['laps'])
    return {lap['num']:lap for lap in value['laps'] if counts[lap['num']]==1 and lap['complete']
        and not lap['partial'] and lap['valid'] is True and not lap['in_pits'] and lap['samples']>=3}


def valid_laps(folder):
    meta=finished_metadata(folder)
    if meta.get('simulator_id')!='ac_evo':raise ValueError('只能选择 AC EVO 记录')
    return [lap_info(lap) for lap in available(index(folder)).values()]


def selected(folder,number,value,meta):
    """Cache a full-precision curve and all original CSV field strings."""
    from lap_exports import cached,remember
    from json_store import load
    from runtime_activity import busy
    if busy():
        from report_worker import ReportDeferred
        raise ReportDeferred('请先停止 HUD，再生成 EVO 圈对比；原始记录已保留')
    best=available(value).get(number)
    if best is None:raise ValueError(f'第 {number} 圈不是已验证的有效完整圈')
    existing=cached(folder,[number],None,individual=True)
    if existing:
        record=None
        try:
            item,=existing['exports'];expected=folder/'SelectedLaps'/f'EVO_Lap_{number}'
            if any(Path(item[k]).resolve()!=expected.with_suffix(ext) for k,ext in (('json','.lap.json'),('csv','.csv'))):raise ValueError('Invalid lap cache path')
            record=load(item['json'])
            if record['lap']!=lap_info(best) or record.get('simulator_id')!='ac_evo':raise ValueError('Stale EVO lap cache')
            return item,record
        except (OSError,ValueError,KeyError,TypeError):
            close=getattr(record.get('data'),'close',None) if isinstance(record,dict) else None
            if close:close()
    target=folder/'SelectedLaps';target.mkdir(exist_ok=True)
    info=lap_info(best);data=None
    json_path=target/f'EVO_Lap_{number}.lap.json';csv_path=target/f'EVO_Lap_{number}.csv'
    from uuid import uuid4
    pending=csv_path.with_name(csv_path.name+'.'+uuid4().hex+'.pending')
    try:
        with pending.open('w',encoding='utf-8',newline='') as out:
            data=read_curve(folder,best,value,target,csv_file=out)
        if len(data)!=info['sample_count'] or stamp(folder)!=value['signature']:raise OSError('EVO lap source changed; retry after capture stops')
        record=dict(format=FORMAT,version=1,id=folder.name+':'+str(number),session=meta,lap=info,
            data_columns=DATA_COLUMNS,data=data,conditions={},trajectory=None,reference_kind='selected',
            input_channels=meta.get('input_channels',{}),simulator_id='ac_evo')
        write_json(json_path,record);pending.replace(csv_path)
        item=dict(number=number,json=str(json_path),csv=str(csv_path))
        remember(folder,[number],None,dict(folder=str(target),exports=[item],comparison=None),individual=True)
        return item,record
    except BaseException:
        if data is not None:data.close()
        raise
    finally:pending.unlink(missing_ok=True)


def export_pair(root,identities):
    identities=tuple(identities)
    if len(identities)!=2:raise ValueError('请选择两个不同的有效圈')
    return export_many(root,identities)


def export_many(root,identities):
    """Two to six full laps; one inventory per source, no boundary synthesis."""
    from paths import ASSETS
    from comparison_cache import Pair
    from lap_identity import same_layout
    from simulators import accepts
    root=Path(root).resolve();identities=[(Path(f).resolve(),n) for f,n in identities]
    if not 2<=len(identities)<=6:raise ValueError('请选择 2–6 个不同的有效圈')
    if any(not f.is_relative_to(root) or type(n) is not int or n<1 for f,n in identities):raise ValueError('只能选择当前游戏目录中的有效圈')
    if len(set(identities))!=len(identities):raise ValueError('请选择 2–6 个不同的有效圈')
    from runtime_activity import busy
    if busy():
        from report_worker import ReportDeferred
        raise ReportDeferred('请先停止 HUD，再生成 EVO 圈对比；原始记录已保留')
    signatures={f:stamp(f) for f in dict.fromkeys(f for f,_ in identities)}
    metadata={f:finished_metadata(f) for f in signatures}
    if any(m.get('simulator_id')!='ac_evo' or not accepts(root,m) for m in metadata.values()):raise ValueError('只能对比当前游戏的赛事记录')
    template=ASSETS/'evo_compare.html';output=root/'LapComparisons'
    prefix='EVO_Compare_' if len(identities)==2 else 'EVO_Multi_'
    page=output/(prefix+hashlib.sha256(repr(identities).encode()).hexdigest()[:16]+'.html')
    cache=Pair(root,identities,template,page)
    if any(signature!=signatures[f]['source'] for signature,(f,_) in zip(cache.signature['sources'],identities)):raise OSError('赛事数据已变化，请重新选择并重试')
    existing=cache.read()
    if existing:return existing
    inventories={f:index(f) for f in metadata};headers=[];eligible={f:available(v) for f,v in inventories.items()}
    if any(v['signature']!=signatures[f] for f,v in inventories.items()):raise OSError('赛事数据已变化，请重新选择并重试')
    for folder,number in identities:
        lap=eligible[folder].get(number)
        if lap is None:raise ValueError(f'第 {number} 圈不是已验证的有效完整圈')
        headers.append(dict(session=metadata[folder],lap=lap_info(lap)))
    if any(not same_layout(a,b) for i,a in enumerate(headers) for b in headers[i+1:]):raise ValueError('请选择同一赛道、同一布局的有效圈；缺少可靠长度时无法确认布局')
    with ExitStack() as stack:
        records=[];exports=[]
        for folder,number in identities:
            item,record=selected(folder,number,inventories[folder],metadata[folder])
            close=getattr(record['data'],'close',None)
            if close:stack.callback(close)
            record['id']=hashlib.sha256(str(folder).encode()).hexdigest()[:16]+':'+str(number)
            records.append(record);exports.append(item)
        output.mkdir(exist_ok=True)
        write_compare(page,template,records,'evo_selected_valid_laps',reference_id=records[0]['id'])
    result=dict(folder=str(output),exports=exports,comparison=str(page));cache.save(result);return result


def export_single(root,folder,number):
    """Open any verified lap, sharing complete exports and page provenance."""
    from comparison_cache import View
    from simulators import accepts,root_identity
    from paths import ASSETS
    from runtime_activity import busy
    from evo_laps import write_curve
    root=Path(root).resolve();folder=Path(folder).resolve()
    if root_identity(root)!='ac_evo' or not folder.is_relative_to(root) or type(number) is not int or number<1:raise ValueError('请选择当前 AC EVO 目录中的有效圈')
    if busy():
        from report_worker import ReportDeferred
        raise ReportDeferred('请先停止 HUD，再生成 EVO 完整圈曲线；原始记录已保留')
    signature=stamp(folder);meta=finished_metadata(folder)
    if not accepts(root,meta):raise ValueError('只能选择 AC EVO 记录')
    value=index(folder)
    if value['signature']!=signature or stamp(folder)!=signature:raise OSError('赛事数据已变化，请重新选择并重试')
    if number not in available(value):raise ValueError(f'第 {number} 圈不是已验证的有效完整圈')
    page=folder/'SelectedLaps'/f'EVO_Lap_{number}.html'
    cache=View(root,[(folder,number)],ASSETS/'evo_compare.html',page);existing=cache.read()
    if existing:return existing
    item,record=selected(folder,number,value,meta)
    try:write_curve(page,record,item['json'])
    finally:record['data'].close()
    result=dict(folder=str(page.parent),exports=[item],comparison=str(page));cache.save(result);return result
