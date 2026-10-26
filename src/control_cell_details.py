"""Keyboard cell navigation and a read-only snapshot of unabridged display text."""
import tkinter as tk
from tkinter import ttk
from control_theme import T
from control_video_widgets import Action
from control_motion import keyboard_action
from i18n import Label,tr


def columns(table):return [k for k in table.displaycolumns if k in table.frozen_columns]+[k for k in table.displaycolumns if k not in table.frozen_columns]


def current(table):
    selected=table.selection();iid=table.cursor if table.cursor in selected else next(iter(selected),None);keys=columns(table)
    if iid is None or not keys:return None
    key=table.focus_column if table.focus_column in keys else keys[0]
    return iid,key,str(dict(zip(table.columns,table.rows[iid])).get(key,''))


def move(table,delta):
    def apply():
        cell=current(table)
        if cell is None:return 'break'
        iid,key,_=cell;keys=columns(table);key=keys[max(0,min(len(keys)-1,keys.index(key)+delta))];table.focus_column=key;table.cursor=iid;table.tooltip.hide()
        if key not in table.frozen_columns and hasattr(table,'actual'):
            x=next(x for k,x,_ in table.positions() if k==key);fixed=table.gutter+sum(table.actual[k] for k in table.frozen_columns);width=table.viewport.winfo_width();offset=table.xoffset
            if x<fixed or table.actual[key]>width-fixed:offset+=x-fixed
            elif x+table.actual[key]>width:offset+=x+table.actual[key]-width
            table.xview('moveto',offset/max(1,table.totalwidth-fixed))
        table.paint();return 'break'
    return keyboard_action(table,apply)


def show(table):
    cell=current(table)
    if cell is None:return None
    iid,key,value=cell
    old=getattr(table,'cell_details',None)
    if old is not None and old.winfo_exists():
        snapshot=old.cell_snapshot
        if (snapshot['row'],snapshot['column'],snapshot['value'])==cell:old.deiconify();old.lift();snapshot['text'].focus_set();return old
        old.destroy()
    table.tooltip.hide();window=tk.Toplevel(table.winfo_toplevel());table.cell_details=window;window.configure(bg=T.BG);window.title(tr('单元格详情'));window.geometry('650x430');window.minsize(460,320);window.transient(table.winfo_toplevel())
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=16,pady=(14,8))
    heading=Label(body,text=table.labels[key],bg=T.CARD,fg=T.ACCENT,font=(T.FONT,13,'bold'),anchor='w');heading.pack(fill='x',padx=12,pady=(10,4))
    values=dict(zip(table.columns,table.rows[iid]));context=' · '.join(str(values[k]) for k in ('track','car','vehicle','date') if values.get(k))
    identity=Label(body,text=context,bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='w',justify='left');identity.pack(fill='x',padx=12,pady=4);identity.bind('<Configure>',lambda e:identity.configure(wraplength=max(100,e.width)))
    hint=Label(body,text='只读快照；可选取文字，原始记录保留。',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='w',justify='left');hint.pack(fill='x',padx=12,pady=(0,8));hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(100,e.width)))
    holder=tk.Frame(body,bg=T.FIELD);holder.pack(fill='both',expand=True,padx=12,pady=(0,12))
    text=tk.Text(holder,wrap='word',state='normal',bg=T.FIELD,fg=T.FG,selectbackground=T.SELECT,selectforeground=T.FG,relief='flat',font=(T.FONT,10),padx=10,pady=8,width=1,height=1,takefocus=True)
    bar=ttk.Scrollbar(holder,orient='vertical',command=text.yview,style='Lab.Vertical.TScrollbar');bar.pack(side='right',fill='y');text.configure(yscrollcommand=bar.set);text.pack(fill='both',expand=True);text.insert('1.0',value);text.configure(state='disabled')
    text.bind('<Control-a>',lambda _:(text.tag_add('sel','1.0','end-1c'),'break')[1])
    footer=tk.Frame(window,bg=T.BG);footer.pack(fill='x',padx=16,pady=(0,12));status=Label(footer,text='',bg=T.BG,fg=T.MUTED,font=(T.FONT,9),anchor='w');status.pack(fill='x',pady=(0,5))
    row=tk.Frame(footer,bg=T.BG);row.pack(fill='x')
    def copy():window.clipboard_clear();window.clipboard_append(value);status.configure(text='已复制到剪贴板')
    actions=[Action(row,'复制完整文字',copy,160,True),Action(row,'关闭',window.destroy,110)]
    for button in actions:button.pack(side='left',padx=(0,8))
    def translate():
        window.title(tr('单元格详情'))
        for button in actions:button.paint()
    window.retranslate=translate;window.bind('<Escape>',lambda _:(window.destroy(),'break')[1]);window.protocol('WM_DELETE_WINDOW',window.destroy)
    def closed(event):
        if event.widget is window and table.winfo_exists():table.cell_details=None;table.viewport.focus_set()
    window.bind('<Destroy>',closed,add='+');window.cell_snapshot=dict(row=iid,column=key,value=value,text=text,copy=copy);text.focus_set();return window


def dispose(table):
    window=getattr(table,'cell_details',None)
    if window is not None and window.winfo_exists():window.destroy()
