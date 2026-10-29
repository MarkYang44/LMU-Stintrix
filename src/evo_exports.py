"""Explicit EVO valid-lap CSV exports; no curve, image or report reconstruction."""
import csv,os,re,tempfile
from pathlib import Path
from uuid import uuid4


def _plain(folder,columns):return (folder/'inputs.csv').is_file() and len(columns)>1 and len(set(columns))==len(columns)


def _csv_lines(path,start,end,cookies,columns,*,projected=None):
    """Canonical text plus optional projected fields; complex rows retain csv.reader rules."""
    import bisect,io
    from itertools import chain
    from csv_projection import projector
    with path.open(encoding='utf-8-sig',newline='') as source:
        fields=next(csv.reader(iter(source.readline,'')),[])
        if fields!=columns:raise OSError('EVO lap source changed; retry after capture stops')
        position=0;project=projector(fields,columns);width=len(fields);scratch=None
        numeric=projector(columns,projected) if projected is not None else None
        if cookies and start:
            position,cookie=cookies[max(0,bisect.bisect_right([v[0] for v in cookies],start)-1)];source.seek(cookie)
        while end is None or position<end:
            line=source.readline()
            if not line:break
            stripped=line.rstrip('\r\n')
            if not stripped:continue
            if '"' not in line and len(line)<=csv.field_size_limit() and stripped.count(',')==width-1:
                encoded=stripped+'\r\n'
                if numeric is not None and position>=start:selected=numeric(stripped.split(','))
            else:
                row=next(csv.reader(chain((line,),iter(source.readline,''))),None)
                if not row:continue
                if scratch is None:scratch=io.StringIO(newline='');writer=csv.writer(scratch)
                scratch.seek(0);scratch.truncate(0);full=project(row);writer.writerow(full);encoded=scratch.getvalue()
                if numeric is not None and position>=start:selected=numeric(full)
            if position>=start:yield encoded if numeric is None else (encoded,selected)
            position+=1


class Inventory:
    """One batch's bounded metadata/index/header, never a telemetry row cache."""
    INDEX_BYTES=512*1024;META_BYTES=64*1024;HEADER_BYTES=64*1024
    def __init__(self):self.reader=None;self.clear()
    def close_rows(self):
        if self.reader is not None:
            close=getattr(self.reader,'close',None)
            if close:close()
        self.reader=None;self.row_key=None;self.position=None;self.serialized=False
    def clear(self):self.close_rows();self.key=None;self.value=None
    def rows(self,folder,best,value,columns):
        from lap_scan_index import raw_rows
        key=(folder,value['signature']);first=best['first_index']
        if self.row_key!=key or self.position!=first:
            self.close_rows();self.serialized=_plain(folder,columns)
            self.reader=(_csv_lines(folder/'inputs.csv',first,None,value.get('cookies',()),columns) if self.serialized else raw_rows(folder/'inputs.csv',first,None,value.get('cookies',()),columns=columns))
            self.row_key=key;self.position=first
        return self.reader,self.serialized
    def load(self,root,folder):
        from evo_laps import index,stamp
        from laps import finished_metadata
        from telemetry_file import Path as ReadPath
        folder=Path(folder);signature=stamp(folder);key=(folder,signature)
        if self.key==key:return self.value
        self.clear()
        meta=finished_metadata(folder)
        from simulators import accepts
        if not accepts(root,meta):raise ValueError('只能导出当前游戏的赛事记录')
        value=index(folder)
        if value['signature']!=signature:raise OSError('EVO lap source changed; retry after capture stops')
        with ReadPath(folder/'inputs.csv').open(encoding='utf-8-sig',newline='') as source:columns=next(csv.reader(source))
        if stamp(folder)!=signature:raise OSError('EVO lap source changed; retry after capture stops')
        prepared=(meta,value,columns)
        try:
            keep=(folder/'evo_laps_index.json').stat().st_size<=self.INDEX_BYTES and (folder/'session.json').stat().st_size<=self.META_BYTES and sum(len(v.encode('utf-8')) for v in columns)<=self.HEADER_BYTES
        except OSError:keep=False
        if keep:self.key=key;self.value=prepared
        return prepared


def lap_csv(root,folder,destination,number=None,*,_inventory=None):
    if number is not None and (type(number) is not int or number<1):raise ValueError('请选择有效圈号')
    from simulators import accepts,root_identity
    from runtime_activity import busy
    from report_worker import ReportDeferred
    root=Path(root).resolve();folder=Path(folder).resolve();destination=Path(destination).resolve()
    if root_identity(root)!='ac_evo' or folder==root or not folder.is_relative_to(root):raise ValueError('只能导出当前游戏的赛事记录')
    if destination.is_relative_to(folder):raise ValueError('导出目录不能位于原赛事内部')
    for name in ('session.json','inputs.csv','inputs.csv.stc'):
        path=folder/name
        if path.is_symlink() or path.is_junction():raise ValueError('不支持链接的赛事文件')
    if busy():raise ReportDeferred('请先停止 HUD，再导出圈 CSV；原始记录已保留')
    from evo_laps import stamp
    from evo_comparison import available
    inventory=_inventory if _inventory is not None else Inventory()
    meta,value,columns=inventory.load(root,folder)
    if not accepts(root,meta):raise ValueError('只能导出当前游戏的赛事记录')
    eligible=available(value);best=value['fastest'] if number is None else eligible.get(number)
    if best is None or best['num'] not in eligible:
        if number is None:raise ValueError('此赛事尚无已验证的最快有效完整圈')
        raise ValueError(f'第 {number} 圈不是已验证的有效完整圈')
    from lap_scan_index import raw_rows
    destination.mkdir(parents=True,exist_ok=True)
    track=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',str(meta.get('track') or 'Track')).strip(' .')[:48] or 'Track'
    target=destination/f"EVO-{track}-Lap-{best['num']}-{uuid4().hex[:12]}.csv"
    fd,name=tempfile.mkstemp(prefix='.evo-fastest-',suffix='.pending',dir=destination);pending=Path(name)
    try:
        count=0
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as out:
            writer=csv.writer(out);writer.writerow(columns)
            if _inventory is None:
                serialized=_plain(folder,columns)
                reader=(_csv_lines(folder/'inputs.csv',best['first_index'],best['end_index'],value.get('cookies',()),columns) if serialized else raw_rows(folder/'inputs.csv',best['first_index'],best['end_index'],value.get('cookies',()),columns=columns))
                rows=reader
            else:
                from itertools import islice
                reader,serialized=inventory.rows(folder,best,value,columns);rows=islice(reader,best['end_index']-best['first_index'])
            write=out.write if serialized else writer.writerow
            try:
                for row in rows:write(row);count+=1
            finally:
                if _inventory is None:reader.close()
        if count!=best['samples'] or stamp(folder)!=value['signature']:raise OSError('EVO lap source changed; retry after capture stops')
        if target.exists():raise FileExistsError(str(target))
        pending.rename(target)
        if _inventory is not None:inventory.position=best['end_index']
        return dict(path=str(target),number=best['num'],samples=count)
    except BaseException:
        inventory.close_rows();raise
    finally:pending.unlink(missing_ok=True)


def fastest_csv(root,folder,destination,*,_inventory=None):return lap_csv(root,folder,destination,_inventory=_inventory)
