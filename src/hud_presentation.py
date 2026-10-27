"""Layout application touches windows only; never the engine or recorder settings."""
import ctypes
from hud_layouts import KINDS,SIZES,defaults,normalize


def visible(app,kind,fallback=True):
    if getattr(app,'simulator','lmu')=='ac_evo' and kind!='main':return False
    return bool(getattr(app,'layout_visibility',{}).get(kind,fallback)) and not getattr(app,'silent_recording',False) and not getattr(app,'presentation_hidden',False)


def windows(app):
    result={'main':app.root}
    for name in ('vehicle_panels','endurance_panels'):
        panels=getattr(app,name,None)
        if panels:result.update(panels.windows)
    return result


def capture(app):
    result=defaults()
    for kind in KINDS:
        if kind!='main':result['panels'][kind]['visible']=getattr(app,'layout_visibility',{}).get(kind,getattr(app,kind+'_on').get())
    result['panels']['main']['visible']=getattr(app,'layout_visibility',{}).get('main',True)
    for kind,window in windows(app).items():
        if window.winfo_exists():
            result['panels'][kind].update(x=window.winfo_x(),y=window.winfo_y(),width=window.winfo_width(),height=window.winfo_height(),opacity=float(window.attributes('-alpha')))
    # Keep a hidden panel's saved size/position even when it has not been created.
    for kind,panel in getattr(app,'layout_snapshot',{}).get('panels',{}).items():
        if kind not in windows(app):result['panels'][kind].update(panel)
    result.update(mode=app.hud_mode.get(),geometry_mode=app.hud_mode.get(),window=app.window.get(),topmost=app.top.get(),clickthrough=app.clickthrough)
    return normalize(result)


def bounds(root):
    if hasattr(ctypes,'WinDLL'):
        user=ctypes.WinDLL('user32');return tuple(user.GetSystemMetrics(i) for i in (76,77,78,79))
    return root.winfo_vrootx(),root.winfo_vrooty(),root.winfo_vrootwidth(),root.winfo_vrootheight()


def place(window,panel,kind,mode='normal'):
    x0,y0,sw,sh=bounds(window);minimum={'normal':(440,160),'curves':(240,60),'controls':(320,80)}[mode] if kind=='main' else SIZES[kind]
    w=max(minimum[0],min(panel['width'],max(minimum[0],sw)));h=max(minimum[1],min(panel['height'],max(minimum[1],sh)))
    x=max(x0,min(panel['x'],x0+sw-w));y=max(y0,min(panel['y'],y0+sh-h))
    window.geometry(f'{w}x{h}');window.update_idletasks()
    if hasattr(ctypes,'WinDLL'):
        user=ctypes.WinDLL('user32');user.GetParent.argtypes=[ctypes.c_void_p];user.GetParent.restype=ctypes.c_void_p
        user.SetWindowPos.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint]
        handle=user.GetParent(window.winfo_id()) or window.winfo_id();user.SetWindowPos(handle,None,x,y,w,h,0x14)
    else:window.geometry(f'{w}x{h}{x:+d}{y:+d}')
    window.attributes('-alpha',panel['opacity'])


def refresh(app):
    app.root.deiconify() if visible(app,'main') else app.root.withdraw()
    for name in ('vehicle_panels','endurance_panels'):
        panels=getattr(app,name,None)
        if panels:panels.refresh_visibility()


def apply(app,snapshot):
    snapshot=normalize(snapshot);app.layout_snapshot=snapshot
    panel=snapshot['panels']['main'];mode=snapshot['mode']
    if mode!='normal' and 'geometry_mode' not in snapshot and (panel['width'],panel['height']) in ((640,228),(440,170),(440,160),(840,300)):
        panel.update(width=600 if mode=='controls' else 440,height=100)
    app.layout_visibility={k:p['visible'] for k,p in snapshot['panels'].items()}
    app.hud_mode.set(snapshot['mode']);app.apply_clean_mode();app.window.set(snapshot['window'])
    app.top.set(snapshot['topmost']);app.root.attributes('-topmost',snapshot['topmost'])
    refresh(app)
    for kind,window in windows(app).items():place(window,snapshot['panels'][kind],kind,snapshot['mode'])
    if app.clickthrough!=snapshot['clickthrough']:app.toggle_clickthrough()
    app.chrome_key=None;app.trace_key=None;app.render_wake.set()


def toggle_visibility(app):
    if app.silent_recording:return False
    app.presentation_hidden=not getattr(app,'presentation_hidden',False);refresh(app);return True
