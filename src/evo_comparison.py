"""Selected EVO laps: reuse selection/cache/storage, keep native clock semantics."""
import csv
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
        try:
            item,=existing['exports'];expected=folder/'SelectedLaps'/f'EVO_Lap_{number}'
            if any(Path(item[k]).resolve()!=expected.with_suffix(ext) for k,ext in (('json','.lap.json'),('csv','.csv'))):raise ValueError('Invalid lap cache path')
            record=load(item['json'])
            if record['lap']!=lap_info(best) or record.get('simulator_id')!='ac_evo':raise ValueError('Stale EVO lap cache')
            return item,record
        except (OSError,ValueError,KeyError,TypeError):pass
    target=folder/'SelectedLaps';target.mkdir(exist_ok=True)
    info=lap_info(best);data=read_curve(folder,best,value,target)
    record=dict(format=FORMAT,version=1,id=folder.name+':'+str(number),session=meta,lap=info,
        data_columns=DATA_COLUMNS,data=data,conditions={},trajectory=None,reference_kind='selected',
        input_channels=meta.get('input_channels',{}),simulator_id='ac_evo')
    json_path=target/f'EVO_Lap_{number}.lap.json';csv_path=target/f'EVO_Lap_{number}.csv'
    from lap_scan_index import raw_rows
    from telemetry_file import Path as ReadPath
    from uuid import uuid4
    pending=csv_path.with_name(csv_path.name+'.'+uuid4().hex+'.pending')
    try:
        with ReadPath(folder/'inputs.csv').open(encoding='utf-8-sig',newline='') as stream:
            fields=next(csv.reader(stream))
        reader=raw_rows(folder/'inputs.csv',start=best['first_index'],end=best['end_index'],cookies=value.get('cookies',()),columns=fields)
        try:
            with pending.open('w',encoding='utf-8',newline='') as out:
                writer=csv.writer(out);writer.writerow(fields);count=0
                for row in reader:writer.writerow(row);count+=1
        finally:reader.close()
        if count!=info['sample_count'] or stamp(folder)!=value['signature']:raise OSError('EVO lap source changed; retry after capture stops')
        write_json(json_path,record);pending.replace(csv_path)
        item=dict(number=number,json=str(json_path),csv=str(csv_path))
        remember(folder,[number],None,dict(folder=str(target),exports=[item],comparison=None),individual=True)
        return item,record
    except BaseException:data.close();raise
    finally:pending.unlink(missing_ok=True)


def export_pair(root,identities):
    from paths import ASSETS
    from comparison_cache import Pair
    from lap_identity import same_layout
    from simulators import accepts
    root=Path(root).resolve();identities=[(Path(f).resolve(),n) for f,n in identities]
    if len(identities)!=2 or identities[0]==identities[1]:raise ValueError('请选择两个不同的有效圈')
    if any(not f.is_relative_to(root) or type(n) is not int or n<1 for f,n in identities):raise ValueError('只能选择当前游戏目录中的有效圈')
    metadata={f:finished_metadata(f) for f,_ in identities}
    if any(m.get('simulator_id')!='ac_evo' or not accepts(root,m) for m in metadata.values()):raise ValueError('只能对比当前游戏的赛事记录')
    template=ASSETS/'evo_compare.html';output=root/'LapComparisons'
    page=output/('EVO_Compare_'+hashlib.sha256(repr(identities).encode()).hexdigest()[:16]+'.html')
    cache=Pair(root,identities,template,page);existing=cache.read()
    if existing:return existing
    inventories={f:index(f) for f in metadata};headers=[]
    for folder,number in identities:
        lap=available(inventories[folder]).get(number)
        if lap is None:raise ValueError(f'第 {number} 圈不是已验证的有效完整圈')
        headers.append(dict(session=metadata[folder],lap=lap_info(lap)))
    if not same_layout(*headers):raise ValueError('请选择同一赛道、同一布局的两圈；缺少可靠长度时无法确认布局')
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
