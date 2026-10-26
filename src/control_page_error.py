"""Recoverable page construction errors keep navigation available."""
from i18n import tr
from control_theme import T


def show(deck,error):
    app=deck.owner;index=deck.index
    app.clear_toolbar()
    from control_disposal import release
    release(deck.active,app);deck.pages.pop(index,None);deck.active=None
    import tkinter as tk
    from control_pages import Page
    page=Page(tk.Frame(deck.host,bg=T.BG),complete=True,failed=True);deck.active=page
    app.content=page.frame;page.frame.pack(fill='x')
    body=app.card('页面暂时无法打开','',compact=True)
    app.label(body,'可重试当前页面，或从左侧切换到其他页面。',10,T.MUTED).pack(fill='x',pady=8)
    label=app.label(body,str(error) or type(error).__name__,10,T.MUTED);label.pack(fill='x');label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    app.button(app.row(body),'重试当前页面',lambda:app.show_page(index,progressive=True),True,150)
    app.status.set(tr('页面未能打开：')+(str(error) or type(error).__name__))
    app.shell.reveal_page(deck.surface)
