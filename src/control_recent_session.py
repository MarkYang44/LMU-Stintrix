"""Quiet post-session actions; no pop-up over a running race."""
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
    label=app.label(row,'',9,T.MUTED);label.configure(takefocus=True);label.grid(row=0,column=0,sticky='ew',padx=(0,8));label.recent_full='';label.recent_short=''
    tip=Tooltip(label)
    def clip(_=None):
        text=label.recent_short;maximum=max(1,label.winfo_width()-4)
        measure=lambda value:int(label.tk.call('font','measure',label.cget('font'),value))
        if measure(text)>maximum:
            while text and measure(text+'…')>maximum:text=text[:-1]
            text+='…'
        label.configure(text=text)
    def hint(event=None):tip.request(label.recent_full,label.recent_full,label.winfo_rootx(),label.winfo_rooty()+label.winfo_height())
    label.bind('<Configure>',clip);label.bind('<Enter>',hint);label.bind('<Leave>',lambda _:tip.hide());label.bind('<FocusIn>',hint);label.bind('<FocusOut>',lambda _:tip.hide());label.bind('<Button-1>',lambda _:label.focus_set());label.bind('<Destroy>',lambda _:tip.hide())
    label.recent_clip=clip;label.recent_tip=tip
    actions=tk.Frame(row,bg=T.BG);actions.grid(row=0,column=1,sticky='e')
    def open_report(kind):
        state=app.recent.state()
        if not state[kind]:return
        if kind=='review':os.startfile(state['folder']/'review.html')
        else:
            from control_report_images import show
            show(app,state['folder'],'圈速单.png')
    def note():
        state=app.recent.state()
        if state['note']:
            from control_event_filters import edit_note
            edit_note(app,dict(folder=str(state['folder'])),lambda:app.status.set(tr('备注已保存')))
    buttons={'review':app.button(actions,'打开刚结束的复盘',lambda:open_report('review'),False,165),
        'laps':app.button(actions,'圈速单',lambda:open_report('laps'),False,100),'note':app.button(actions,'添加备注',note,False,110)}
    for button in buttons.values():button.configure(height=px(button,38));button.pack_configure(pady=0)
    app.recent_widgets=(label,buttons)
    update(app)


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
        label.recent_tip.hide();label.recent_full=text;label.recent_short=tr('最近赛事')+' ⓘ · '+state['text'];label.recent_clip()
    for key,button in buttons.items():
        if button.enabled!=state[key]:button.configure(state='normal' if state[key] else 'disabled')
