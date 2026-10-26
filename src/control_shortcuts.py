"""Combination-key recording with per-row feedback and transactional registration."""
import tkinter as tk
from control_fields import Field
from control_widgets import Switch
from control_theme import T
from shortcut_keys import LABELS,DEFAULTS,parse,captured
from i18n import tr
import control_confirm


def show(app):
    old=getattr(app,'shortcut_window',None)
    if old is not None and old.winfo_exists():old.deiconify();old.lift();return old
    window=tk.Toplevel(app.root);app.shortcut_window=window;window.title(tr('全局快捷键'));window.configure(bg=T.BG);window.geometry('790x615');window.minsize(710,510)
    from control_video_widgets import ScrollPage
    scroll=ScrollPage(window);scroll.pack(fill='both',expand=True);window.bind('<MouseWheel>',lambda e:scroll.wheel(e.delta))
    body=tk.Frame(scroll.body,bg=T.CARD);body.pack(fill='both',expand=True,padx=16,pady=16)
    remembered=getattr(app,'shortcut_draft',None) or app.shortcuts.settings
    enabled=tk.BooleanVar(window,value=remembered['enabled']);status=tk.StringVar(window,value=app.shortcuts.message_text());dirty=tk.StringVar(window);fields={};hints={};recorders={};traces=[]
    state={'recording':None,'binding':None,'focus':None,'busy':False};owner=object()
    Switch(body,'启用全局快捷键',enabled,lambda:None,compact=True).pack(anchor='w',pady=(0,8))
    app.label(body,'点击“录入”后按组合键，Esc 取消；也可手动填写。清除后保存可禁用单项。',9,T.MUTED).pack(fill='x',pady=6)
    def errors():
        problems={};seen={}
        for key,value in fields.items():
            try:
                text,mods,vk=parse(value.get())
                if text and (mods,vk) in seen:problems[key]=problems[seen[(mods,vk)]]='多个操作不能使用相同快捷键'
                elif text:seen[(mods,vk)]=key
            except ValueError as error:problems[key]=str(error)
        return problems
    def validate(*_):
        problems=errors()
        for key,hint in hints.items():
            if key==state['recording']:continue
            hint.set(tr(problems.get(key,'保存后生效' if fields[key].get()!=app.shortcuts.settings['bindings'][key] else '未绑定' if not fields[key].get() else '当前组合')))
        dirty.set(tr('有未保存修改' if is_dirty() else '快捷键与已保存值一致'));return problems
    def snapshot():return dict(enabled=enabled.get(),bindings={k:v.get() for k,v in fields.items()})
    def is_dirty():return snapshot()!=dict(enabled=app.shortcuts.settings['enabled'],bindings=app.shortcuts.settings['bindings'])
    def stop_capture():
        key=state['recording'];state['recording']=None
        if state['binding']:window.unbind('<KeyPress>',state['binding']);state['binding']=None
        if state['focus']:window.unbind('<FocusOut>',state['focus']);state['focus']=None
        try:app.shortcuts.end_capture(owner,lambda message:status.set(message) if window.winfo_exists() else None)
        except OSError as error:status.set(str(error))
        if key is not None and window.winfo_exists():validate();recorders[key].configure(text=tr('录入'))
    def start_capture(key):
        if state['busy']:return
        stop_capture();state['recording']=key;recorders[key].configure(text=tr('取消录入'));hints[key].set(tr('正在准备录入…'))
        def ready(ok):
            if not window.winfo_exists() or state['recording']!=key:return
            if not ok:stop_capture();status.set(tr('全局快捷键服务不可用'));return
            hints[key].set(tr('请按组合键 · Esc 取消'));recorders[key].focus_set()
            state['binding']=window.bind('<KeyPress>',key_pressed,add='+')
            state['focus']=window.bind('<FocusOut>',focus_changed,add='+')
        try:app.shortcuts.begin_capture(owner,ready)
        except (ValueError,OSError) as error:stop_capture();status.set(tr(str(error)))
    def focus_changed(_):
        def check():
            if window.winfo_exists() and state['recording'] is not None:
                try:focus=window.focus_get()
                except KeyError:focus=None
                if focus is not recorders[state['recording']]:stop_capture()
        window.after_idle(check)
    def key_pressed(event):
        key=state['recording']
        if key is None:return
        if event.keysym=='Escape':stop_capture();return 'break'
        try:value=captured(event.keysym,event.state)
        except ValueError as error:hints[key].set(tr(str(error)));return 'break'
        if value is not None:
            fields[key].set(value);stop_capture();status.set(tr('组合键已录入，保存后生效'))
        return 'break'
    for key,label in LABELS.items():
        tile=tk.Frame(body,bg=T.CARD);tile.pack(fill='x',pady=5)
        row=app.row(tile);row.columnconfigure(0,weight=1)
        app.label(row,label,10).grid(row=0,column=0,sticky='w',padx=(0,12))
        value=tk.StringVar(window,value=remembered['bindings'][key]);fields[key]=value;Field(row,textvariable=value,width=22).grid(row=0,column=1,sticky='ew')
        def record(k=key):
            if state['recording']==k:stop_capture()
            else:start_capture(k)
        actions=tk.Frame(row,bg=T.CARD);actions.grid(row=0,column=2,padx=(8,0))
        button=app.button(actions,'录入',record,False,78);recorders[key]=button
        app.button(actions,'清除',lambda k=key:(stop_capture(),fields[k].set('')),False,65)
        hint=tk.StringVar(window);hints[key]=hint;app.label(tile,hint,9,T.MUTED).pack(anchor='w',pady=(0,3))
    app.label(body,'显示与布局操作不会停止记录。原 F6–F11 单键操作保留；F12 为系统保留，不支持绑定。',9,T.MUTED).pack(fill='x',pady=10)
    footer=tk.Frame(window,bg=T.BG);footer.pack(side='bottom',fill='x',padx=16,pady=10);app.label(footer,dirty,9,T.MUTED).pack(fill='x');row=app.row(footer)
    def save(on_success=None):
        if state['busy']:return
        stop_capture();problems=validate()
        if problems:status.set(tr(next(iter(problems.values()))));return
        state['busy']=True;button.configure(state='disabled')
        def done(ok,message):
            state['busy']=False
            if window.winfo_exists():
                button.configure(state='normal');validate();status.set(tr(message))
                if not ok and app.shortcuts.conflict_action in hints:hints[app.shortcuts.conflict_action].set(tr(message))
                if ok:
                    app.shortcut_draft=None
                    if on_success:
                        if not is_dirty():on_success()
                        else:status.set(tr('保存期间又有新修改，请确认后再关闭。'))
        try:app.shortcuts.configure(dict(enabled=enabled.get(),bindings={k:v.get() for k,v in fields.items()}),done)
        except (ValueError,OSError) as error:state['busy']=False;button.configure(state='normal');status.set(tr(str(error)))
    button=app.button(row,'保存快捷键',save,True,140)
    def defaults():
        stop_capture()
        def fill():
            for key,value in fields.items():value.set(DEFAULTS[key])
            status.set(tr('已填入推荐组合，保存后生效'))
        if is_dirty():
            answer=control_confirm.draft_choice(window,save_label='保存快捷键')
            if answer=='cancel':return
            if answer=='save':save(fill);return
        fill()
    app.button(row,'填入推荐组合',defaults,False,150)
    feedback=app.label(footer,status,9,T.ACCENT);feedback.pack(fill='x',pady=5);feedback.bind('<Configure>',lambda e:feedback.configure(wraplength=max(100,e.width)))
    def close(after=None,exiting=False):
        if state['busy']:status.set(tr('正在保存，请稍候'));return
        stop_capture()
        def finish():
            window.destroy()
            if after:after()
        if is_dirty():
            answer=control_confirm.draft_choice(window,closing=True,exiting=exiting,save_label='保存快捷键')
            if answer=='cancel':return
            if answer=='save':save(finish);return
            if answer=='keep':app.shortcut_draft=snapshot()
            else:app.shortcut_draft=None
        finish()
    def dispose(event):
        if event.widget is window:
            stop_capture()
            for variable,token in traces:variable.trace_remove('write',token)
            for variable in [enabled,status,dirty,*fields.values(),*hints.values()]:variable.__del__();variable._tk=None
    window.bind('<Destroy>',dispose,add='+')
    for value in fields.values():traces.append((value,value.trace_add('write',validate)))
    traces.append((enabled,enabled.trace_add('write',validate)))
    for label in body.winfo_children():
        if isinstance(label,tk.Label):label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(100,e.width)))
    validate();window.shortcut_fields=fields;window.shortcut_save=save;window.shortcut_status=status
    window.protocol('WM_DELETE_WINDOW',close);control_confirm.register(app,window,close)
    window.shortcut_close=close;window.shortcut_dirty=is_dirty;window.shortcut_enabled=enabled
    window.shortcut_record=start_capture;window.shortcut_key=key_pressed;window.shortcut_stop=stop_capture;window.shortcut_hints=hints
    return window
