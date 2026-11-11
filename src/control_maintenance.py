"""User-visible report retries and safe, opt-in cache maintenance."""
import tkinter as tk
from control_theme import T
from control_list import SessionList
from i18n import tr

def shell(app,title,columns,feedback=False,subtitle=''):
    """A table window: heading and purpose, the table, then the shared footer.

    `footer` is a free row above the footer's state line for windows that lay
    out their own controls; others add actions with `window.add_action`.
    """
    from control_window import window as sheet
    from control_widgets import px
    window=sheet(app.root,title,subtitle,feedback=feedback,transient=False);body=window.body
    footer=tk.Frame(window.footer,bg=T.BG);footer.pack(fill='x',padx=px(window,22),before=window.footer.bar)
    table=SessionList(body,columns=[k for k,_,_ in columns],height=8,selectmode='extended')
    for key,label,width in columns:table.heading(key,text=label);table.column(key,width=width*table.s,minwidth=70*table.s,stretch=True)
    text=window.status
    if feedback:window.work_feedback=window.footer.feedback
    table.pack(fill='both',expand=True,pady=(px(window,6),0))
    return window,footer,table,text


def reports(app,initial=()):
    from control_report_tasks import show
    return show(app,initial)


def caches(app):
    from control_cache_panel import show
    return show(app)


def busy(app):
    from control_batch import jobs
    return bool(getattr(app,'maintenance_busy',False) or getattr(app,'lap_curve_jobs',0) or getattr(getattr(app,'report_retry_job',None),'busy',False)
        or any(getattr(job,'blocks_capture',False) is True and job.busy for job in jobs(app)))


def offline_ready(app):
    from control_batch import running
    hud=getattr(app,'hud',None)
    return not busy(app) and not app.active() and not app.tasks.busy and not (hud is not None and hud.root.winfo_exists()) and running(app) is None


def update(app):
    for name in ('report_tasks_window','cache_panel_window','split_checks_window'):
        window=getattr(app,name,None)
        if window is not None and window.winfo_exists() and hasattr(window,'worklist'):window.worklist.sync()
