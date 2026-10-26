"""GUI-thread command dispatch; global hotkeys never stop or restart recording."""
import os
import tkinter as tk
from pathlib import Path
import shortcut_keys
from i18n import tr


class DisabledService:
    def configure(self,bindings,done):done(dict(ok=True))
    def drain(self):return []
    def close(self):pass


class UnavailableService(DisabledService):
    def configure(self,bindings,done):done(dict(ok=not bool(bindings),action='',error='全局快捷键服务不可用'))


class ShortcutService:
    def __init__(self,root,hud,show,notify=lambda message:None):
        self.root=Path(root);self.hud=hud;self.show=show;self.notify=notify;self.message='';self.closed=False;self.capture_owner=None;self.conflict_action=None
        try:self.settings=shortcut_keys.load(self.root)
        except ValueError as error:self.settings=shortcut_keys.validate(dict(enabled=False));self.message=str(error)
        try:
            from native_hotkeys import NativeHotkeys
            self.native=DisabledService() if os.environ.get('LMU_STINTRIX_HOTKEYS')=='0' else NativeHotkeys()
        except OSError as error:self.native=UnavailableService();self.message=str(error)
        self.native.configure(self.settings['bindings'] if self.settings['enabled'] else {},self.started)
    def started(self,result):
        if not result['ok']:self.message=result.get('error','快捷键被占用：')+self.settings['bindings'].get(result.get('action'),'')
        elif not self.message:self.message='全局快捷键已启用' if self.settings['enabled'] else '全局快捷键已禁用'
    def message_text(self):
        prefix='快捷键被占用：'
        return tr(prefix)+self.message[len(prefix):] if self.message.startswith(prefix) else tr(self.message)
    def configure(self,settings,done):
        if self.capture_owner is not None:raise ValueError('请先结束快捷键录入')
        checked=shortcut_keys.validate(settings);before=self.settings
        self.conflict_action=None
        def finish(result):
            if self.closed:return
            if not result['ok']:
                self.conflict_action=result.get('action')
                self.message=result.get('error','快捷键被占用：')+checked['bindings'].get(result.get('action'),'');done(False,self.message_text());return
            try:shortcut_keys.save(self.root,checked)
            except OSError as error:
                self.native.configure(before['bindings'] if before['enabled'] else {},lambda result:None)
                done(False,str(error));return
            self.settings=checked;self.message='快捷键已保存' if checked['enabled'] else '全局快捷键已禁用';done(True,self.message_text())
        self.native.configure(checked['bindings'] if checked['enabled'] else {},finish)
    def begin_capture(self,owner,done):
        if self.capture_owner is not None:raise ValueError('请先结束快捷键录入')
        self.capture_owner=owner
        def ready(result):
            if self.capture_owner is not owner:return
            if not result['ok']:self.capture_owner=None
            done(result['ok'])
        try:self.native.configure({},ready)
        except OSError:self.capture_owner=None;raise
    def end_capture(self,owner,failed=lambda message:None):
        if self.capture_owner is not owner:return
        # Queue restoration even if the release command has not completed yet.
        def restored(result):
            if self.closed:return
            self.started(result)
            if not result['ok']:self.notify(self.message_text());failed(self.message_text())
        try:self.native.configure(self.settings['bindings'] if self.settings['enabled'] else {},restored)
        finally:self.capture_owner=None
    def invoke(self,action):
        if self.capture_owner is not None:return
        if action=='center':self.show();return
        hud=self.hud()
        if action=='layout':
            from layout_actions import next_layout
            self.notify(tr('当前布局：')+next_layout(self.root,hud));return
        if hud is None or hud.closing:self.notify(tr('请先启动记录'));return
        if action=='visibility':
            from hud_presentation import toggle_visibility
            if not toggle_visibility(hud):self.notify(tr('静默记录中，请在控制中心关闭静默模式'))
            else:self.notify(tr('HUD 已隐藏，继续记录' if hud.presentation_hidden else 'HUD 已恢复显示'))
        elif action=='lock':hud.toggle_clickthrough();self.notify(tr('HUD 已锁定并穿透' if hud.clickthrough else 'HUD 已解锁'))
    def drain(self):
        if self.closed:return
        for action in self.native.drain():
            try:self.invoke(action)
            except (OSError,ValueError,tk.TclError) as error:self.notify(str(error))
    def close(self):
        if not self.closed:self.closed=True;self.native.close()
