"""One independent read worker and a bounded, stamp-keyed PNG cache."""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def stamp(path):
    path=Path(path).resolve();s=path.stat();return str(path),s.st_size,s.st_mtime_ns,s.st_ctime_ns


def read_image(key):
    from PIL import Image
    with Path(key[0]).open('rb') as stream:
        image=Image.open(stream,formats=('PNG',));image.load()
    if stamp(key[0])!=key:raise OSError('图片正在更新，请重试读取')
    return image


class ImageLoader:
    def __init__(self,limit=64*1024*1024):
        self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='Stintrix-image');self.cache=OrderedDict();self.limit=limit;self.future=None;self.loading=None;self.wanted=None;self.closed=False
    def request(self,path):
        if self.closed:return None
        self.wanted=stamp(path)
        if self.wanted in self.cache:self.cache.move_to_end(self.wanted);return self.cache[self.wanted]
        self.begin();return None
    def begin(self):
        if not self.closed and self.future is None and self.wanted is not None:
            self.loading=self.wanted;self.future=self.pool.submit(read_image,self.loading)
    def remember(self,key,image):
        for old in list(self.cache):
            if old[0]==key[0]:self.cache.pop(old)
        self.cache[key]=image
        size=lambda:sum(im.width*im.height*len(im.getbands()) for im in self.cache.values())
        while len(self.cache)>2 or len(self.cache)>1 and size()>self.limit:self.cache.popitem(last=False)
    def poll(self):
        if self.closed:return None,None
        if self.future is not None and self.future.done():
            future,key=self.future,self.loading;self.future=None;self.loading=None
            try:image=future.result();error=None;self.remember(key,image)
            except Exception as e:image=None;error=str(e)
            if key==self.wanted:return image,error
        if self.wanted in self.cache:return self.cache[self.wanted],None
        self.begin();return None,None
    def forget(self,path):
        path=str(Path(path).resolve())
        for key in list(self.cache):
            if key[0]==path:self.cache.pop(key)
    def cancel(self):self.wanted=None
    def close(self):
        self.closed=True;self.wanted=None;self.cache.clear();self.pool.shutdown(wait=False,cancel_futures=True)
