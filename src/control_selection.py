"""One line above a session list: what is selected, read before anything opens."""
import tkinter as tk
from tkinter import font as tkfont
from control_theme import T
from i18n import tr


class SelectionLine(tk.Frame):
    """Key facts in the foreground, details muted; one line, so rows never move."""
    def __init__(self,parent):
        super().__init__(parent,bg=parent.cget('bg'))
        self.lead=tk.Label(self,bg=self.cget('bg'),fg=T.FG,font=(T.FONT,10,'bold'),anchor='w',padx=0,pady=0,bd=0)
        self.rest=tk.Label(self,bg=self.cget('bg'),fg=T.MUTED,font=(T.FONT,9),anchor='w',padx=0,pady=0,bd=0)
        self.lead.pack(side='left');self.rest.pack(side='left',fill='x',expand=True,padx=(10,0))
        self.full=('','');self.font=tkfont.Font(self,font=self.rest.cget('font'))
        bold=tkfont.Font(self,font=self.lead.cget('font'));height=max(bold.metrics('linespace'),self.font.metrics('linespace'))+2;bold.__del__();bold.delete_font=False
        self.configure(height=height);self.pack_propagate(False)
        from control_tooltip import Tooltip
        self.tip=Tooltip(self.rest)
        self.rest.bind('<Enter>',self.hint);self.rest.bind('<Leave>',lambda _:self.tip.hide())
        self.bind('<Configure>',lambda _:self.fit());self.bind('<Destroy>',self.dispose,add='+')
    def dispose(self,event):
        if event.widget is self:self.tip.hide();self.font.__del__();self.font.delete_font=False
    def set(self,lead,rest):
        if self.full==(lead,rest):return
        self.full=(lead,rest);self.lead.configure(text=lead)
        if lead:self.lead.pack(side='left',before=self.rest);self.rest.pack_configure(padx=(10,0))
        else:self.lead.pack_forget();self.rest.pack_configure(padx=0)
        self.fit()
    def fit(self):
        text=self.full[1];room=max(1,self.winfo_width()-(self.lead.winfo_reqwidth()+12 if self.full[0] else 0))
        if self.font.measure(text)>room:
            while text and self.font.measure(text+'…')>room:text=text[:-1]
            text+='…'
        self.rest.configure(text=text)
    def hint(self,_=None):
        if self.rest.cget('text')!=self.full[1]:self.tip.request(self.full,self.full[1],self.rest.winfo_rootx(),self.rest.winfo_rooty()+self.rest.winfo_height())
    def retranslate(self):self.fit()


def facts(app):
    """(lead, rest) for the current selection of the session list."""
    table=app.tree
    if table is None or not table.winfo_exists():return '',''
    ids=table.selection();total=len(table.get_children())
    if not ids:return '',tr('列表 {total} 场 · 单击查看要点，双击或 Enter 打开复盘').format(total=total)
    if len(ids)>1:
        note=tr('选 2 场可对比两场最快圈') if len(ids)>2 else tr('可对比两场最快圈或圈 A / 圈 B')
        return tr('已选 {count} 场').format(count=len(ids)),tr('列表 {total} 场').format(total=total)+' · '+note
    values=dict(zip(table.columns,table.rows.get(ids[0],())))
    def pick(key):
        value=str(values.get(key) or '').strip()
        return '' if value in ('','—','-') else value
    stage=' '.join(v for v in (pick('type'),pick('result')) if v)
    best=tr('最快圈')+' '+pick('lap')+(' PB' if ids[0] in getattr(table,'marked',()) else '') if pick('lap') else ''
    lead=' · '.join(v for v in (pick('track'),stage,best) if v)
    detail=app.event_detail.get() if getattr(app,'event_detail',None) is not None else ''
    layout=pick('layout')
    if pick('track') and layout.startswith(pick('track')):layout=layout[len(pick('track')):].lstrip(' ·')  # "Spa · 7.004 km" -> "7.004 km"
    rest=' · '.join(v for v in (pick('car'),layout,pick('class'),pick('mode'),detail) if v)
    return lead,rest
