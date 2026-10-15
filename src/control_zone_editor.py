"""Editable distance zones persisted privately; raw laps and old reports stay intact."""
import copy,tkinter as tk
from i18n import tr
from control_theme import T
from control_fields import Field
from control_list import SessionList
from control_motion import reveal_window
from training_zones import validate,save,path

def show(app,entry,definitions,on_save):
    window=tk.Toplevel(app.root);window.title(tr('编辑分析区间'));window.configure(bg=T.BG);window.geometry('920x620');window.minsize(750,500)
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18);app.label(body,'编辑分析区间',18,T.FG,True).pack(anchor='w',pady=8)
    app.label(body,'距离单位 m；自定义名称不等于官方弯号。允许留空区间，禁止重叠。',9).pack(fill='x')
    state=dict(zones=copy.deepcopy(definitions),selected=None)
    table=SessionList(body,columns=('name','start','apex','end'),height=5)
    for key,title in (('name','名称'),('start','起点 / m'),('apex','弯心 / m'),('end','终点 / m')):table.heading(key,text=title);table.column(key,width=200,minwidth=90,stretch=True)
    table.pack(fill='both',expand=True,pady=8)
    variables={};forms=tk.Frame(body,bg=T.CARD);forms.pack(fill='x')
    for i,(key,title) in enumerate((('name','名称'),('start','起点'),('apex','弯心'),('end','终点'))):
        tile=tk.Frame(forms,bg=T.CARD);tile.grid(row=0,column=i,sticky='ew',padx=4);forms.columnconfigure(i,weight=1);app.label(tile,title,9).pack(anchor='w');variables[key]=tk.StringVar(window);Field(tile,textvariable=variables[key],width=14).pack(fill='x')
    message=tk.StringVar(window);app.label(body,message,9).pack(fill='x',pady=8)
    def populate():
        table.replace([(str(i),(z['name'],f"{z['start']:.1f}",f"{z['apex']:.1f}",f"{z['end']:.1f}")) for i,z in enumerate(state['zones'])],());state['selected']=None
    def selected(_=None):
        ids=table.selection()
        if not ids:return
        i=int(ids[0]);state['selected']=i
        for key,var in variables.items():var.set(str(state['zones'][i][key]))
    table.bind('<<TreeviewSelect>>',selected)
    def modify(add=False):
        try:
            z=dict(name=variables['name'].get(),**{k:float(variables[k].get()) for k in ('start','end','apex')});validate([z],entry['length_m'])
            values=copy.deepcopy(state['zones'])
            if add or state['selected'] is None:values.append(z)
            else:values[state['selected']]=z
            state['zones']=validate(values,entry['length_m']);populate();message.set(tr('区间已更新，保存后用于重新分析'))
        except (ValueError,KeyError) as e:message.set(str(e))
    def remove():
        if state['selected'] is not None:state['zones'].pop(state['selected']);populate()
    def commit():
        try:save(app.data_path,entry,state['zones']);on_save();window.destroy()
        except (OSError,ValueError) as e:message.set(str(e))
    def automatic():
        p=path(app.data_path,entry)
        if p.is_file():p.unlink() # Only this application's editable zone preference.
        on_save();window.destroy()
    row=app.row(body);app.button(row,'更新选中区间',modify,False,150);app.button(row,'添加区间',lambda:modify(True),False,120);app.button(row,'移除选中区间',remove,False,150)
    row=app.row(body);app.button(row,'保存并重新分析',commit,True,180);app.button(row,'恢复自动区间',automatic,False,160);populate();reveal_window(window)
