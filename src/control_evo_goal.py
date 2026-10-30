"""Small industrial editor for an in-window, observed lap-time target."""
import tkinter as tk
from control_fields import Field
from control_theme import T
from i18n import tr


def show(app,parent,value,apply):
    if app.closing or not parent.winfo_exists():return
    old=getattr(parent,'goal_window',None)
    if old is not None and old.winfo_exists():old.lift();old.focus_set();return old
    window=tk.Toplevel(parent);parent.goal_window=window;window.title(tr('本场目标圈速'));window.geometry('540x320');window.minsize(450,300);window.configure(bg=T.BG);window.transient(parent)
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    app.label(body,'本场目标圈速',16,T.FG,True).pack(anchor='w',pady=(12,8),padx=12)
    label=app.label(body,'输入秒数或 分:秒；只统计可用圈，不作条件校正。目标仅保留在本次打开的窗口中。',10,T.MUTED);label.pack(fill='x',padx=12,pady=5);label.bind('<Configure>',lambda e:label.configure(wraplength=max(80,e.width)))
    text=tk.StringVar(window,value=value);message=tk.StringVar(window);issue={'text':''}
    field=Field(body,textvariable=text);field.pack(fill='x',padx=12,pady=8)
    hint=app.label(body,message,9,T.RED);hint.pack(fill='x',padx=12);hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(80,e.width)))
    def save():
        try:apply(text.get())
        except ValueError as error:issue['text']=str(error);message.set(tr(issue['text']));field.set_error(message.get());return False
        window.destroy();return True
    row=app.row(body);app.button(row,'应用目标',save,True,135);app.button(row,'取消',window.destroy,False,110)
    def translate():window.title(tr('本场目标圈速'));message.set(tr(issue['text']))
    window.retranslate=translate;field.entry.bind('<Return>',lambda _:(save(),'break')[1]);window.bind('<Escape>',lambda _:(window.destroy(),'break')[1]);window.protocol('WM_DELETE_WINDOW',window.destroy)
    window.goal_controls=dict(text=text,save=save,message=message,field=field);field.focus_set();return window
