"""Responsive inventory filters, independent of row selection or file identity."""
import tkinter as tk
from control_fields import Field,Select
from control_widgets import px
from control_theme import T
from i18n import tr
from review_filters import PERIODS,SORTS
from track_names import display

class ReviewFilters(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=T.CARD);self.app=app;self.tiles=[];self.variables={};self.choices={};self.lookup={}
        self.state=getattr(app,'review_filter_state',dict(period=0,sort=0,phase='',track='',car='',start='',end=''))
        app.review_filter_state=self.state
        for key,label in (('period','时间范围（UTC）'),('phase','阶段'),('track','赛道'),('car','车辆'),('start','开始日期（YYYY-MM-DD）'),('end','结束日期（YYYY-MM-DD）'),('sort','排序')):
            tile=tk.Frame(self,bg=T.CARD);tile.columnconfigure(0,weight=1);self.tiles.append(tile)
            app.label(tile,label,9,T.MUTED).pack(anchor='w',pady=(3,4));var=tk.StringVar(self);self.variables[key]=var
            if key in ('start','end'):
                var.set(self.state.get(key,''));widget=Field(tile,textvariable=var,width=18)
                widget.entry.bind('<Return>',lambda _:self.apply());widget.entry.bind('<FocusOut>',lambda _:self.apply())
            else:
                widget=Select(tile,textvariable=var,width=18);self.choices[key]=widget
                widget.bind('<<ComboboxSelected>>',lambda _:self.apply())
            widget.pack(fill='x')
        self.update_options([]);self.bind('<Configure>',self.layout);self.pack(fill='x',pady=(0,8))
        row=app.row(parent);app.button(row,'应用筛选',self.apply,False,108);app.button(row,'重置筛选',self.reset,False,108)
    def layout(self,event):
        columns=max(1,min(4,int(event.width/px(self,190))))
        for i in range(4):self.columnconfigure(i,weight=1 if i<columns else 0,uniform='filters' if i<columns else '')
        for i,tile in enumerate(self.tiles):tile.grid(row=i//columns,column=i%columns,sticky='ew',padx=(0,px(self,10)) if i%columns<columns-1 else 0,pady=(0,px(self,7)))
    def update_options(self,items):
        for key,labels in (('period',PERIODS),('sort',SORTS)):
            values=[tr(v) for v in labels];self.lookup[key]=dict(zip(values,range(len(values))));self.choices[key].configure(values=values);self.variables[key].set(values[self.state.get(key,0)])
        for key,field,label in (('phase','session_type','全部阶段'),('track','track','全部赛道'),('car','vehicle','全部车辆')):
            raw=sorted({str(v.get(field,'')) for v in items if v.get(field)}|({self.state[key]} if self.state.get(key) else set()))
            labels=[tr(label)]+[display(v) if key=='track' else tr(v) for v in raw]
            # Keep same-circuit variants distinguishable in the filter options.
            if key=='track':labels=[tr(label)]+[display(v)+' · '+v if sum(display(x)==display(v) for x in raw)>1 else display(v) for v in raw]
            self.lookup[key]=dict(zip(labels,['']+raw));self.choices[key].configure(values=labels)
            self.variables[key].set(next(k for k,v in self.lookup[key].items() if v==self.state.get(key,'')))
    def apply(self):
        for key,var in self.variables.items():self.state[key]=var.get() if key in ('start','end') else self.lookup[key].get(var.get(),self.state.get(key))
        self.app.populate()
    def reset(self):
        self.state.update(period=0,sort=0,phase='',track='',car='',start='',end='')
        for key in ('start','end'):self.variables[key].set('')
        self.update_options(self.app.items);self.app.search.set('');self.app.populate()
