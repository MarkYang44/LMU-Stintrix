"""Read-only, bounded catalog of local video extraction results."""
import json
from pathlib import Path

SUMMARY='video_result_summary.json'
HEADERS={'format','version','id','created_utc','video_file','identity','mode','start_s','end_s','quality'}


def write_summary(folder,result):
    value={k:result[k] for k in HEADERS if k in result}
    (Path(folder)/SUMMARY).write_text(json.dumps(value,ensure_ascii=False,allow_nan=False),encoding='utf-8')


def header(path):
    # Bounded streaming prefix parser. Older results place rows last; stop at
    # its key without parsing sample arrays or creating temporary disk tables.
    with Path(path).open(encoding='utf-8-sig') as stream:
        text='';position=0;eof=False;decoder=json.JSONDecoder()
        def more():
            nonlocal text,eof
            if len(text)>=65536:raise ValueError('结果头过大')
            chunk=stream.read(min(4096,65536-len(text)));text+=chunk;eof=not chunk
        def space():
            nonlocal position
            while True:
                while position<len(text) and text[position].isspace():position+=1
                if position<len(text) or eof:return
                more()
        def require(char):
            nonlocal position
            space()
            if text[position:position+1]!=char:raise ValueError('结果头无效')
            position+=1
        def value():
            nonlocal position
            space()
            while True:
                try:v,end=decoder.raw_decode(text,position)
                except json.JSONDecodeError:
                    if eof:raise ValueError('结果头无效') from None
                    more();continue
                # A scalar number may continue in the next input chunk.
                if end==len(text) and not eof:more();continue
                position=end;return v
        require('{');out={}
        while True:
            space()
            if text[position:position+1]=='}':break
            key=value()
            if not isinstance(key,str):raise ValueError('结果头无效')
            require(':')
            if key=='rows':break
            item=value()
            if key in HEADERS:out[key]=item
            space();end=text[position:position+1];position+=1
            if end=='}':break
            if end!=',':raise ValueError('结果头无效')
    if out.get('format')!='stintrix.video-curves' or not isinstance(out.get('identity'),dict) or not isinstance(out.get('video_file'),str) or not isinstance(out.get('quality',{}),dict):
        raise ValueError('不是视频提取结果')
    return out


def file_in(folder,name,root):
    root=Path(root).resolve()/'VideoCurves';folder=Path(folder)
    if folder.is_symlink() or folder.is_junction() or folder.parent.resolve()!=root:return None
    file=folder/name
    if file.is_symlink() or file.is_junction() or not file.is_file() or not file.resolve().is_relative_to(root):return None
    return file


def inventory(root,limit=100):
    base=Path(root).resolve()/'VideoCurves'
    if not base.is_dir() or base.is_symlink() or base.is_junction():return []
    out=[]
    for folder in sorted(base.iterdir(),key=lambda p:p.name,reverse=True):
        if folder.name.startswith(('.', 'pending-')):continue
        curve=file_in(folder,'curve.json',root)
        if curve is None:continue
        try:
            meta=header(file_in(folder,SUMMARY,root) or curve)
            reports={k:str(file) for k,name in [('raw','report.html'),('smooth','report_120hz.html')] if (file:=file_in(folder,name,root))}
            if not reports:continue
            out.append(dict(meta,folder=str(folder),reports=reports))
        except (OSError,ValueError,TypeError,KeyError,RecursionError):continue
        if len(out)>=limit:break
    return out
