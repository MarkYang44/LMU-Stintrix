"""Read-only import of one LMU native telemetry log, in the shared window style.

The HUD menu opens it for a single file. Every identity field is optional:
an empty field keeps the log's own metadata. A track or car name is needed
only when the log has none, and a lap length only when the log has none and
distances should not be estimated.
"""
import math
import tkinter as tk
from pathlib import Path
from control_fields import Field
from control_theme import T
from i18n import tr

FIELDS=(('track','赛道'),('vehicle','车辆'),('driver','车手'),('track_length','圈长 / m'))


class OverrideError(ValueError):
    def __init__(self,message,field):
        super().__init__(message);self.field=field


def overrides(values):
    """Drop blank fields and check the lap length; the rest is passed through."""
    result={key:str(value).strip() for key,value in values.items() if str(value).strip()}
    if 'track_length' in result:
        try:length=float(result['track_length'])
        except ValueError:length=math.nan
        if not math.isfinite(length) or not 100<length<100000:raise OverrideError('圈长应为 100–100000 m 之间的数字','track_length')
    return result


def show(owner,path,run,topmost=False):
    """`run(values, done)` imports off the GUI thread and later calls `done(error)` on it."""
    from control_window import window as sheet,fit,note
    from control_widgets import px
    previous=getattr(owner,'native_import_window',None)
    if previous is not None and previous.winfo_exists():previous.destroy()
    window=sheet(owner.root,'导入 LMU 官方遥测','源文件保持只读，导入后生成完整复盘与最快圈。留空的项目沿用日志中的信息。',topmost=topmost)
    owner.native_import_window=window
    source=note(window.body,Path(path).name,10,T.FG,True);source.pack(fill='x')
    note(window.body,'日志缺少赛道或车辆名称时必须填写；没有圈长时，距离只做估算。',9,T.MUTED).pack(fill='x',pady=(px(window,4),px(window,12)))
    grid=tk.Frame(window.body,bg=T.BG);grid.pack(fill='x');grid.columnconfigure(1,weight=1)
    variables={};fields={}
    for row,(key,label) in enumerate(FIELDS):
        note(grid,label,10,T.MUTED).grid(row=row,column=0,sticky='w',padx=(0,px(window,16)),pady=px(window,4))
        variable=tk.StringVar(window);variables[key]=variable
        field=Field(grid,textvariable=variable);field.grid(row=row,column=1,sticky='ew',pady=px(window,4));fields[key]=field
        variable.trace_add('write',lambda *_,f=field:f.set_error('') if f.winfo_exists() else None)
        field.entry.bind('<Return>',lambda _:(begin(),'break')[1])
    state={'running':False}
    def begin():
        if state['running']:return
        try:values=overrides({key:variable.get() for key,variable in variables.items()})
        except OverrideError as error:
            fields[error.field].set_error(tr(str(error)));window.status.set(tr(str(error)));fields[error.field].focus_set();return
        state['running']=True;start.configure(state='disabled');window.status.set(tr('正在只读导入并生成完整复盘…'))
        def done(error):
            if not window.winfo_exists():return
            state['running']=False;start.configure(state='normal')
            if error:window.status.set(tr(str(error)))
            else:window.destroy()
        run(values,done)
    start=window.add_action('开始导入',begin,True,110);window.add_action('取消',window.destroy,False,90)
    window.import_controls=dict(variables=variables,fields=fields,begin=begin,start=start)
    fit(window,520,owner=owner.root);fields['track'].focus_set()
    return window
