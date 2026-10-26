"""Validated global shortcuts; empty bindings explicitly disable an action."""
from race_model import read_json
from storage import atomic_json

DEFAULTS={'visibility':'Ctrl+Shift+F9','lock':'Ctrl+Shift+F10','center':'Ctrl+Shift+F11','layout':'Ctrl+Shift+F5'}
LABELS={'visibility':'显示 / 隐藏 HUD','lock':'鼠标穿透 / 解锁','center':'呼出控制中心','layout':'下一套 HUD 布局'}


def parse(text):
    if not isinstance(text,str):raise ValueError('快捷键必须是文字')
    if not text.strip():return '',0,0
    parts=[p.strip().upper() for p in text.split('+')];key=parts.pop();modifiers=set(parts)
    if len(parts)!=len(modifiers) or not modifiers or not modifiers<=set(('CTRL','SHIFT','ALT')):raise ValueError('快捷键需包含 Ctrl、Shift 或 Alt，不能重复修饰键')
    if key.startswith('F') and key[1:].isdigit() and 1<=int(key[1:])<=24:vk=111+int(key[1:])
    elif len(key)==1 and key.isascii() and key.isalnum():vk=ord(key)
    else:raise ValueError('快捷键末位需为字母、数字或 F1–F24')
    if key=='F12' or (modifiers=={'ALT'} and key=='F4'):raise ValueError('该组合为系统保留，请选择其他快捷键')
    names=[name for name in ('Ctrl','Alt','Shift') if name.upper() in modifiers]
    flags=sum({'CTRL':2,'ALT':1,'SHIFT':4}[m] for m in modifiers)
    return '+'.join([*names,key]),flags,vk


def validate(value):
    if not isinstance(value,dict) or not isinstance(value.get('enabled',True),bool):raise ValueError('快捷键设置无效')
    bindings=value.get('bindings',DEFAULTS)
    if not isinstance(bindings,dict):raise ValueError('快捷键设置无效')
    result={};seen=set()
    for key in DEFAULTS:
        text,mod,vk=parse(bindings.get(key,DEFAULTS[key]))
        if text and (mod,vk) in seen:raise ValueError('多个操作不能使用相同快捷键')
        if text:seen.add((mod,vk))
        result[key]=text
    return dict(version=1,enabled=value.get('enabled',True),bindings=result)


def load(root):
    path=root/'hotkey_settings.json'
    if path.exists() and path.stat().st_size>65536:raise ValueError('快捷键配置文件过大')
    return validate(read_json(path,{}))
def save(root,value):atomic_json(root/'hotkey_settings.json',validate(value))


def captured(keysym,state):
    """Tk key event to the same canonical syntax as manual entry."""
    if keysym in ('Control_L','Control_R','Shift_L','Shift_R','Alt_L','Alt_R','Meta_L','Meta_R'):return None
    mods=[name for name,mask in (('Ctrl',4),('Alt',0x20008),('Shift',1)) if state&mask]
    key=keysym.upper()
    if key.startswith('KP_') and len(key)==4 and key[-1].isdigit():key=key[-1]
    return parse('+'.join([*mods,key]))[0]


def legacy_state(app,key):
    """A modifier chord must never also fire the legacy single-F-key action."""
    state=app.user32.GetAsyncKeyState(key);down=bool(state&0x8000)
    blocked=getattr(app,'legacy_chord_keys',None)
    if blocked is None:blocked=app.legacy_chord_keys=set()
    if getattr(getattr(app,'shortcuts',None),'capture_owner',None) is not None:
        if down:blocked.add(key)
        return 0
    if any(app.user32.GetAsyncKeyState(mod)&0x8000 for mod in (0x10,0x11,0x12)) and down:blocked.add(key)
    if key in blocked:
        if not down:blocked.discard(key)
        return 0
    return state
