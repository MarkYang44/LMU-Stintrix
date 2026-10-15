"""Manual split inspection; both original records stay available."""
import os,tkinter as tk
from pathlib import Path
from control_theme import T
from control_list import SessionList
from split_checks import candidates,mark
from race_model import read_json
from track_names import display
from i18n import tr

def show(app):
    window=tk.Toplevel(app.root);window.title(tr('检查疑似拆分'));window.geometry('1080x600');window.configure(bg=T.BG)
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    label=app.label(body,'这里只列出相同赛道布局、车型、车手和参赛方式的相邻正赛片段；相邻不代表同一场，不会自动合并或删除。',10);label.pack(fill='x',pady=10);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    table=SessionList(body,columns=('track','car','first','second','gap','reason'),height=6)
    for key,title,width in (('track','赛道',150),('car','车型',190),('first','前段时间（UTC）',170),('second','后段时间（UTC）',170),('gap','间隔 / 秒',90),('reason','前段结束原因',180)):
        table.heading(key,text=title);table.column(key,width=width,minwidth=70,stretch=key in ('track','car','reason'))
    table.pack(fill='both',expand=True);state={'items':[]};note=tk.StringVar(window);app.label(body,note,10).pack(fill='x',pady=10)
    def refresh():
        from library import inventory
        def work():return candidates(inventory(app.data_path),read_json(app.data_path/'EventCatalog/split_checks.json',{}).get('checked',[]))
        def done(value,error):
            if not window.winfo_exists():return
            if error:note.set(error);return
            state['items']=value;table.replace([(str(i),(display(e['first']['track']),e['first']['vehicle'],e['first']['date'][:19].replace('T',' '),e['second']['date'][:19].replace('T',' '),f"{e['gap_s']:.1f}",e['reason'])) for i,e in enumerate(value)],());note.set(str(len(value))+' '+tr('组待人工检查'))
            if value:table.selection_set(('0',))
        app.run_background(work,done)
    def chosen():
        ids=table.selection();return state['items'][int(ids[0])] if ids else None
    def open_part(which):
        e=chosen()
        if e:
            folder=Path(e[which]['folder']);path=folder/'review.html';os.startfile(str(path if path.is_file() else folder))
    def checked():
        e=chosen()
        if e:mark(app.data_path,e['id']);refresh()
    row=app.row(body);app.button(row,'查看前段',lambda:open_part('first'),False,130);app.button(row,'查看后段',lambda:open_part('second'),False,130);app.button(row,'标为已检查',checked,False,145);app.button(row,'刷新',refresh,False,100)
    refresh();return window
