"""Small industrial editor for an in-window, observed lap-time target."""
import tkinter as tk
from control_fields import Field
from control_theme import T
from i18n import tr


def show(app,parent,value,apply):
    if app.closing or not parent.winfo_exists():return
    old=getattr(parent,'goal_window',None)
    if old is not None and old.winfo_exists():old.lift();old.focus_set();return old
    from control_window import window as sheet,fit,note
    window=sheet(parent,'本场目标圈速','输入秒数或分:秒（例如2:05.300）。只统计可用圈，不作条件校正；目标只保留在本次打开的窗口中。');parent.goal_window=window
    text=tk.StringVar(window,value=value);message=tk.StringVar(window);issue={'text':''}
    field=Field(window.body,textvariable=text);field.pack(fill='x')
    hint=note(window.body,message,9,T.RED);hint.pack(fill='x',pady=(6,0))
    def save():
        try:apply(text.get())
        except ValueError as error:issue['text']=str(error);message.set(tr(issue['text']));field.set_error(message.get());return False
        window.destroy();return True
    window.add_action('应用目标',save,True,110);window.add_action('取消',window.destroy,False,90)
    shell_translate=window.retranslate
    def translate():shell_translate();message.set(tr(issue['text']))
    window.retranslate=translate;field.entry.bind('<Return>',lambda _:(save(),'break')[1])
    window.goal_controls=dict(text=text,save=save,message=message,field=field);fit(window,500,owner=parent);field.focus_set();return window
