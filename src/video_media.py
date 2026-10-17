"""Local FFmpeg adapter. Bounded pipes, actual selected PTS, no frame cache."""
from collections import deque
import io
import json
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading


class Cancelled(Exception):
    pass


def executable(name, directory=''):
    candidate=Path(directory)/(name+'.exe') if directory else None
    value=str(candidate) if candidate and candidate.is_file() else shutil.which(name)
    if not value:raise ValueError('未找到 '+name+'；请选择同时包含 ffmpeg 和 ffprobe 的文件夹')
    return value


def process(args, **kwargs):
    return subprocess.Popen(args,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),**kwargs)


def capture(args, cancel=None, timeout=30):
    p=process(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        # communicate drains both pipes, while short timeouts keep cancellation responsive.
        import time
        deadline=time.monotonic()+timeout
        while True:
            if cancel and cancel.is_set():raise Cancelled('已取消')
            try:
                out,err=p.communicate(timeout=.15);break
            except subprocess.TimeoutExpired:
                if time.monotonic()>deadline:raise ValueError('视频工具超时')
        if p.returncode:raise ValueError(err.decode('utf-8','replace')[-1800:])
        return out
    finally:
        if p.poll() is None:p.kill()
        p.communicate()


def probe(path, directory='', cancel=None):
    path=Path(path).resolve()
    if not path.is_file():raise ValueError('请选择本地视频文件')
    data=json.loads(capture([executable('ffprobe',directory),'-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height,duration,avg_frame_rate:format=duration','-of','json',str(path)],cancel))
    streams=data.get('streams',[])
    if not streams:raise ValueError('视频中没有画面流')
    stream=streams[0];w=int(stream['width']);h=int(stream['height'])
    duration=float(data.get('format',{}).get('duration') or stream.get('duration') or 0)
    if not 16<=w<=8192 or not 16<=h<=8192 or w*h>4096*2160 or duration<=0:
        raise ValueError('不支持的视频尺寸或时长；请使用不超过约 4K 的视频')
    return dict(width=w,height=h,duration=duration,path=str(path))


def preview(path, seconds, directory='', cancel=None):
    from PIL import Image
    data=capture([executable('ffmpeg',directory),'-v','error','-threads','2','-noautorotate','-ss',str(seconds),
        '-i',str(path),'-map','0:v:0','-frames:v','1','-vf',"scale='min(1120,iw)':-1",
        '-f','image2pipe','-vcodec','png','-threads','1','pipe:1'],cancel)
    with Image.open(io.BytesIO(data)) as image:return image.convert('RGB')


def frames(path, start, end, hz, crop, directory='', cancel=None):
    """Yield (video_pts_s, RGB ROI); never manufacture CFR timestamps."""
    from PIL import Image
    x,y,w,h=crop
    args=[executable('ffmpeg',directory),'-hide_banner','-nostdin','-loglevel','info','-threads','2',
          '-noautorotate','-ss',str(start),'-i',str(path),'-t',str(end-start),'-map','0:v:0','-an','-sn','-dn',
          '-vf',f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{1/hz-1e-6:.9f})',format=rgb24,crop={w}:{h}:{x}:{y},showinfo=checksum=0",
          '-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','-threads','1','pipe:1']
    p=process(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    stamps=queue.Queue(maxsize=4);errors=deque(maxlen=8);done=threading.Event()
    def read_log():
        for raw in iter(p.stderr.readline,b''):
            line=raw.decode('utf-8','replace');match=re.search(r'\bn:\s*\d+.*?pts_time:\s*([-+\d.eE]+)',line)
            if match:
                while not done.is_set():
                    try:stamps.put(float(match[1]),timeout=.1);break
                    except queue.Full:pass
            elif 'error' in line.lower() or 'invalid' in line.lower():errors.append(line.strip())
    def watch():
        while not done.wait(.1):
            if cancel and cancel.is_set():
                if p.poll() is None:p.kill()
                return
    log=threading.Thread(target=read_log,daemon=True);watcher=threading.Thread(target=watch,daemon=True)
    log.start();watcher.start();size=w*h*3
    try:
        previous=None
        while True:
            if cancel and cancel.is_set():raise Cancelled('已取消')
            raw=bytearray()
            while len(raw)<size:
                part=p.stdout.read(size-len(raw))
                if not part:break
                raw.extend(part)
            if not raw:break
            if len(raw)!=size:raise ValueError('视频帧不完整')
            try:pts=stamps.get(timeout=5)+start
            except queue.Empty:raise ValueError('无法读取视频帧时间戳') from None
            if previous is not None and pts<=previous:raise ValueError('视频时间戳不连续，请重新导出无剪辑视频')
            previous=pts
            yield pts,Image.frombytes('RGB',(w,h),bytes(raw))
        p.wait(timeout=10)
        if cancel and cancel.is_set():raise Cancelled('已取消')
        if p.returncode:raise ValueError('视频解码失败：'+' / '.join(errors))
    finally:
        done.set()
        if p.poll() is None:p.kill()
        p.wait();log.join(2);watcher.join(1);p.stdout.close();p.stderr.close()
