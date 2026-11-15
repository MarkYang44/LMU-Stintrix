"""The HUD's reference lap, shown and edited on the Run & HUD page.

This is the same preference the HUD's right-click menu and F6 change, which
used to be its only home: whether the live delta is drawn, where the lap
comes from (matched for the car and track, or one fixed lap) and, when
matched, which kind of lap. With a HUD running a change applies at once;
otherwise it is saved for the next start. A file chosen here, or a lap locked
in the Recording Manager, becomes the fixed reference.
"""
import json
import tkinter as tk
from pathlib import Path
from control_theme import T
from i18n import tr

SOURCES={'auto':'自动匹配','fixed':'固定参考圈'}
KINDS={'fastest':'最快完整圈','stable':'典型稳定圈'}
AUTOMATIC={'fastest':'自动匹配同车同赛道已记录的最快完整圈','stable':'自动匹配同车同赛道已记录的典型稳定圈'}


def owner(app):
    """The live HUD while one runs; the control center's saved copy otherwise."""
    return app.hud if app.active() else app


def source(target):
    return 'auto' if target.reference_auto.get() and not target.reference_locked.get() else 'fixed'


def reload(app):
    """Refresh the control center's copy from the file a HUD may have changed."""
    try:saved=json.loads((app.data_path/'reference_settings.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return
    if not isinstance(saved,dict):return
    app.reference_settings=saved
    for variable,key,default in ((app.reference_on,'enabled',False),(app.reference_auto,'automatic',True),(app.reference_locked,'locked',False)):
        value=bool(saved.get(key,default))
        if variable.get()!=value:variable.set(value)
    kind=saved.get('kind','fastest')
    if app.reference_kind.get()!=kind:app.reference_kind.set(kind)


def describe(app):
    target=owner(app);shown=target.reference_on.get();path=str(target.reference_settings.get('path','') or '')
    if source(target)=='auto':
        text=tr(AUTOMATIC.get(target.reference_kind.get(),AUTOMATIC['fastest']))
    elif path:text=tr('固定参考圈：{name}').format(name=Path(path).name)
    else:text=tr('固定参考圈：尚未选择；HUD 运行时会固定当前匹配到的圈')
    message=getattr(target,'reference_message','') if target is not app else ''
    if message:text+=' · '+tr(message)
    return (tr('HUD 不显示参考圈差')+' · ' if not shown else '')+text


def build(app):
    """Add the card (full width, after the HUD cards); returns its refresh."""
    from control_widgets import Switch,segmented_row,px
    body=app.card('参考圈','比赛中按距离与参考圈对比，差值显示在 HUD 上')
    shown=tk.BooleanVar(app.root);origin=tk.StringVar(app.root);kind=tk.StringVar(app.root);state={'syncing':False}
    def change(**values):
        if state['syncing']:return
        target=owner(app)
        if 'enabled' in values:target.reference_on.set(values['enabled'])
        if 'source' in values:
            target.reference_locked.set(values['source']=='fixed')
            if values['source']=='auto':target.reference_auto.set(True)
        if 'kind' in values:target.reference_kind.set(values['kind'])
        target.apply_reference();refresh()
    switch=Switch(body,'在 HUD 显示参考圈差 · F6',shown,lambda:change(enabled=shown.get()));switch.pack(fill='x',pady=2)
    origin_row=segmented_row(body,'参考来源',origin,list(SOURCES),lambda:change(source=origin.get()),SOURCES)
    kind_row=segmented_row(body,'自动匹配的圈',kind,list(KINDS),lambda:change(kind=kind.get()),KINDS)
    # The current reference reads on its own line; long translations of the
    # two actions would otherwise squeeze it into a narrow column.
    status=app.label(body,'',9,T.MUTED);status.pack(fill='x',pady=(px(body,8),0))
    actions=tk.Frame(body,bg=body.cget('bg'));actions.pack(fill='x',pady=(px(body,8),0))
    status.bind('<Configure>',lambda e:status.configure(wraplength=max(100,e.width)),add='+')
    def choose():
        target=owner(app)
        if target is app.hud:target.select_reference();refresh();return
        from tkinter import filedialog
        path=filedialog.askopenfilename(parent=app.root,title=tr('选择完整参考圈'),initialdir=str(app.data_path/'Logs'),filetypes=[(tr('Stintrix 完整圈'),'*.lap.json')])
        if not path:return
        try:
            from reference import ReferenceLap
            ReferenceLap.load(path)
        except Exception as error:
            from control_confirm import notice
            notice(app.root,'参考圈读取失败',str(error));return
        app.reference_settings['path']=path;app.reference_auto.set(False);app.reference_locked.set(True);app.reference_on.set(True)
        app.apply_reference();refresh()
    picker=app.button(actions,'选择参考圈文件…',choose,False,150,compact=True);picker.pack_configure(side='left',padx=(0,px(body,8)))
    if app.capabilities.training:
        manager=app.button(actions,'从完整记录管理挑选…',lambda:app.library([]),False,170,compact=True);manager.pack_configure(side='left',padx=0)
    def refresh():
        if not status.winfo_exists():return
        target=owner(app)
        if target is app:reload(app)
        state['syncing']=True
        try:
            for variable,value in ((shown,target.reference_on.get()),(origin,source(target)),(kind,target.reference_kind.get())):
                if variable.get()!=value:variable.set(value)
        finally:state['syncing']=False
        # The kind only chooses among recorded laps when matching automatically.
        automatic=origin.get()=='auto'
        kind_row.set_enabled(automatic)
        text=describe(app)
        if status.cget('text')!=text:tk.Label.configure(status,text=text)
    app.reference_refresh=refresh;app.reference_controls=dict(switch=switch,source=origin_row,kind=kind_row,status=status,choose=choose)
    refresh()
    return refresh
