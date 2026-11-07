"""Quiet post-session actions; no pop-up over a running race."""
from platform_runtime import open_path
import os
import tkinter as tk
from control_theme import T
from i18n import tr
from control_widgets import px
from control_tooltip import Tooltip


def install(app):
    if app.recent.folder is None:return
    body=app.shell.action_host;body.pack(fill='x',before=app.shell.scroll.master,pady=(0,4))
    row=app.row(body);row.pack_configure(pady=0);row.columnconfigure(0,weight=1)
    # Two short lines instead of one clipped sentence: what it was, then when
    # and how far its reports are. The full text stays on hover and focus.
    text=tk.Frame(row,bg=T.BG);text.grid(row=0,column=0,sticky='ew',padx=(0,8))
    label=app.label(text,'',9,T.FG,True);label.configure(takefocus=True,pady=0,bd=0);label.pack(fill='x')
    detail=app.label(text,'',9,T.MUTED);detail.configure(pady=0,bd=0);detail.pack(fill='x')
    label.recent_full='';label.recent_short='';label.recent_detail=detail;detail.recent_short=''
    tip=Tooltip(label)
    def clip(_=None):
        for widget in (label,detail):
            value=widget.recent_short;maximum=max(1,widget.winfo_width()-4)
            measure=lambda value,w=widget:int(w.tk.call('font','measure',w.cget('font'),value))
            if measure(value)>maximum:
                while value and measure(value+'…')>maximum:value=value[:-1]
                value+='…'
            widget.configure(text=value)
    def hint(event=None):tip.request(label.recent_full,label.recent_full,label.winfo_rootx(),detail.winfo_rooty()+detail.winfo_height())
    for widget in (label,detail):
        widget.bind('<Configure>',clip);widget.bind('<Enter>',hint);widget.bind('<Leave>',lambda _:tip.hide());widget.bind('<Button-1>',lambda _:label.focus_set())
    label.bind('<FocusIn>',hint);label.bind('<FocusOut>',lambda _:tip.hide());label.bind('<Destroy>',lambda _:tip.hide())
    label.recent_clip=clip;label.recent_tip=tip
    actions=tk.Frame(row,bg=T.BG);actions.grid(row=0,column=1,sticky='e')
    buttons={'review':app.button(actions,'打开刚结束的复盘',lambda:open_report(app,'review'),False,165),
        'laps':app.button(actions,'圈速单',lambda:open_report(app,'laps'),False,100),'note':app.button(actions,'添加备注',lambda:add_note(app),False,110)}
    for button in buttons.values():button.configure(height=px(button,38));button.pack_configure(pady=0)
    app.recent_widgets=(label,buttons)
    update(app)


def open_report(app,kind):
    """Shared by the recent-session row and the command palette."""
    state=app.recent.state()
    if not state[kind]:return
    if kind=='review':open_path(state['folder']/'review.html')
    else:
        from control_report_images import show
        show(app,state['folder'],'圈速单.png')


def add_note(app):
    state=app.recent.state()
    if state['note']:
        from control_event_filters import edit_note
        edit_note(app,dict(folder=str(state['folder'])),lambda:app.status.set(tr('备注已保存')))


def update(app):
    app.recent.observe(app.hud,app.run_background)
    if app.page!=0:return
    widgets=getattr(app,'recent_widgets',None)
    if not widgets or not widgets[0].winfo_exists():
        if app.recent.folder is not None and app.pages.pending is None:app.install_toolbar()
        return
    state=app.recent.state();label,buttons=widgets
    text=state['text']+'\n'+tr(state['status']) if state.get('status') else tr(state['text'])
    if label.recent_full!=text:
        parts=state['text'].split(' · ');status=state.get('status') or ''
        label.recent_tip.hide();label.recent_full=text;label.recent_short=tr('上一场')+' · '+parts[0]
        # Only an unfinished report state earns words; ready shows in the buttons.
        short={'赛事已保存，报告正在生成':'报告生成中','赛事已保存，部分报告待完成':'部分报告待完成'}.get(status)
        label.recent_detail.recent_short=' · '.join([*parts[1:],*([tr(short)] if short else [])])
        label.recent_clip()
    for key,button in buttons.items():
        if button.enabled!=state[key]:button.configure(state='normal' if state[key] else 'disabled')
