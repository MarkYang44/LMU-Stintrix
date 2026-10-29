"""Streaming, atomic standalone reports. No full-race text/JSON copies in RAM."""
import base64
import csv
from functools import wraps
import json
import math
from telemetry_file import Path
import struct
import tempfile
import threading
import zlib

_lock=threading.RLock()
_encoder=json.JSONEncoder(ensure_ascii=False,separators=(',',':'),allow_nan=False)
_numeric_types=(int,float,bool,type(None))
REVIEW_COLUMNS=('time_s','lap','lap_distance_m','throttle','brake','steering',
    'filtered_throttle','filtered_brake','filtered_steering','speed_kmh',
    'world_x_m','world_z_m','track_length_m')


def serialized(function):
    @wraps(function)
    def run(*args,**kwargs):
        with _lock:return function(*args,**kwargs)
    return run


class JSONFile:
    def __init__(self,path):self.path=Path(path)


class VehicleJSON:
    def __init__(self,folder,meta):self.folder,self.meta=Path(folder),meta
    def chunks(self):
        from processing_context import current
        shared=current(self.folder)
        if shared is not None and shared.values.get('vehicle') is not None:
            yield from json_chunks(shared.values['vehicle']);return
        from vehiclelab import COLUMNS,DEFAULT_PROFILE,number
        columns=[k for k in COLUMNS if k not in ('time_s','session_time_s')]
        from lap_scan_index import raw_rows
        from contextlib import closing
        with closing(raw_rows(self.folder/'vehicle.csv',columns=('session_time_s','time_s',*columns))) as rows:
            first=next(rows,None)
            origin=(number(first[0]) or 0)-(number(first[1]) or 0) if first else 0
            header=dict(version=1,columns=columns,record_hz=self.meta.get('vehicle_telemetry',{}).get('target_hz'),
                source=self.meta.get('source'),time_origin_s=origin,profile=self.meta.get('vehicle_profile',DEFAULT_PROFILE),
                strategy=self.meta.get('vehicle_strategy',{}),strategy_history=self.meta.get('vehicle_settings_history',[]))
            yield from json_chunks(header,open_object=True)
            yield b',"data":'
            def numbers():
                last=-math.inf
                for row in __import__('itertools').chain((first,) if first else (),rows):
                    t=number(row[0])
                    if t is None or t<=last:raise ValueError('附加遥测时间戳无效')
                    last=t;yield [t,*_vehicle_values(row[2:])]
            yield from _matrix_chunks(numbers(),len(columns)+1)
            yield b'}'


def _vehicle_values(row):
    # CSV projection supplies text or missing cells. Empty cells and nonfinite
    # text retain number()'s None result; malformed fields keep its fallback.
    try:values=list(map(float,('nan' if v is None or v=='' else v for v in row)))
    except (ValueError,TypeError):
        from vehiclelab import number
        return list(map(number,row))
    return [v if math.isfinite(v) else None for v in values]


def _matrix_chunks(rows,width):
    """Exact JSON rows, at most 64 boxed rows / 8192 cells per ordinary batch."""
    yield b'['
    comma=False;batch=[];batch_limit=min(64,max(1,8192//width))
    for row in rows:
        if len(row)>256:
            if batch:
                if comma:yield b','
                yield _encoder.encode(batch)[1:-1].encode('utf-8');batch=[];comma=True
            if comma:yield b','
            yield from json_chunks(row);comma=True
        else:
            batch.append(row)
            if len(batch)>=batch_limit:
                if comma:yield b','
                yield _encoder.encode(batch)[1:-1].encode('utf-8');batch=[];comma=True
    if batch:
        if comma:yield b','
        yield _encoder.encode(batch)[1:-1].encode('utf-8')
    yield b']'


def json_chunks(value,open_object=False):
    from buffers import NumericTable
    from analysis_spool import DiskTable
    if isinstance(value,JSONFile):
        with value.path.open('rb') as f:
            yield from iter(lambda:f.read(65536),b'')
    elif isinstance(value,VehicleJSON):yield from value.chunks()
    elif isinstance(value,dict):
        yield b'{'
        for i,(key,item) in enumerate(value.items()):
            if i:yield b','
            yield _encoder.encode(key).encode('utf-8');yield b':'
            yield from json_chunks(item)
        if not open_object:yield b'}'
    elif isinstance(value,(NumericTable,DiskTable)):
        # Bound both boxed rows and cell count. The same encoder, separators and
        # scalar representations produce exactly the previous JSON byte stream.
        yield from _matrix_chunks(value,value.width)
    elif isinstance(value,(list,tuple)) and len(value)<=256 and all(type(v) in _numeric_types for v in value):
        yield _encoder.encode(value).encode('utf-8')
    elif isinstance(value,(list,tuple)) and any(isinstance(v,(dict,list,tuple,NumericTable,DiskTable,JSONFile,VehicleJSON)) for v in value):
        yield b'['
        for i,item in enumerate(value):
            if i:yield b','
            yield from json_chunks(item)
        yield b']'
    else:
        # Coalesce the encoder's tiny numeric tokens before calling zlib.
        pieces=[];size=0
        for piece in _encoder.iterencode(value):
            pieces.append(piece);size+=len(piece)
            if size>=32768:
                yield ''.join(pieces).encode('utf-8');pieces=[];size=0
        if pieces:yield ''.join(pieces).encode('utf-8')


def review_records(path):
    pack=struct.Struct('<13d');pending=bytearray()
    from column_store import values
    for row in values(path,REVIEW_COLUMNS):
        # Input-only records often lack coordinates; skip the full-field test
        # immediately for these rows, preserving the original sparse path.
        if row[10] and row[11] and row[12] and all(row):pending.extend(pack.pack(*map(float,row)))
        else:
            # Keep the historical zero / missing-coordinate rules for sparse rows.
            numbers=[float(value or (0 if i<10 else 'nan')) for i,value in enumerate(row)]
            pending.extend(pack.pack(*numbers))
        if len(pending)>=65536:yield pending;pending=bytearray()
    if pending:yield pending


def coalesced(chunks,limit=65536):
    """Batch tiny encoder tokens, preserving the exact byte stream and order."""
    pending=bytearray()
    for chunk in chunks:
        if not pending and len(chunk)>=limit:yield chunk;continue
        pending.extend(chunk)
        if len(pending)>=limit:yield bytes(pending);pending.clear()
    if pending:yield bytes(pending)


def _block(out,identifier,chunks):
    compressor=zlib.compressobj(6,zlib.DEFLATED,31);size=0
    with tempfile.SpooledTemporaryFile(max_size=1048576,dir=Path(out.name).parent if isinstance(getattr(out,'name',None),str) else None) as f:
        for chunk in coalesced(chunks):
            size+=len(chunk);f.write(compressor.compress(chunk))
        f.write(compressor.flush());f.seek(0)
        out.write(f'<script type="application/octet-stream" id="{identifier}" data-bytes="{size}">')
        for chunk in iter(lambda:f.read(49152),b''):out.write(base64.b64encode(chunk).decode('ascii'))
        out.write('</script>\n')


def write_page(path,source,blocks):
    path=Path(path);pending=path.with_name(path.name+'.'+str(threading.get_ident())+'.pending')
    before,after=source.split('/*STINTRIX_BLOCKS*/',1)
    try:
        with pending.open('w',encoding='utf-8',newline='') as out:
            out.write(before)
            for identifier,chunks in blocks:_block(out,identifier,chunks)
            out.write(after)
        pending.replace(path)
    finally:
        if pending.exists():pending.unlink()


def script(assets):return (Path(assets)/'dataview.js').read_text(encoding='utf-8')


@serialized
def render_review(folder,assets,track_js,fastest=None,output=None,local=False):
    folder,assets=Path(folder),Path(assets)
    meta=json.loads((folder/'session.json').read_text(encoding='utf-8'))
    payload=dict(meta=meta,fastest=fastest)
    for key,name in [('analysis','session_analysis.json'),('native_channels','native_channels.json'),('endurance','endurance_analysis.json')]:
        path=folder/name;payload[key]=JSONFile(path) if path.exists() else None
    payload['vehicle_telemetry']=VehicleJSON(folder,meta) if (folder/'vehicle.csv').exists() else None
    with (folder/'inputs.csv').open(encoding='utf-8-sig',newline='') as f:
        first=next(csv.DictReader(f),None)
        payload['native_time_offset_s']=(float(first['time_s'])-float(first['session_time_s'])) if first else 0
    from control_theme import web_script
    source=(assets/'report.html').read_text(encoding='utf-8').replace('/*INTERFACE_THEME_JS*/',web_script(assets))
    for marker,text in [('/*DATA_VIEW_JS*/',script(assets)),('/*TRACK_VIEW_JS*/',track_js),
        ('/*VEHICLE_VIEW_JS*/',(assets/'vehicleview.js').read_text(encoding='utf-8')),
        ('/*ENDURANCE_VIEW_JS*/',(assets/'enduranceview.js').read_text(encoding='utf-8')),
        ('/*SESSION_DATA*/null','await StintrixData.jsonBlock("stintrix-meta")')]:source=source.replace(marker,text)
    target=output or folder/'review.html'
    if local:
        from report_assets import prepare
        source=prepare(target,source,assets,folder.parent.parent)
    write_page(target,source,[('stintrix-meta',json_chunks(payload)),('stintrix-inputs',review_records(folder/'inputs.csv'))])
