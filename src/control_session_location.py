"""Temporarily reveal one imported session without replacing the user's filters."""
import json,os,tkinter as tk
from pathlib import Path
from control_theme import T
from i18n import tr


def identity(value):return os.path.normcase(os.path.abspath(str(value)))


def locate(app,folder):
    folder=Path(folder).resolve()
    if not folder.is_relative_to(app.data_path.resolve()) or not (folder/'session.json').is_file():
        app.status.set(tr('赛事目录不可用或尚未完整保存'));return False
    if app.page==1:app.browsing.capture(app)
    previous=getattr(app,'session_location',None);origin=dict(previous['origin'] if previous else app.browsing.states.get(1,{}))
    app.session_location=dict(folder=str(folder),origin=origin,signature=None,pending=True)
    app.show_page(1);app.root.lift();return True


class SessionLocation:
    def __init__(self,app,parent):
        self.app=app;self.frame=tk.Frame(parent,bg=T.CARD)
        self.label=app.label(self.frame,'',9,T.ACCENT);self.label.pack(side='left',fill='x',expand=True);self.label.bind('<Configure>',lambda e:self.label.configure(wraplength=max(100,e.width)))
        app.button(self.frame,'返回原筛选',self.restore,False,140)
    def signature(self):return (self.app.search.get(),json.dumps(self.app.review_filters.state,sort_keys=True))
    def augment(self,pairs):
        request=getattr(self.app,'session_location',None)
        if not request:self.frame.pack_forget();return pairs,None
        signature=self.signature()
        if request['signature'] is None:request['signature']=signature
        elif request['signature']!=signature:
            self.app.session_location=None;self.frame.pack_forget();return pairs,None
        target=next(((i,e) for i,e in enumerate(self.app.items) if identity(e['folder'])==identity(request['folder'])),None)
        self.frame.pack(fill='x',before=self.app.search_target.master,pady=(0,6))
        if target is None:self.label.configure(text=tr('尚未在列表找到目标赛事，可刷新或返回原筛选'));return pairs,None
        outside=all(i!=target[0] for i,_ in pairs)
        if outside:pairs=[target,*pairs]
        self.label.configure(text=tr('已定位赛事；当前筛选保持不变')+(' · '+tr('临时显示筛选外的 1 场赛事') if outside else ''))
        chosen=str(target[0]) if request['pending'] else None;request['pending']=False
        return pairs,chosen
    def reveal(self,iid):
        table=self.app.tree
        if iid in table.order:
            table.cursor=iid;table.set_offset(min(table.order.index(iid)*table.rowheight,table.limit()))
    def restore(self):
        request=getattr(self.app,'session_location',None);self.app.session_location=None;self.frame.pack_forget()
        if not request:return
        origin=request['origin'];self.app.browsing.states[1]=origin
        self.app.populate(self.app.browsing.selected(1,self.app.items));self.app.browsing.restore(self.app,True);self.app.status.set(tr('已返回原筛选与选择'))
