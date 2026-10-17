"""Bounded, lossless lexical CSV columns. No hashes or verification passes.

Values stay as original UTF-8 field bytes, including quotes and line endings.
Each 2048-row / ~2 MiB block compresses its columns independently.
"""
import csv,io,json,os,struct,zlib
from functools import cached_property
from pathlib import Path
from uuid import uuid4
MAGIC=b'STXCOL1\n';END=b'STXEND1\n';HEAD=struct.Struct('<QQII');U32=struct.Struct('<I')
NAMES={'inputs.csv','vehicle.csv'}


def packed(path):return Path(str(path)+'.stc')


def _records(stream):
    pending=bytearray();quoted=False
    for line in stream:
        pending.extend(line);quoted^=bool(line.count(b'"')%2)
        if len(pending)>8*1024*1024:raise ValueError('CSV record exceeds block limit')
        if not quoted:yield bytes(pending);pending.clear()
    if pending:yield bytes(pending)


def _fields(record):
    result=[];start=0;quoted=False
    for i,value in enumerate(record):
        if value==34:quoted=not quoted
        elif value==44 and not quoted:result.append(record[start:i]);start=i+1
    result.append(record[start:]);return result


def _encode(values):
    out=bytearray();prefix=bytearray();last=None;count=0;previous=b''
    for value in values:
        shared=0
        for a,b in zip(previous,value):
            if a!=b:break
            shared+=1
        suffix=value[shared:];prefix.extend(U32.pack(shared));prefix.extend(U32.pack(len(suffix)));prefix.extend(suffix);previous=value
        if last is not None and value!=last:out.extend(U32.pack(count));out.extend(U32.pack(len(last)));out.extend(last);count=0
        last=value;count+=1
    if count:out.extend(U32.pack(count));out.extend(U32.pack(len(last)));out.extend(last)
    repeat=b'\x00'+zlib.compress(out,6);delta=b'\x01'+zlib.compress(prefix,6)
    return repeat if len(repeat)<=len(delta) else delta


def _decode(data,rows):
    kind=data[0];raw=zlib.decompress(data[1:]);result=[];pos=0;previous=b''
    if kind==1:
        while pos<len(raw):
            shared=U32.unpack_from(raw,pos)[0];length=U32.unpack_from(raw,pos+4)[0];pos+=8
            if shared>len(previous) or pos+length>len(raw) or len(result)>=rows:raise ValueError('Invalid prefix column')
            previous=previous[:shared]+raw[pos:pos+length];result.append(previous);pos+=length
        if len(result)!=rows:raise ValueError('Incomplete prefix column')
        return result
    if kind!=0:raise ValueError('Unsupported column encoding')
    while pos<len(raw):
        count=U32.unpack_from(raw,pos)[0];length=U32.unpack_from(raw,pos+4)[0];pos+=8
        if count<1 or len(result)+count>rows or pos+length>len(raw):raise ValueError('Invalid column block')
        result.extend([raw[pos:pos+length]]*count);pos+=length
    if len(result)!=rows:raise ValueError('Incomplete column block')
    return result


class Reader:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.is_symlink() or self.path.is_junction():raise ValueError('Linked column store is not supported')
        with self.path.open('rb') as f:
            if f.read(8)!=MAGIC:raise ValueError('Unsupported column store')
            self.logical_bytes,self.mtime_ns,size,self.width=HEAD.unpack(f.read(HEAD.size))
            if size>1048576 or not 1<=self.width<=512:raise ValueError('Invalid column header')
            self.header=f.read(size);self.columns=next(csv.reader(io.StringIO(self.header.decode('utf-8-sig'),newline='')))
    @cached_property
    def blocks(self):
        with self.path.open('rb') as f:
            f.seek(-16,2);n=struct.unpack('<Q',f.read(8))[0]
            if f.read(8)!=END or n>16*1048576:raise ValueError('Incomplete column store')
            f.seek(-16-n,2);return json.loads(f.read(n))

    def chunks(self,columns=None,start_row=0,end_row=None):
        indexes=list(range(self.width)) if columns is None else [self.columns.index(k) if k in self.columns else None for k in columns]
        full=columns is None;position=0
        with self.path.open('rb') as f:
            for block in self.blocks:
                count=block['rows'];first=position;position+=count
                if position<=start_row or end_row is not None and first>=end_row:continue
                values=[]
                for i in indexes:
                    if i is None:values.append([b'']*count);continue
                    offset,size=block['columns'][i];f.seek(offset);values.append(_decode(f.read(size),count))
                begin=max(0,start_row-first);end=min(count,end_row-first) if end_row is not None else count
                def record(j):
                    if full:return b','.join(v[j] for v in values)
                    fields=[]
                    for i,v in zip(indexes,values):
                        field=v[j]
                        if i==self.width-1:field=field[:-2] if field.endswith(b'\r\n') else field[:-1] if field.endswith((b'\n',b'\r')) else field
                        fields.append(field)
                    return b','.join(fields)+b'\n'
                yield b''.join(record(j) for j in range(begin,end))

    def bytes(self):
        yield self.header
        yield from self.chunks()


class Stream(io.RawIOBase):
    def __init__(self,reader):super().__init__();self.iterator=iter(reader.bytes());self.pending=b'';self.offset=0
    def readable(self):return True
    def readinto(self,buffer):
        if self.offset==len(self.pending):
            self.pending=next(self.iterator,b'');self.offset=0
        n=min(len(buffer),len(self.pending)-self.offset);buffer[:n]=self.pending[self.offset:self.offset+n];self.offset+=n;return n
    def close(self):
        self.iterator.close();self.pending=b'';super().close()


def open_csv(path,mode='r',encoding='utf-8',errors=None,newline=None):
    stream=io.BufferedReader(Stream(Reader(packed(path))))
    return stream if 'b' in mode else io.TextIOWrapper(stream,encoding=encoding or 'utf-8',errors=errors,newline=newline)


def rows(path,columns=None,start_row=0,end_row=None):
    path=Path(path)
    if not path.is_file() and packed(path).is_file():
        reader=Reader(packed(path));names=columns or reader.columns
        for block in reader.chunks(columns,start_row,end_row):
            yield from csv.DictReader(io.StringIO(block.decode('utf-8'),newline=''),fieldnames=names)
    else:
        with path.open(encoding='utf-8-sig',newline='') as stream:
            for i,row in enumerate(csv.DictReader(stream)):
                if i<start_row:continue
                if end_row is not None and i>=end_row:break
                yield {k:row.get(k,'') for k in columns} if columns else row


def convert(path,replace=False):
    """Single read, atomic promotion. Retire CSV only after a smaller file closes."""
    path=Path(path)
    if path.name not in NAMES or path.is_symlink() or path.is_junction():raise ValueError('Not a telemetry CSV')
    meta=json.loads((path.parent/'session.json').read_text(encoding='utf-8-sig'))
    if meta.get('status') not in ('complete','completed','finished','imported','recovered'):raise ValueError('Wait for recording to finish')
    if not path.is_file():return dict(converted=False,saved_bytes=0)
    stamp=path.stat();target=packed(path);pending=target.with_name(target.name+'.'+str(os.getpid())+'.'+uuid4().hex+'.pending')
    from session_compression import physical_size
    before=physical_size(path);index=[];rows_total=0
    try:
        with path.open('rb') as source,pending.open('xb') as out:
            records=iter(_records(source));header=next(records,b'');width=len(_fields(header))
            if not header or width>512:raise ValueError('Unsupported CSV header')
            out.write(MAGIC);out.write(HEAD.pack(stamp.st_size,stamp.st_mtime_ns,len(header),width));out.write(header)
            block=[];size=0
            def flush():
                nonlocal rows_total
                if not block:return
                entries=[]
                for col in zip(*block):
                    data=_encode(col);entries.append([out.tell(),len(data)]);out.write(data)
                index.append(dict(rows=len(block),columns=entries));rows_total+=len(block)
            for record in records:
                values=_fields(record)
                if len(values)!=width:raise ValueError('CSV column count changed')
                block.append(values);size+=len(record)
                if len(block)>=2048 or size>=2*1048576:flush();block=[];size=0
            flush();data=json.dumps(index,separators=(',',':')).encode()
            if len(data)>16*1048576:raise ValueError('Column index exceeds format limit; CSV retained')
            out.write(data);out.write(struct.pack('<Q',len(data)));out.write(END)
        after=pending.stat().st_size
        if after>=before:pending.unlink();return dict(converted=False,saved_bytes=0,reason='existing storage is smaller')
        # Size/time are cheap concurrency guards, not content verification.
        now=path.stat()
        if (now.st_size,now.st_mtime_ns)!=(stamp.st_size,stamp.st_mtime_ns):raise OSError('CSV changed during conversion')
        if target.exists():raise FileExistsError('Existing column store retained')
        pending.replace(target)
        if replace:
            try:path.unlink()
            except OSError:
                # A reader can still hold the CSV on Windows. Keep that original
                # authoritative and discard only this conversion's new output.
                target.unlink(missing_ok=True);raise
        return dict(converted=True,rows=rows_total,logical_bytes=stamp.st_size,physical_bytes=after,saved_bytes=max(0,before-after) if replace else 0,path=str(target))
    finally:pending.unlink(missing_ok=True)


def cleanup_pending(folder):
    import re,time
    from storage import process_alive
    folder=Path(folder).resolve();removed=0
    for p in folder.glob('*.csv.stc.*.pending'):
        match=re.fullmatch(r'(?:inputs|vehicle)\.csv\.stc\.(\d+)\.[0-9a-f]{32}\.pending',p.name)
        if match and not p.is_symlink() and not p.is_junction() and p.resolve().parent==folder and time.time()-p.stat().st_mtime>86400 and not process_alive(int(match[1])):
            removed+=p.stat().st_size;p.unlink()
    return removed


def restore(path):
    import shutil
    path=Path(path);source=packed(path)
    if path.is_file() or not source.is_file():return dict(restored=False,path=str(path))
    reader=Reader(source);pending=path.with_name(path.name+'.'+uuid4().hex+'.pending')
    try:
        with io.BufferedReader(Stream(reader)) as src,pending.open('xb') as out:shutil.copyfileobj(src,out,1048576)
        pending.replace(path);os.utime(path,ns=(reader.mtime_ns,reader.mtime_ns));source.unlink()
        return dict(restored=True,path=str(path))
    finally:pending.unlink(missing_ok=True)
