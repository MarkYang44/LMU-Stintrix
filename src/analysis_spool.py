"""Lossless, bounded-memory scratch tables for offline analysis. Files auto-close."""
from collections import OrderedDict
from collections.abc import Sequence
from functools import partial
import math,struct,tempfile,sys
from buffers import CompactRow


def _sparse_pack(record,*row):
    if None in row:row=(math.nan if v is None else v for v in row)
    return record.pack(*row)

class Slice(Sequence):
    def __init__(self,source,indices):self.source,self.indices=source,indices
    def __len__(self):return len(self.indices)
    def __iter__(self):
        if self.indices.step==1 and hasattr(self.source,'iter_range'):
            yield from self.source.iter_range(self.indices.start,self.indices.stop)
        else:
            for index in self.indices:yield self.source[index]
    def __getitem__(self,index):
        if isinstance(index,slice):return Slice(self.source,self.indices[index])
        return self.source[self.indices[index]]
    def project(self,columns):
        method=getattr(self.source,'project',None)
        return Slice(method(columns),self.indices) if method is not None else self

class Column(Sequence):
    """Zero-copy column view for bisect and chronological lookup."""
    def __init__(self,source,index=0,offset=0):self.source,self.index,self.offset=source,index,offset
    def __len__(self):return len(self.source)
    def __iter__(self):
        for row in self.source:yield row[self.index]-self.offset
    def __getitem__(self,index):
        if isinstance(index,slice):return Slice(self,range(len(self))[index])
        return self.source[index][self.index]-self.offset

class DiskTable(Sequence):
    """Float64 records; two random-read pages plus one block per active iterator."""
    def __init__(self,rows,width,directory=None,nullable=False):
        self.width=width;self.nullable=nullable;self.record=struct.Struct('<'+str(width)+'d');self._pack=self.record.pack
        self._file=tempfile.TemporaryFile(dir=directory);self._cache=OrderedDict();self._size=0;self._sealed=False
        self.page_rows=max(1,65536//self.record.size)
        try:
            append=self.append
            if getattr(append,'__func__',None) is not __class__.append or self.record.size>=65536:
                for row in rows:append(row)
            else:self._build(rows)
            self.seal()
        except BaseException:self.close();raise
    def _build(self,rows):
        # Construction has no read cache; buffer at most 64 KiB plus one row.
        pending=bytearray();pack=self._pack;write=self._file.write;width=self.width
        try:
            for row in rows:
                if len(row)!=width:raise ValueError('Scratch row width changed')
                try:block=pack(*row)
                except (TypeError,struct.error):
                    if not any(v is None for v in row):raise
                    pack=partial(_sparse_pack,self.record);self._pack=pack;block=pack(*row)
                pending.extend(block);self._size+=1
                if len(pending)>=65536:
                    try:write(pending)
                    except BaseException:pending.clear();raise
                    pending.clear()
        finally:
            if pending:write(pending)
    def extend(self,rows):
        """Append a bounded input batch, retaining append overrides and prefix errors."""
        if self._sealed:raise ValueError('Scratch table is sealed')
        end=self._size*self.record.size
        if self._file.tell()!=end:self._file.seek(end)
        self._cache.clear()
        append=self.append
        if getattr(append,'__func__',None) is not __class__.append or self.record.size>=65536:
            for row in rows:append(row)
        else:self._build(rows)
    def append(self,row):
        if len(row)!=self.width:raise ValueError('Scratch row width changed')
        if self._sealed:raise ValueError('Scratch table is sealed')
        # Numeric scratch rows go straight through struct's C implementation.
        # Sparse rows keep the original None -> NaN wire representation.
        try:block=self._pack(*row)
        except (TypeError,struct.error):
            if not any(v is None for v in row):raise
            # Remember sparse encoding without binding this table into a cycle;
            # only the immutable Struct is retained, so scratch files auto-close.
            self._pack=partial(_sparse_pack,self.record);block=self._pack(*row)
        self._file.write(block);self._size+=1
        self._cache.clear()
    def seal(self):self._file.flush();self._sealed=True;return self
    def append_packed(self,block):
        """Internal exact float64 row, already encoded in this table's wire order."""
        if len(block)!=self.record.size:raise ValueError('Scratch row width changed')
        if self._sealed:raise ValueError('Scratch table is sealed')
        self._file.write(block);self._size+=1;self._cache.clear()
    def __len__(self):return self._size
    def __iter__(self):
        yield from self.iter_range()
    def iter_range(self,start=0,stop=None):
        # Sequential consumers need neither per-row seeks nor LRU updates.
        # Each iterator owns one small byte block; nested/random reads are safe.
        if not self._sealed:self._file.flush()
        position=start
        while position<(self._size if stop is None else min(stop,self._size)):
            count=min(self.page_rows,(self._size if stop is None else min(stop,self._size))-position)
            self._file.seek(position*self.record.size);block=self._file.read(count*self.record.size)
            if len(block)!=count*self.record.size:raise ValueError('Incomplete scratch table')
            for values in self.record.iter_unpack(block):
                yield [None if math.isnan(v) else v for v in values] if self.nullable else list(values)
            position+=count
    def __getitem__(self,index):
        if isinstance(index,slice):return Slice(self,range(self._size)[index])
        if index<0:index+=self._size
        if not 0<=index<self._size:raise IndexError(index)
        if not self._sealed:self._file.flush()
        page=index//self.page_rows
        block=self._cache.pop(page,None)
        if block is None:
            self._file.seek(page*self.page_rows*self.record.size);block=self._file.read(self.page_rows*self.record.size)
        self._cache[page]=block
        while len(self._cache)>2:self._cache.popitem(last=False)
        result=list(self.record.unpack_from(block,(index%self.page_rows)*self.record.size))
        return [None if math.isnan(v) else v for v in result] if self.nullable else result
    def close(self):
        file=getattr(self,'_file',None)
        if file:file.close();self._file=None
        cache=getattr(self,'_cache',None)
        if cache is not None:cache.clear()
    def __del__(self):self.close()

class _Columns(Sequence):
    """Decode selected float64 cells in C while retaining the original row stride."""
    def __init__(self,source,indices):
        self.source=source;self.indices=indices
        selected=sorted(set(indices));positions={v:i for i,v in enumerate(selected)}
        self.order=[positions[i] for i in indices];self.reorder=indices!=selected
        pieces=['<'];cursor=0
        for index in selected:
            if index*8>cursor:pieces.append(str(index*8-cursor)+'x')
            pieces.append('d');cursor=index*8+8
        if cursor<source.record.size:pieces.append(str(source.record.size-cursor)+'x')
        self.record=struct.Struct(''.join(pieces))
    def __len__(self):return len(self.source)
    def __getitem__(self,index):
        if isinstance(index,slice):return Slice(self,range(len(self))[index])
        row=self.source[index];return [row[i] for i in self.indices]
    def iter_range(self,start=0,stop=None):
        source=self.source
        if not source._sealed:source._file.flush()
        position=start
        while position<(len(source) if stop is None else min(stop,len(source))):
            count=min(source.page_rows,(len(source) if stop is None else min(stop,len(source)))-position)
            source._file.seek(position*source.record.size);block=source._file.read(count*source.record.size)
            if len(block)!=count*source.record.size:raise ValueError('Incomplete scratch table')
            for row in self.record.iter_unpack(block):
                yield [row[i] for i in self.order] if self.reorder else row
            position+=count


class _LapProjection(Sequence):
    def __init__(self,source,columns):
        self.source=source;self.directory=source.directory
        wanted=set(columns);keys=[k for k in source.layout if k in wanted]
        self.layout={k:i for i,k in enumerate(keys)}
        self.table=_Columns(source.table,[*[source.layout[k] for k in keys],source.table.width-2,source.table.width-1])
    def __len__(self):return len(self.source)
    def __iter__(self):yield from self.iter_range()
    def iter_range(self,start=0,stop=None):yield from self.source._iter_rows(self.table,self.layout,start,stop)
    def __getitem__(self,index):
        if isinstance(index,slice):return Slice(self,range(len(self))[index])
        row=self.source[index]
        return CompactRow(self.layout,[row.values[row.layout[k]] for k in self.layout],row.utc)
    def project(self,columns):return _LapProjection(self.source,[k for k in self.layout if k in columns])


def project_rows(rows,columns):
    """Other mappings keep their original path; no data or precision is discarded."""
    method=getattr(rows,'project',None)
    return method(columns) if method is not None else rows


class _NumericProjection(Sequence):
    """Read-only numeric view; explicitly omits unused UTC text and array copies."""
    def __init__(self,source,columns):
        self.source=source;self.directory=source.directory
        wanted=set(columns);keys=[k for k in source.layout if k in wanted]
        self.layout={k:i for i,k in enumerate(keys)}
        self.table=_Columns(source.table,[source.layout[k] for k in keys])
    def __len__(self):return len(self.source)
    def row(self,values):
        row=object.__new__(CompactRow);row.layout=self.layout;row.values=values;row.utc=''
        return row
    def __iter__(self):yield from self.iter_range()
    def iter_range(self,start=0,stop=None):
        for values in self.table.iter_range(start,stop):yield self.row(values)
    def __getitem__(self,index):
        if isinstance(index,slice):return Slice(self,range(len(self))[index])
        return self.row(self.table[index])
    def project(self,columns):return _NumericProjection(self.source,[k for k in self.layout if k in columns])


def numeric_rows(rows,columns):
    """Only for numeric consumers. Ordinary projection still preserves UTC."""
    if isinstance(rows,Slice):return Slice(numeric_rows(rows.source,columns),rows.indices)
    if isinstance(rows,(_LapProjection,_NumericProjection)):return _NumericProjection(rows.source,[k for k in rows.layout if k in columns])
    if isinstance(rows,LapRows) and rows.table is not None:return _NumericProjection(rows,columns)
    return project_rows(rows,columns)


class LapRows(Sequence):
    """Spill exact compact rows plus variable UTF-8 UTC text, including missing fields."""
    def __init__(self,directory):
        self.directory=directory;self.layout=None;self.table=None;self.utc=tempfile.TemporaryFile(dir=directory)
    def __len__(self):return len(self.table) if self.table is not None else 0
    def __iter__(self):
        yield from self.iter_range()
    def iter_range(self,start=0,stop=None):
        if self.table is None:return
        yield from self._iter_rows(self.table,self.layout,start,stop)
    def _iter_rows(self,table,layout,start=0,stop=None):
        block=b'';first=0
        for row in table.iter_range(start,stop):
            offset=int(row[-2]);length=int(row[-1]);end=offset+length
            if not first<=offset<=end<=first+len(block):
                self.utc.seek(offset);block=self.utc.read(max(65536,length));first=offset
            yield CompactRow(layout,row[:-2],block[offset-first:end-first].decode('utf-8'))
    def project(self,columns):return _LapProjection(self,columns) if self.table is not None else self
    def append(self,row):
        if self.table is None:
            self.layout=row.layout;self.table=DiskTable((),len(self.layout)+2,self.directory);self.table._sealed=False
        if row.layout!=self.layout:raise ValueError('Telemetry layout changed within lap')
        text=row.utc.encode('utf-8');offset=self.utc.tell();self.utc.write(text)
        if sys.byteorder=='little':self.table.append_packed(row.values.tobytes()+struct.pack('<2d',offset,len(text)))
        else:self.table.append([*row.values,offset,len(text)])
    def seal(self):
        if self.table is not None:self.table.seal()
        self.utc.flush();return self
    def __getitem__(self,index):
        if isinstance(index,slice):return Slice(self,range(len(self))[index])
        row=self.table[index];self.utc.seek(int(row[-2]));utc=self.utc.read(int(row[-1])).decode('utf-8')
        return CompactRow(self.layout,row[:-2],utc)
    def close(self):
        if self.table is not None:self.table.close()
        if self.utc:self.utc.close();self.utc=None
    def __del__(self):
        if hasattr(self,'utc'):self.close()

def median(values):
    """Exact in-place selection on a float64 array; no sorted Python float list."""
    n=len(values)
    if not n:raise ValueError('Median requires data')
    k=n//2;lo=0;hi=n-1
    while lo<hi:
        pivot=values[(lo+hi)//2];lt=lo;i=lo;gt=hi
        while i<=gt:
            if values[i]<pivot:values[lt],values[i]=values[i],values[lt];lt+=1;i+=1
            elif values[i]>pivot:values[i],values[gt]=values[gt],values[i];gt-=1
            else:i+=1
        if k<lt:hi=lt-1
        elif k>gt:lo=gt+1
        else:break
    return values[k] if n%2 else (values[k]+max(values[i] for i in range(k)))/2
