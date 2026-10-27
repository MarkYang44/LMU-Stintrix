"""Bounded, lossless lexical CSV columns. No hashes or verification passes.

Values stay as original UTF-8 field bytes, including quotes and line endings.
Each 2048-row / ~2 MiB block compresses its columns independently.
"""
import csv,io,json,os,struct,zlib
from functools import cached_property,lru_cache
from pathlib import Path
from uuid import uuid4
MAGIC=b'STXCOL2\n';END=b'STXEND2\n';LEGACY_MAGIC=b'STXCOL1\n';LEGACY_END=b'STXEND1\n'
HEAD=struct.Struct('<QQII');U32=struct.Struct('<I')
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
    if b'"' not in record:return record.split(b',')
    result=[];start=0;quoted=False
    for i,value in enumerate(record):
        if value==34:quoted=not quoted
        elif value==44 and not quoted:result.append(record[start:i]);start=i+1
    result.append(record[start:]);return result


def _varint(value):
    out=bytearray()
    while value>=128:out.append((value&127)|128);value>>=7
    out.append(value);return out


def _read_varint(raw,pos):
    if pos>=len(raw):raise ValueError('Incomplete column integer')
    byte=raw[pos];pos+=1
    if byte<128:return byte,pos
    value=byte&127
    for shift in range(7,35,7):
        if pos>=len(raw):raise ValueError('Incomplete column integer')
        byte=raw[pos];pos+=1;value|=(byte&127)<<shift
        if not byte&128:
            if value>0xffffffff:break
            return value,pos
    raise ValueError('Invalid column integer')


def _encode(values):
    values=tuple(values)
    if values and len(values)<=2048 and len(values[0])<=256 and values.count(values[0])==len(values):return _constant(values[0],len(values))
    return _encode_uncached(values)


@lru_cache(maxsize=128)
def _constant(value,count):return _encode_uncached((value,)*count)


def _encode_uncached(values):
    out=bytearray();prefix=bytearray();compact=bytearray();last=None;count=0;previous=b''
    for value in values:
        shared=0
        for a,b in zip(previous,value):
            if a!=b:break
            shared+=1
        suffix=value[shared:];prefix.extend(U32.pack(shared));prefix.extend(U32.pack(len(suffix)));prefix.extend(suffix)
        compact.extend(_varint(shared));compact.extend(_varint(len(suffix)));compact.extend(suffix);previous=value
        if last is not None and value!=last:out.extend(U32.pack(count));out.extend(U32.pack(len(last)));out.extend(last);count=0
        last=value;count+=1
    if count:out.extend(U32.pack(count));out.extend(U32.pack(len(last)));out.extend(last)
    # Retaining both v1 candidates makes each column no larger than before.
    candidates=[b'\x00'+zlib.compress(out,6),b'\x01'+zlib.compress(prefix,6),b'\x02'+zlib.compress(compact,6)]
    del out,prefix,compact
    plain=b''.join(_varint(len(value))+value for value in values)
    candidates.append(b'\x03'+zlib.compress(plain,6));del plain
    dictionary=list(dict.fromkeys(values))
    if len(dictionary)<=len(values)//2:
        ids={value:i for i,value in enumerate(dictionary)}
        encoded=_varint(len(dictionary))
        for value in dictionary:encoded.extend(_varint(len(value)));encoded.extend(value)
        for value in values:encoded.extend(_varint(ids[value]))
        candidates.append(b'\x04'+zlib.compress(encoded,6))
    return min(candidates,key=len)


def _decode(data,rows):
    kind=data[0];raw=zlib.decompress(data[1:]);result=[];pos=0;previous=b''
    if kind in (2,3,4):
        dictionary=[]
        if kind==4:
            count,pos=_read_varint(raw,pos)
            if not 1<=count<=rows:raise ValueError('Invalid column dictionary')
            for _ in range(count):
                length,pos=_read_varint(raw,pos)
                if pos+length>len(raw):raise ValueError('Incomplete column dictionary')
                dictionary.append(raw[pos:pos+length]);pos+=length
            # Valid one-byte IDs can be bounds-checked once and mapped in C.
            # Other/noncanonical encodings retain the original integer reader.
            if count<=128 and len(raw)-pos==rows:
                indexes=raw[pos:]
                if max(indexes,default=0)<count:return list(map(dictionary.__getitem__,indexes))
        for _ in range(rows):
            if kind==4:
                index,pos=_read_varint(raw,pos)
                if index>=len(dictionary):raise ValueError('Invalid dictionary index')
                result.append(dictionary[index]);continue
            shared=0
            if kind==2 and pos+1<len(raw) and raw[pos]<128 and raw[pos+1]<128:
                shared=raw[pos];length=raw[pos+1];pos+=2
            else:
                if kind==2:shared,pos=_read_varint(raw,pos)
                if pos<len(raw) and raw[pos]<128:length=raw[pos];pos+=1
                else:length,pos=_read_varint(raw,pos)
            if shared>len(previous) or pos+length>len(raw):raise ValueError('Invalid compact column')
            previous=previous[:shared]+raw[pos:pos+length];result.append(previous);pos+=length
        if pos!=len(raw):raise ValueError('Unexpected trailing column bytes')
        return result
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
            magic=f.read(8)
            if magic not in (MAGIC,LEGACY_MAGIC):raise ValueError('Unsupported column store')
            self.version=2 if magic==MAGIC else 1
            self.logical_bytes,self.mtime_ns,size,self.width=HEAD.unpack(f.read(HEAD.size))
            if size>1048576 or not 1<=self.width<=512:raise ValueError('Invalid column header')
            self.header=f.read(size);self.columns=next(csv.reader(io.StringIO(self.header.decode('utf-8-sig'),newline='')))
    @cached_property
    def blocks(self):
        with self.path.open('rb') as f:
            f.seek(-16,2);n=struct.unpack('<Q',f.read(8))[0]
            if f.read(8)!=(END if self.version==2 else LEGACY_END) or n>16*1048576:raise ValueError('Incomplete column store')
            f.seek(-16-n,2);return json.loads(f.read(n))

    def _selected(self,columns=None,start_row=0,end_row=None):
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
                # Keep original field bytes; transpose each decoded block in C.
                # The physical last column owns the original record terminator.
                if not full:
                    for j,i in enumerate(indexes):
                        if i==self.width-1:
                            values[j]=[v[:-2] if v.endswith(b'\r\n') else v[:-1] if v.endswith((b'\n',b'\r')) else v for v in values[j]]
                yield values,begin,end

    def chunks(self,columns=None,start_row=0,end_row=None):
        from itertools import islice
        full=columns is None
        for values,begin,end in self._selected(columns,start_row,end_row):
            if not values:
                yield b'\n'*(end-begin);continue
            records=islice(zip(*values),begin,end)
            yield b''.join(b','.join(row) for row in records) if full else b''.join(b','.join(row)+b'\n' for row in records)

    def values(self,columns,start_row=0,end_row=None):
        """Decode simple lexical fields in columns; complex CSV keeps its parser."""
        from itertools import islice
        from csv_projection import projector
        columns=tuple(columns);project=projector(columns,columns)
        for values,begin,end in self._selected(columns,start_row,end_row):
            count=end-begin
            if not values or count<=0:continue
            joined=[b'\0'.join(column[begin:end]) for column in values]
            simple=all(raw.count(b'\0')==count-1 and not any(c in raw for c in (b'"',b',',b'\r',b'\n')) for raw in joined)
            if simple:
                # Replace the block's byte columns rather than retaining both
                # representations. No samples escape into a persistent cache.
                for i,raw in enumerate(joined):values[i]=raw.decode('utf-8').split('\0')
                del joined
                for row in zip(*values):
                    # csv.reader skips a blank line, but not two empty fields.
                    if len(row)>1 or row[0]:yield project(row)
            else:
                del joined
                block=b''.join(b','.join(row)+b'\n' for row in islice(zip(*values),begin,end))
                for row in csv.reader(io.StringIO(block.decode('utf-8'),newline='')):
                    if row:yield project(row)

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


def values(path,columns,start_row=0,end_row=None):
    """Projected field values without a transient dictionary per numeric row."""
    path=Path(path)
    from csv_projection import projector
    if not path.is_file() and packed(path).is_file():
        reader=Reader(packed(path))
        yield from reader.values(columns,start_row,end_row)
    else:
        with path.open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.reader(stream);project=projector(next(reader,[]),columns);position=0
            for row in reader:
                if not row:continue
                if end_row is not None and position>=end_row:break
                if position>=start_row:yield project(row)
                position+=1


def rows(path,columns=None,start_row=0,end_row=None):
    path=Path(path)
    if not path.is_file() and packed(path).is_file():
        reader=Reader(packed(path));names=columns or reader.columns
        for block in reader.chunks(columns,start_row,end_row):
            yield from csv.DictReader(io.StringIO(block.decode('utf-8'),newline=''),fieldnames=names)
    else:
        with path.open(encoding='utf-8-sig',newline='') as stream:
            if not columns:reader=csv.DictReader(stream)
            else:
                raw=csv.reader(stream);positions={name:i for i,name in enumerate(next(raw,[]))}
                indexes=[positions.get(name) for name in columns]
                reader=({name:(row[index] if index is not None and index<len(row) else None if index is not None else '')
                         for name,index in zip(columns,indexes)} for row in raw if row)
            for i,row in enumerate(reader):
                if i<start_row:continue
                if end_row is not None and i>=end_row:break
                yield row


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
