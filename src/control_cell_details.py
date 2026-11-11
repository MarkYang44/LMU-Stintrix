"""Keyboard cell navigation and a read-only snapshot of unabridged display text."""
import tkinter as tk
from tkinter import ttk
from control_theme import T
from control_video_widgets import Action
from control_motion import keyboard_action,fade_in
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
    from control_window import window as sheet,fit
    table.tooltip.hide()
    values=dict(zip(table.columns,table.rows[iid]));context=' · '.join(str(values[k]) for k in ('track','car','vehicle','date') if values.get(k))
    window=sheet(table.winfo_toplevel(),'单元格详情',context,heading=table.labels[key]);table.cell_details=window
    holder=tk.Frame(window.body,bg=T.FIELD);holder.pack(fill='both',expand=True)
    text=tk.Text(holder,wrap='word',state='normal',bg=T.FIELD,fg=T.FG,selectbackground=T.SELECT,selectforeground=T.FG,relief='flat',font=(T.FONT,10),padx=10,pady=8,width=1,height=1,takefocus=True)
    bar=ttk.Scrollbar(holder,orient='vertical',command=text.yview,style='Lab.Vertical.TScrollbar');bar.pack(side='right',fill='y');text.configure(yscrollcommand=bar.set);text.pack(fill='both',expand=True);text.insert('1.0',value);text.configure(state='disabled')
    text.bind('<Control-a>',lambda _:(text.tag_add('sel','1.0','end-1c'),'break')[1])
    window.status.set(tr('只读快照；可选取文字，原始记录保留。'))
    def copy():window.clipboard_clear();window.clipboard_append(value);window.status.set(tr('已复制到剪贴板'))
    actions=[window.add_action('复制完整文字',copy,True,130),window.add_action('关闭',window.destroy,False,90)]
    def closed(event):
        if event.widget is window and table.winfo_exists():table.cell_details=None;table.viewport.focus_set()
    window.bind('<Destroy>',closed,add='+');window.cell_snapshot=dict(row=iid,column=key,value=value,text=text,copy=copy)
    fit(window,600,420,minimum=(440,300),owner=table);text.focus_set();return window


def dispose(table):
    window=getattr(table,'cell_details',None)
    if window is not None and window.winfo_exists():window.destroy()
