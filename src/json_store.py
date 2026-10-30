"""Incremental JSON with exact float64 scratch matrices and selective headers."""
import json,math,re
from pathlib import Path
from analysis_spool import DiskTable

_SPACE=re.compile(r'[ \t\r\n]*')
_TOKEN=re.compile(r'[^ \t\r\n,\]}]*')
# Batch only unselected simple rows. The standard decoder still validates every
# token, including big-integer limits and nonstandard constants. No whole matrix.
_ROW_BATCH=16384
_ROWS=re.compile(r'\[[^\[\]"{}]*\](?:[ \t\r\n]*,[ \t\r\n]*\[[^\[\]"{}]*\])*')

class Reader:
    def __init__(self,stream,directory=None,chunk_size=65536,fields=None):
        self.stream=stream;self.directory=directory;self.chunk_size=chunk_size
        self.fields=set(fields) if fields is not None else None
        self.buffer='';self.pos=0;self.eof=False;self.decoder=json.JSONDecoder()
    def fill(self):
        self.buffer=self.buffer[self.pos:];self.pos=0
        block=self.stream.read(self.chunk_size);self.buffer+=block;self.eof=not block
    def peek(self):
        while self.pos>=len(self.buffer) and not self.eof:self.fill()
        return self.buffer[self.pos:self.pos+1]
    def space(self):
        while True:
            if self.pos<len(self.buffer) and self.buffer[self.pos] not in ' \t\r\n':return
            self.pos=_SPACE.match(self.buffer,self.pos).end()
            if self.pos<len(self.buffer) or self.eof:return
            self.fill()
    def require(self,char):
        self.space()
        if self.peek()!=char:raise ValueError('Invalid JSON: expected '+char)
        self.pos+=1
    def scalar(self):
        if self.peek()=='"':
            while True:
                try:
                    value,end=self.decoder.raw_decode(self.buffer,self.pos)
                    self.pos=end;return value
                except json.JSONDecodeError:
                    if self.eof:raise ValueError('Invalid JSON string') from None
                    self.fill()
        # Wait for a delimiter so split exponents/numbers cannot decode partly.
        while True:
            end=_TOKEN.match(self.buffer,self.pos).end()
            if end<len(self.buffer) or self.eof:break
            self.fill()
        token=self.buffer[self.pos:end];self.pos=end
        if not token:raise ValueError('Invalid JSON value')
        try:return self.decoder.decode(token)
        except json.JSONDecodeError:raise ValueError('Invalid JSON value') from None
    def row(self,depth,keep):
        # Decode one numeric row in C, never the entire telemetry matrix.
        # Fall back for unusually large rows so the read buffer stays bounded.
        self.space()
        if self.peek()=='[':
            while len(self.buffer)-self.pos<=1048576:
                if not keep:
                    match=_ROWS.match(self.buffer,self.pos,min(len(self.buffer),self.pos+_ROW_BATCH))
                    if match is not None and match.group().count('[')>1:
                        try:self.decoder.raw_decode('['+match.group()+']')
                        except json.JSONDecodeError:raise ValueError('Invalid JSON row') from None
                        self.pos=match.end();return None
                try:
                    value,end=self.decoder.raw_decode(self.buffer,self.pos)
                    self.pos=end;return value if keep else None
                except json.JSONDecodeError:
                    if self.eof:raise ValueError('Invalid JSON row') from None
                    self.fill()
        return self.value('',depth,keep)
    def rows(self,depth,keep):
        # Decode bounded sibling rows in C. Each row still goes through the
        # original type/width checks and exact float64 scratch representation.
        if keep:
            self.space()
            if self.peek()=='[':
                match=_ROWS.match(self.buffer,self.pos,min(len(self.buffer),self.pos+_ROW_BATCH))
                if match is not None and match.group().count('[')>1:
                    try:value,_=self.decoder.raw_decode('['+match.group()+']')
                    except json.JSONDecodeError:raise ValueError('Invalid JSON row') from None
                    self.pos=match.end();return value
        return (self.row(depth,keep),)
    def value(self,key='',depth=0,keep=True):
        if depth>100:raise ValueError('JSON nesting exceeds 100')
        self.space();char=self.peek()
        if char=='{':
            self.pos+=1;result={};self.space()
            if self.peek()=='}':self.pos+=1;return result if keep else None
            while True:
                self.space()
                if self.peek()!='"':raise ValueError('Invalid JSON object key')
                name=self.scalar();self.require(':')
                selected=keep and (depth!=0 or self.fields is None or name in self.fields)
                item=self.value(name,depth+1,selected)
                if selected:result[name]=item
                self.space();end=self.peek();self.pos+=1
                if end=='}':return result if keep else None
                if end!=',':raise ValueError('Invalid JSON object separator')
        if char=='[':
            self.pos+=1;result=[];table=None;self.space()
            if self.peek()==']':self.pos+=1;return result if keep else None
            try:
                while True:
                    rows=self.rows(depth+1,keep) if key in ('data','points','profile') else (self.value('',depth+1,keep),)
                    pending=[]
                    for row in rows:
                        if keep:
                            numeric=isinstance(row,list) and bool(row) and all(x is None or
                                (type(x)==float and math.isfinite(x) or type(x)==int and abs(x)<=2**53) for x in row)
                            if table is None and not result and key in ('data','points','profile') and numeric:
                                table=DiskTable((),len(row),self.directory,nullable=True);table._sealed=False
                            if table is not None:
                                if numeric and len(row)==table.width:pending.append(row)
                                else:
                                    table.extend(pending);pending=[]
                                    table.seal();result=list(table);table.close();table=None;result.append(row)
                            else:result.append(row)
                    if pending:table.extend(pending)
                    self.space();end=self.peek();self.pos+=1
                    if end==']':return table.seal() if table is not None else result if keep else None
                    if end!=',':raise ValueError('Invalid JSON array separator')
            except BaseException:
                if table is not None:table.close()
                raise
        value=self.scalar();return value if keep else None

def _metadata_only(value,depth=0):
    if depth>100:raise ValueError('JSON nesting exceeds 100')
    # Flat tags/options keep standard JSON types; matrices still use exact
    # float64 scratch tables and the bounded streaming parser.
    if isinstance(value,list):return all(not isinstance(item,(dict,list)) for item in value)
    return not isinstance(value,dict) or all(_metadata_only(item,depth+1) for item in value.values())


def load(path,fields=None,chunk_size=65536):
    """Large numeric arrays spill next to the source; no permanent format change."""
    path=Path(path)
    if fields is not None:fields=set(fields)
    with path.open(encoding='utf-8-sig') as stream:
        # Small headers use the standard C decoder, without building scratch
        # directories or resolving game preferences. Arrays retain the bounded
        # streaming/table reader and its existing numeric representation.
        if path.stat().st_size<=65536:
            text=stream.read(65537)
            if len(text)<=65536:
                value=json.loads(text)
                if _metadata_only(value):
                    return {k:v for k,v in value.items() if k in fields} if fields is not None and isinstance(value,dict) else value
            stream.seek(0)
        from paths import data_directory
        scratch=data_directory()/'_work'
        if fields is None:scratch.mkdir(parents=True,exist_ok=True)
        reader=Reader(stream,scratch,chunk_size,fields);value=reader.value();reader.space()
        if reader.peek():raise ValueError('Trailing JSON content')
        return value
