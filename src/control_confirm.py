"""Explicit local choices. A confirmation never uses ambiguous Yes/No labels."""
import tkinter as tk
from control_theme import T
from control_widgets import px
from control_video_widgets import Action
from i18n import tr


def ask(parent,title,message,choices):
    owner=parent.winfo_toplevel();window=tk.Toplevel(owner);window.title(tr(title));window.configure(bg=T.BG);window.transient(owner)
    window.resizable(False,False);result=['cancel'];body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=16,pady=16)
    tk.Label(body,text=tr(message),wraplength=px(window,570),justify='left',anchor='w',bg=T.CARD,fg=T.FG,font=(T.FONT,10)).pack(fill='x',padx=12,pady=16)
    actions=tk.Frame(body,bg=T.CARD);actions.pack(fill='x',padx=8,pady=8);buttons={}
    def choose(key):result[0]=key;window.destroy()
    for index,(key,label) in enumerate(choices):
        button=Action(actions,label,lambda k=key:choose(k),260,key=='save');button.grid(row=index//2,column=index%2,padx=5,pady=4,sticky='ew');buttons[key]=button
    actions.columnconfigure(0,weight=1);actions.columnconfigure(1,weight=1)
    window.protocol('WM_DELETE_WINDOW',lambda:choose('cancel'));window.bind('<Escape>',lambda _:choose('cancel'))
    window.confirm_buttons=buttons;owner._stintrix_confirm=window
    previous=owner.grab_current();window.update_idletasks()
    from control_layout_preview import monitors
    from control_tooltip import position
    cx=owner.winfo_rootx()+owner.winfo_width()/2;cy=owner.winfo_rooty()+owner.winfo_height()/2;screens=monitors(owner)
    sx,sy,sw,sh=next((r for r in screens if r[0]<=cx<r[0]+r[2] and r[1]<=cy<r[1]+r[3]),screens[0])
    width=window.winfo_reqwidth();height=window.winfo_reqheight();position(window,max(sx,min(cx-width/2,sx+sw-width)),max(sy,min(owner.winfo_rooty()+80,sy+sh-height)))
    try:
        window.grab_set();buttons.get('cancel',next(iter(buttons.values()))).focus_set();owner.wait_window(window)
    finally:
        owner._stintrix_confirm=None
        if previous is not None and previous.winfo_exists():previous.grab_set()
        if owner.winfo_exists():owner.focus_set()
    return result[0]


def draft_choice(parent,closing=False,exiting=False,save_label='保存并应用'):
    choices=[('save',save_label)]
    if closing and not exiting:choices.append(('keep','保留草稿并关闭'))
    choices.extend([('discard','放弃修改并关闭' if closing else '放弃修改'),('cancel','继续编辑')])
    message='退出程序后未保存草稿将丢失。请选择保存或明确放弃。' if exiting else '请选择如何处理未保存的修改。草稿只在本次程序运行中保留。'
    return ask(parent,'有未保存修改',message,choices)


def register(app,window,close):
    window.request_draft_close=close
    app.draft_editors=[w for w in getattr(app,'draft_editors',[]) if w.winfo_exists()]
    app.draft_editors.append(window)


def close_editors(app,done):
    editors=[w for w in getattr(app,'draft_editors',[]) if w.winfo_exists()]
    def next_editor(index=0):
        if index==len(editors):
            if getattr(app,'layout_draft',None) or getattr(app,'shortcut_draft',None) or getattr(app,'column_drafts',None) or getattr(app,'profile_draft',None) or getattr(app,'note_drafts',None):
                answer=ask(app.root,'有未保存修改','仍有保留的草稿。退出会丢失草稿，可返回程序打开对应编辑器保存。',[('discard','放弃保留草稿并退出'),('cancel','返回程序')])
                if answer!='discard':return
                app.layout_draft=None;app.shortcut_draft=None;app.column_drafts={};app.profile_draft=None;app.note_drafts={}
            done();return
        window=editors[index]
        if not window.winfo_exists():next_editor(index+1);return
        window.request_draft_close(lambda:next_editor(index+1),exiting=True)
    next_editor()
