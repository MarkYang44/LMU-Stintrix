"""Thread-owned Win32 hotkeys with blocking message waits and atomic remapping."""
import ctypes
from ctypes import wintypes
from queue import Queue,Empty
import threading
from shortcut_keys import parse


class Registration:
    def __init__(self,register,unregister):
        self.register=register;self.unregister=unregister;self.combos={};self.actions={};self.next_id=100
    def update(self,bindings):
        wanted={key:parse(text)[1:] for key,text in bindings.items() if text};added={}
        for action,combo in wanted.items():
            if combo in self.combos or combo in added:continue
            self.next_id+=1
            if self.next_id>0xBFFF:self.next_id=100
            while self.next_id in self.combos.values():self.next_id+=1
            if not self.register(self.next_id,*combo):
                for identifier in added.values():self.unregister(identifier)
                return dict(ok=False,action=action)
            added[combo]=self.next_id
        kept={combo:identifier for combo,identifier in self.combos.items() if combo in wanted.values()}
        for combo,identifier in self.combos.items():
            if combo not in kept:self.unregister(identifier)
        self.combos={**kept,**added};self.actions={self.combos[combo]:key for key,combo in wanted.items()}
        return dict(ok=True)
    def close(self):
        for identifier in self.combos.values():self.unregister(identifier)
        self.combos={};self.actions={}


class NativeHotkeys:
    def __init__(self):
        self.commands=Queue();self.results=Queue();self.events=Queue();self.ready=threading.Event();self.closed=False;self.error=None
        self.thread=threading.Thread(target=self.run,name='Stintrix shortcuts',daemon=True);self.thread.start()
        if not self.ready.wait(2):raise OSError('快捷键服务未就绪')
        if self.error:raise OSError(self.error)
    def run(self):
        registration=None
        try:
            self.user=ctypes.WinDLL('user32',use_last_error=True);kernel=ctypes.WinDLL('kernel32')
            kernel.GetCurrentThreadId.restype=wintypes.DWORD;self.thread_id=kernel.GetCurrentThreadId()
            self.user.PeekMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),ctypes.c_void_p,wintypes.UINT,wintypes.UINT,wintypes.UINT]
            self.user.GetMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),ctypes.c_void_p,wintypes.UINT,wintypes.UINT]
            self.user.GetMessageW.restype=ctypes.c_int
            self.user.RegisterHotKey.argtypes=[ctypes.c_void_p,ctypes.c_int,wintypes.UINT,wintypes.UINT]
            self.user.UnregisterHotKey.argtypes=[ctypes.c_void_p,ctypes.c_int]
            self.user.PostThreadMessageW.argtypes=[wintypes.DWORD,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
            msg=wintypes.MSG();self.user.PeekMessageW(ctypes.byref(msg),None,0,0,0)
            registration=Registration(lambda i,m,k:self.user.RegisterHotKey(None,i,m|0x4000,k),lambda i:self.user.UnregisterHotKey(None,i))
            self.ready.set()
            while self.user.GetMessageW(ctypes.byref(msg),None,0,0)>0:
                if msg.message==0x312:
                    action=registration.actions.get(msg.wParam)
                    if action:self.events.put(action)
                elif msg.message==0x8001:
                    while True:
                        try:bindings,callback=self.commands.get_nowait()
                        except Empty:break
                        self.results.put((callback,registration.update(bindings)))
        except (OSError,AttributeError) as error:self.error=str(error)
        finally:
            if registration:registration.close()
            self.ready.set()
    def configure(self,bindings,callback):
        if self.closed or not self.thread.is_alive():callback(dict(ok=False,action='',error='快捷键服务已停止'));return
        self.commands.put((bindings,callback))
        if not self.user.PostThreadMessageW(self.thread_id,0x8001,0,0):raise OSError('无法更新快捷键服务')
    def drain(self):
        while True:
            try:callback,result=self.results.get_nowait()
            except Empty:break
            callback(result)
        actions=[]
        while len(actions)<16:
            try:actions.append(self.events.get_nowait())
            except Empty:break
        return actions
    def close(self):
        if self.closed:return
        self.closed=True
        if self.thread.is_alive():self.user.PostThreadMessageW(self.thread_id,0x12,0,0);self.thread.join(1)
