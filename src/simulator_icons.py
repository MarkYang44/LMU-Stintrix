"""Read installed game icons locally; never redistribute game artwork."""
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=2)
def source(game):
    from paths import discover_game
    folder=discover_game(game)
    if folder is None:return None
    for name in (('evo.ico','AssettoCorsaEVO.exe') if game=='ac_evo' else ('Le Mans Ultimate.exe',)):
        path=folder/name
        if path.is_file():return path
    return None


def executable_icon(path,size):
    import ctypes as C
    from ctypes import wintypes as W
    from PIL import Image
    class Info(C.Structure):
        _fields_=[('hIcon',W.HICON),('iIcon',C.c_int),('attributes',W.DWORD),('name',W.WCHAR*260),('kind',W.WCHAR*80)]
    class Header(C.Structure):
        _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),('bits',W.WORD),('compression',W.DWORD),('image_size',W.DWORD),('x',W.LONG),('y',W.LONG),('used',W.DWORD),('important',W.DWORD)]
    user=C.WinDLL('user32');gdi=C.WinDLL('gdi32');shell=C.WinDLL('shell32')
    shell.SHGetFileInfoW.argtypes=[W.LPCWSTR,W.DWORD,C.POINTER(Info),W.UINT,W.UINT];shell.SHGetFileInfoW.restype=C.c_size_t
    user.DestroyIcon.argtypes=[W.HICON];user.DrawIconEx.argtypes=[W.HDC,C.c_int,C.c_int,W.HICON,C.c_int,C.c_int,W.UINT,W.HBRUSH,W.UINT]
    gdi.CreateCompatibleDC.argtypes=[W.HDC];gdi.CreateCompatibleDC.restype=W.HDC
    gdi.CreateDIBSection.argtypes=[W.HDC,C.POINTER(Header),W.UINT,C.POINTER(C.c_void_p),W.HANDLE,W.DWORD];gdi.CreateDIBSection.restype=W.HBITMAP
    gdi.SelectObject.argtypes=[W.HDC,W.HANDLE];gdi.SelectObject.restype=W.HANDLE
    gdi.DeleteObject.argtypes=[W.HANDLE];gdi.DeleteDC.argtypes=[W.HDC]
    info=Info();dc=bitmap=old=None
    if not shell.SHGetFileInfoW(str(path),0,C.byref(info),C.sizeof(info),0x100):raise OSError('Game icon unavailable')
    try:
        dc=gdi.CreateCompatibleDC(None);bits=C.c_void_p();header=Header(C.sizeof(Header),size,-size,1,32,0,size*size*4,0,0,0,0)
        bitmap=gdi.CreateDIBSection(dc,C.byref(header),0,C.byref(bits),None,0)
        if not dc or not bitmap or not bits.value:raise OSError('Icon surface unavailable')
        old=gdi.SelectObject(dc,bitmap);C.memset(bits,0,size*size*4)
        if not user.DrawIconEx(dc,0,0,info.hIcon,size,size,0,None,3):raise OSError('Game icon decode failed')
        return Image.frombytes('RGBA',(size,size),C.string_at(bits,size*size*4),'raw','BGRA')
    finally:
        if old:gdi.SelectObject(dc,old)
        if bitmap:gdi.DeleteObject(bitmap)
        if dc:gdi.DeleteDC(dc)
        if info.hIcon:user.DestroyIcon(info.hIcon)


@lru_cache(maxsize=8)
def pixels(game,size,path,stamp):
    from PIL import Image,ImageDraw,ImageFont,ImageOps
    if path:
        try:
            if Path(path).suffix.lower()=='.ico':
                with Image.open(path) as image:return ImageOps.contain(image.convert('RGBA'),(size,size),Image.Resampling.LANCZOS)
            return executable_icon(path,size)
        except (OSError,ValueError,AttributeError):pass
    image=Image.new('RGBA',(size,size));draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((0,0,size-1,size-1),radius=max(1,size//8),fill='#292929',outline='#c8ce42')
    try:font=ImageFont.truetype('segoeuib.ttf',max(8,size//3))
    except OSError:font=ImageFont.load_default(size=max(8,size//3))
    draw.text((size/2,size/2),'EVO' if game=='ac_evo' else 'LMU',anchor='mm',fill='#f0f0e8',font=font)
    return image


def load(master,size):
    from PIL import ImageTk
    images={}
    for game in ('lmu','ac_evo'):
        path=source(game)
        try:stamp=(path.stat().st_size,path.stat().st_mtime_ns) if path else None
        except OSError:path=None;stamp=None
        images[game]=ImageTk.PhotoImage(pixels(game,size,str(path) if path else None,stamp),master=master)
    return images
