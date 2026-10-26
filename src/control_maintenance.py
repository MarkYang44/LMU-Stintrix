"""User-visible report retries and safe, opt-in cache maintenance."""
import tkinter as tk
from control_theme import T
from control_list import SessionList
from i18n import tr

def shell(app,title,columns,feedback=False):
    window=tk.Toplevel(app.root);window.title(tr(title));window.geometry('1050x650');window.configure(bg=T.BG)
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=(0,18))
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    app.label(body,title,18,T.FG,True).pack(anchor='w',pady=10)
    table=SessionList(body,columns=[k for k,_,_ in columns],height=8,selectmode='extended')
    for key,label,width in columns:table.heading(key,text=label);table.column(key,width=width*table.s,minwidth=70*table.s,stretch=True)
    text=tk.StringVar(window)
    if feedback:
        from control_feedback import StatusFeedback
        window.work_feedback=StatusFeedback(body,text);window.work_feedback.pack(side='bottom',fill='x',pady=8)
    else:
        label=app.label(body,text,10);label.pack(side='bottom',fill='x',pady=10);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    table.pack(fill='both',expand=True,pady=8)
    return window,footer,table,text


def reports(app):
    from control_report_tasks import show
    return show(app)


def caches(app):
    from control_cache_panel import show
    return show(app)


def busy(app):
    return bool(getattr(app,'maintenance_busy',False) or getattr(getattr(app,'report_retry_job',None),'busy',False))


def offline_ready(app):
    from control_batch import running
    hud=getattr(app,'hud',None)
    return not busy(app) and not app.active() and not app.tasks.busy and not (hud is not None and hud.root.winfo_exists()) and running(app) is None


def update(app):
    for name in ('report_tasks_window','cache_panel_window','split_checks_window'):
        window=getattr(app,name,None)
        if window is not None and window.winfo_exists() and hasattr(window,'worklist'):window.worklist.sync()
