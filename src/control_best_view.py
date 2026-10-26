"""A record list uses available space and offers direct list/detail navigation."""
from control_widgets import px
from event_filters import DEFAULTS


class Layout:
    def __init__(self,page,info):
        self.page=page;self.info=info;self.job=None;self.closed=False
        self.binding=page.app.scroll.bind('<Configure>',lambda _:self.schedule(),add='+')
        page.cleanups.append(self.dispose);self.schedule()
    def schedule(self):
        if self.closed:return
        if self.job is not None:self.page.host.after_cancel(self.job)
        self.job=self.page.host.after_idle(self.resize)
    def resize(self):
        self.job=None;p=self.page
        if not p.alive() or p.table.winfo_width()<2:return
        doc=p.app.pages.active.frame;top=p.table.viewport.winfo_rooty()-doc.winfo_rooty()
        available=p.app.scroll.winfo_height()-top-px(p.host,12)
        rows=max(4,min(8,int(available/p.table.rowheight)))
        target=round(rows*p.table.rowheight)
        if int(p.table.viewport.cget('height'))!=target:p.table.viewport.configure(height=target)
    def empty(self):
        p=self.page;active=any(value!=DEFAULTS.get(key) for key,value in p.modes.state.items() if key not in ('query','sort'))
        if p.query.get().strip():text='没有匹配的纪录；清空搜索后保留筛选。';label='清空搜索';command=p.search_field.clear
        elif active:text='当前筛选下没有纪录。';label='重置筛选';command=p.modes.reset
        else:text='暂无符合条件的有效赛道纪录。';label='刷新记录';command=p.refresh_records
        p.table.set_empty(text,label,command)
    def details(self):
        p=self.page
        if not p.alive() or p.selected is None:return
        p.app.shell.scroller.cancel();p.app.root.update_idletasks()
        doc=p.app.pages.active.frame;top=self.info.winfo_rooty()-doc.winfo_rooty()-px(p.host,12)
        if p.app.scroll.canvasy(0)<top-px(p.host,10):p.context['detail_return']=p.app.scroll.yview()[0]
        p.context['in_details']=True
        p.app.scroll.yview_moveto(max(0,top)/max(1,doc.winfo_height()))
    def listing(self):
        p=self.page
        if not p.alive():return
        p.context['in_details']=False;p.app.shell.scroller.cancel();p.app.scroll.yview_moveto(p.context.get('detail_return',0));p.table.viewport.focus_set()
    def dispose(self):
        self.closed=True;self.page.app.scroll.unbind('<Configure>',self.binding)
        if self.job is not None:self.page.host.after_cancel(self.job);self.job=None
