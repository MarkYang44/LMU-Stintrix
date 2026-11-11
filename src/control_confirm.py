"""Explicit local choices. A confirmation never uses ambiguous Yes/No labels."""
import tkinter as tk
from control_theme import T
from i18n import tr


DANGER=('discard','stop')


def ask(parent,title,message,choices):
    from control_window import window as sheet,fit,modal,natural_width,note
    owner=parent.winfo_toplevel();window=sheet(owner,title,escape=False);window.resizable(False,False);result=['cancel']
    note(window.body,message,10,T.FG).pack(fill='x')
    buttons={}
    def choose(key):result[0]=key;window.destroy()
    for key,label in choices:buttons[key]=window.add_action(label,lambda k=key:choose(k),key=='save',110,key in DANGER)
    window.on_close=lambda:choose('cancel');window.bind('<Escape>',lambda _:(choose('cancel'),'break')[1])
    window.confirm_buttons=buttons;owner._stintrix_confirm=window
    fit(window,natural_width(window,440,820),owner=owner)
    try:modal(window,owner,buttons.get('cancel',next(iter(buttons.values()))))
    finally:owner._stintrix_confirm=None
    return result[0]


def notice(parent,title,message):
    """A single-answer message in the app's own window style instead of a native box."""
    return ask(parent,title,message,[('cancel','知道了')])


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
