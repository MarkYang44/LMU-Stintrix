"""On-demand session rhythm reuses the history chart, without reading telemetry."""
import tkinter as tk
from control_theme import T
from control_widgets import px
from control_history_chart import ProgressChart


class Rhythm:
    def __init__(self,app,body,header,table,ready,*,footer=()):
        self.app=app;self.table=table;self.ready=ready;self.rows={};self.chart=None;self.visible=False;self.target=None;self.layout=dict(table.pack_info());self.layout.pop('in',None)
        self.footer=[]
        for widget in footer:
            layout=dict(widget.pack_info());layout.pop('in',None)
            siblings=widget.master.pack_slaves();following=siblings[siblings.index(widget)+1:]
            if following:layout['before']=following[0]
            self.footer.append((widget,layout))
        siblings=body.pack_slaves();position=siblings.index(table)
        if position+1<len(siblings):self.layout['before']=siblings[position+1]
        self.host=tk.Frame(body,bg=T.CARD)
        self.button=app.button(header,'圈速节奏',self.toggle,False,130)
    def set(self,rows):
        self.rows=rows;self.sync_button()
        if self.visible:self.render()
    def set_target(self,target):
        if self.target==target:return
        self.target=target
        if self.visible:self.render()
    def render(self):
        entries=[dict(key=key,number=row['lap']['num'],time_s=row['lap']['time']) for key,row in self.rows.items() if row['usable']]
        self.chart.empty_text='当前筛选中没有完整有效圈'
        self.chart.set(sorted(entries,key=lambda e:e['number']),target=self.target)
    def toggle(self):
        if not self.ready() or self.app.closing:return
        self.set_view(not self.visible)
    def set_view(self,value):
        self.visible=value
        for widget,layout in self.footer:
            widget.pack_forget() if value else widget.pack(**layout)
        if value:
            if self.chart is None:
                hint=self.app.label(self.host,'点击数据点，或用 ← → 选点、Enter 返回列表选圈；间断处不连接，未作条件校正。',9,T.MUTED);hint.pack(fill='x',pady=4)
                hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(80,e.width)))
                self.chart=ProgressChart(self.host,self.choose,height=240,axis='lap');self.chart.pack(fill='both',expand=True)
            self.table.pack_forget();self.host.pack(**self.layout);self.render();self.chart.focus_set()
        else:
            self.host.pack_forget();self.table.pack(**self.layout);self.table.viewport.focus_set()
        self.sync_button()
    def sync_button(self):
        self.button.configure(text='返回圈速表' if self.visible else '圈速节奏',selected=self.visible)
        self.button.configure(width=max(px(self.button,130),self.button.font.measure(self.button.cget('text'))+px(self.button,36)))
    def choose(self,entry):
        if not self.ready() or entry['key'] not in self.table.rows:return
        self.set_view(False);key=entry['key'];self.table.selection_set((key,));self.table.scroller.move(self.table.order.index(key)*self.table.rowheight)
