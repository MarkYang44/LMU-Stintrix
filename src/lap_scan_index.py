"""Small source-bound lap descriptors; seek original CSV for complete samples."""
import bisect
import csv
import hashlib
import json
from pathlib import Path
from comparison_cache import source

STEP=2048
LIMIT=4*1024*1024


def signature(folder):
    from lap_cache_versions import signature as data_signature
    return data_signature(folder,'scan')


def load(folder):
    path=Path(folder)/'_lap_scan.json'
    try:
        if path.stat().st_size>LIMIT:return None
        envelope=json.loads(path.read_text('utf-8'));value=envelope['value']
        from lap_cache_versions import compatible
        expected=signature(folder)
        if not compatible(value['signature'],expected):return None
        if hashlib.sha256(encode(value)).hexdigest()!=envelope['sha256']:return None
        # Normalize in memory only; preserve the historical index on disk.
        value['signature']=expected
        return value
    except (OSError,ValueError,KeyError,TypeError):return None


def encode(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


def save(folder,inventory,index):
    if signature(folder)!=index['signature']:raise OSError('赛事数据已变化，请重新选择并重试')
    value=dict(signature=index['signature'],inventory=inventory,groups=index['groups'],cookies=index['cookies'],clocks=index['clocks'],monotonic=index['monotonic'])
    encoded=encode(value)
    if len(encoded)>LIMIT-1024:return
    from storage import atomic_json
    try:atomic_json(Path(folder)/'_lap_scan.json',dict(value=value,sha256=hashlib.sha256(encoded).hexdigest()))
    except OSError:pass  # Read-only records still support the ordinary extraction path.


def builder(folder):return dict(signature=signature(folder),groups=[],candidates=[],cookies=[],clocks=[],monotonic=True)


def ranges(best,first,last,index):
    if not index['monotonic']:return
    best['_range']=(first,last,index['cookies'])
    # Text conditions historically use the first timestamp match, even when
    # game lap-number updates lag the timer. Seek by time rather than lap start.
    position=max(0,bisect.bisect_left([entry[1] for entry in index['clocks']],best['start_s'])-1)
    best['_text_range']=(index['clocks'][position][0] if index['clocks'] else 0,None,index['cookies'])


def raw_rows(path,start=0,end=None,cookies=(),capture=None,columns=None):
    """CSV text cookies preserve quoted multiline fields and universal newlines."""
    path=Path(path)
    if not path.is_file():
        from column_store import rows,values,Reader,packed
        if columns is not None:
            names=Reader(packed(path)).columns
            if len(names)!=len(set(names)):
                # Full DictReader historically chooses the last duplicate name.
                for row in rows(path,start_row=start,end_row=end):yield tuple(row.get(k,'') for k in columns)
                return
        yield from (values(path,columns,start,end) if columns is not None else rows(path,start_row=start,end_row=end));return
    with path.open(encoding='utf-8-sig',newline='') as stream:
        if columns is None:reader=csv.DictReader(iter(stream.readline,''));fields=reader.fieldnames
        else:
            reader=csv.reader(iter(stream.readline,''));fields=next(reader,[])
            from csv_projection import projector
            project=projector(fields,columns)
        position=0
        if cookies and start:
            entry=cookies[max(0,bisect.bisect_right([item[0] for item in cookies],start)-1)]
            position,cookie=entry;stream.seek(cookie)
            reader=csv.DictReader(iter(stream.readline,''),fieldnames=fields) if columns is None else csv.reader(iter(stream.readline,''))
        while end is None or position<end:
            cookie=stream.tell() if capture is not None and position%STEP==0 else None
            row=next(reader,None)
            if columns is not None:
                while row==[]:row=next(reader,None)
            if row is None:break
            if cookie is not None:capture.append([position,cookie])
            if position>=start:yield row if columns is None else project(row)
            position+=1


def restore(folder,numbers,index):
    from analysis_spool import LapRows
    from laps import read_rows
    selected={}
    for info in index['groups']:
        if info['number'] not in numbers:continue
        best=dict(info);first,last=best.pop('_range');rows=LapRows(folder)
        for row in read_rows(Path(folder)/'inputs.csv',start=first,end=last,cookies=index['cookies']):rows.append(row)
        rows.seal()
        if len(rows)!=last-first:raise ValueError('Incomplete indexed telemetry')
        best['rows']=rows
        ranges(best,first,last,index)
        selected[best['number']]=best
    if signature(folder)!=index['signature']:raise OSError('赛事数据已变化，请重新选择并重试')
    return selected
