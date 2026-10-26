"""Private, lossless annotation editing with explicit limits and close protection."""
import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
from control_theme import T
from control_fields import Field,Select
from control_widgets import Switch
from control_confirm import register,draft_choice
from storage import atomic_json
from i18n import tr


def load(path):
    if not path.exists():return {}
    try:value=json.loads(path.read_text('utf-8-sig'))
    except (ValueError,OSError) as error:raise ValueError('标记文件无法读取，原文件已保留') from error
    if not isinstance(value,dict):raise ValueError('标记文件无法读取，原文件已保留')
    return value


def checked(tags,text):
    values=list(dict.fromkeys(v.strip() for v in tags.replace('，',',').split(',') if v.strip()))
    if len(values)>20 or any(len(v)>40 for v in values):raise ValueError('最多 20 个标签，每个最多 40 字')
    if len(text)>2000:raise ValueError('备注最多 2000 字，请修改后保存')
    return values


def show(app,entry,done):
    if not entry or not entry.get('folder'):return
    root=Path(app.data_path).resolve();folder=Path(entry['folder']).resolve()
    if not folder.is_relative_to(root) or folder==root:return
    key=str(folder.relative_to(root));windows=getattr(app,'note_windows',{});app.note_windows=windows
    if key in windows and windows[key].winfo_exists():windows[key].deiconify();windows[key].lift();return windows[key]
    try:
        notes=load(root/'library_notes.json');alternate=folder.relative_to(root).as_posix();stored=key if key in notes else alternate
        old=notes.get(stored)
        if old is None:old=load(folder/'_archive_note.json')
        if not isinstance(old,dict) or not isinstance(old.get('text',''),str) or not isinstance(old.get('tags',[]),list) or any(not isinstance(tag,str) for tag in old.get('tags',[])):raise ValueError('标记文件无法读取，原文件已保留')
    except ValueError as error:app.status.set(tr(str(error)));return
    window=tk.Toplevel(app.root);windows[key]=window;window.title(tr('收藏与标签'));window.geometry('720x650');window.minsize(620,570);window.configure(bg=T.BG)
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=(0,18))
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    baseline=dict(favorite=bool(old.get('favorite')),traffic=bool(old.get('traffic')),tags=', '.join(old.get('tags',[])),text=old.get('text',''))
    drafts=getattr(app,'note_drafts',{});app.note_drafts=drafts;value=drafts.get(key,baseline)
    favorite=tk.BooleanVar(window,value=value['favorite']);traffic=tk.BooleanVar(window,value=value['traffic']);tags=tk.StringVar(window,value=value['tags']);message=tk.StringVar(window)
    app.label(body,'收藏与标签',18,T.FG,True).pack(anchor='w',padx=12,pady=8)
    identity=app.label(body,folder.name,9,T.MUTED);identity.pack(fill='x',pady=(0,5));identity.bind('<Configure>',lambda e:identity.configure(wraplength=max(100,e.width)))
    window.retranslate=lambda:window.title(tr('收藏与标签')+' · '+folder.name);window.retranslate()
    Switch(body,'收藏这场赛事',favorite,lambda:None).pack(fill='x');Switch(body,'交通影响（人工标记）',traffic,lambda:None).pack(fill='x')
    app.label(body,'标签（逗号分隔）',10).pack(anchor='w');Field(body,textvariable=tags).pack(fill='x',pady=6)
    known=sorted({tag for item in notes.values() if isinstance(item,dict) and isinstance(item.get('tags',[]),list) for tag in item.get('tags',[]) if isinstance(tag,str)})
    choice=tk.StringVar(window);row=app.row(body);picker=Select(row,textvariable=choice,values=known,width=24);picker.pack(side='left',fill='x',expand=True)
    def add():
        if choice.get():tags.set(', '.join(dict.fromkeys([v.strip() for v in tags.get().replace('，',',').split(',') if v.strip()]+[choice.get()])))
    add_button=app.button(row,'添加已有标签',add,False,150)
    if not known:picker.configure(state='disabled');add_button.configure(state='disabled')
    app.label(body,'备注',10).pack(anchor='w',pady=(8,3))
    holder=tk.Frame(body,bg=T.FIELD);holder.pack(fill='both',expand=True,pady=(0,8));text=tk.Text(holder,height=5,wrap='word',bg=T.FIELD,fg=T.FG,insertbackground=T.ACCENT,relief='flat',font=(T.FONT,10),undo=True,padx=10,pady=8)
    scrollbar=ttk.Scrollbar(holder,command=text.yview,orient='vertical',style='Lab.Vertical.TScrollbar');scrollbar.pack(side='right',fill='y');text.configure(yscrollcommand=scrollbar.set);text.pack(fill='both',expand=True);text.insert('1.0',value['text']);text.edit_modified(False)
    def snapshot():return dict(favorite=favorite.get(),traffic=traffic.get(),tags=tags.get(),text=text.get('1.0','end-1c'))
    def dirty():return snapshot()!=baseline
    def update(*_):
        value=snapshot();issue=''
        try:checked(value['tags'],value['text'])
        except ValueError as error:issue=tr(str(error))
        count=len({v.strip() for v in value['tags'].replace('，',',').split(',') if v.strip()})
        message.set(issue or (tr('有未保存修改') if dirty() else tr('设置与已保存值一致'))+' · '+tr('标签 {count}/20 · 备注 {length}/2000').format(count=count,length=len(value['text'])))
        hint.configure(fg=T.RED if issue else T.ACCENT if dirty() else T.MUTED)
    def save():
        value=snapshot()
        try:
            labels=checked(value['tags'],value['text']);current=load(root/'library_notes.json')
            target=key if key in current else alternate if alternate in current else key
            base=current.get(target,old)
            if not isinstance(base,dict):raise ValueError('标记文件无法读取，原文件已保留')
            current[target]={**base,**value,'tags':labels};atomic_json(root/'library_notes.json',current)
        except (ValueError,OSError) as error:message.set(tr(str(error)));hint.configure(fg=T.RED);return False
        drafts.pop(key,None);window.destroy();done();return True
    def close(after=None,exiting=False):
        if dirty():
            answer=draft_choice(window,closing=True,exiting=exiting,save_label='保存标记')
            if answer=='cancel':return
            if answer=='save':
                if not save():return
                if after:after()
                return
            if answer=='keep':drafts[key]=snapshot()
            else:drafts.pop(key,None)
        else:drafts.pop(key,None)
        window.destroy()
        if after:after()
    hint=app.label(footer,message,9);hint.pack(fill='x',padx=8,pady=8)
    app.button(app.row(footer),'保存标记',save,True,150)
    traces=[(v,v.trace_add('write',update)) for v in (favorite,traffic,tags)]
    def edited(_):
        if text.edit_modified():text.edit_modified(False);update()
    text.bind('<<Modified>>',edited);window.bind('<Control-s>',lambda _:(save(),'break')[1]);window.bind('<Escape>',lambda _:close());window.protocol('WM_DELETE_WINDOW',close);register(app,window,close)
    def dispose(event):
        if event.widget is window:
            windows.pop(key,None)
            for v,token in traces:v.trace_remove('write',token)
            for v in (favorite,traffic,tags,choice,message):v.__del__();v._tk=None
    window.bind('<Destroy>',dispose,add='+');update()
    window.note_controls=dict(tags=tags,text=text,favorite=favorite,traffic=traffic,choice=choice,add=add,save=save,close=close,dirty=dirty,message=message)
    return window
