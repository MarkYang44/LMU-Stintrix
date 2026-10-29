"""One selection surface moves between archive and storage tasks without reloading."""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from control_theme import T
from control_flow import install
from control_widgets import px
from control_action_menu import ActionMenu,MenuAction
from i18n import tr
from track_names import display


class DataBrowser:
    def __init__(self,app,parent,packages,storage,summary_host):
        self.app=app;self.packages=packages;self.storage=storage;self.summary_host=summary_host;self.toolbar={};self.conditions={};self.token=None
        self.host=tk.Frame(parent,bg=T.CARD);self.host.retranslate=self.translate
        app.sessions(self.host,True,True,False,compact_actions=True,height=4)
        self.table=app.tree;self.filters=app.review_filters
        self.filter_button=app.button(app.search_target.master,'筛选条件',self.toggle_filters,False,110)
        self.filters_open=getattr(app,'data_filters_open',False)
        if not self.filters_open:self.filters.pack_forget()
        self.filters.compact(self.table)
        self.summary=tk.StringVar(summary_host);summary_host.selection_summary=self.summary
        self.count=tk.StringVar(summary_host);summary_host.selection_count=self.count;row=app.row(summary_host);row.pack_configure(pady=2)
        app.label(row,self.count,9,T.MUTED).pack(side='left',fill='x',expand=True)
        from control_sections import Disclosure
        self.details=Disclosure(summary_host,app,'storage-selection-details','查看已选赛事',header=row)
        self.selection_text=tk.Text(self.details.body,height=4,wrap='word',bg=T.CARD,fg=T.FG,insertbackground=T.FG,selectbackground=T.SELECT,font=(T.FONT,9),relief='flat',highlightthickness=0,state='disabled')
        bar=ttk.Scrollbar(self.details.body,orient='vertical',command=self.selection_text.yview,style='Lab.Vertical.TScrollbar');bar.pack(side='right',fill='y');self.selection_text.configure(yscrollcommand=bar.set);self.selection_text.pack(fill='x',expand=True)
        self.picker_button=None
        self.picker_open=getattr(app,'storage_picker_open',True);self.sync()
        self.resize_binding=app.scroll.bind('<Configure>',self.resize_table,add='+');self.host.bind('<Destroy>',self.dispose,add='+')
    def alive(self):return not self.app.closing and self.app.page==3 and bool(self.host.winfo_exists())
    def selected(self):
        return [self.app.items[int(i)] for i in self.table.selection() if str(i).isdigit() and int(i)<len(self.app.items)]
    def mount(self,name):
        self.host.pack_forget()
        if name=='packages':self.packages.pack(fill='x');self.host.pack(in_=self.packages,fill='x')
        elif name=='storage':
            self.host.pack(in_=self.storage,fill='x');self.show_picker()
        if self.app.pages.building is None:self.app.install_toolbar()
        self.resize_table();self.sync()
    def resize_table(self,_=None):
        if not self.alive():return
        rows=4
        if self.app.data_tasks.current=='packages':rows=max(4,min(10,4+int((self.app.scroll.winfo_height()-px(self.host,429))/self.table.rowheight)))
        height=round(rows*self.table.rowheight)
        if int(self.table.viewport.cget('height'))!=height:self.table.viewport.configure(height=height)
    def dispose(self,event):
        if event.widget is self.host:self.app.scroll.unbind('<Configure>',self.resize_binding)
    def show_picker(self):
        if self.picker_open:self.storage.pack(fill='x',pady=5)
        else:self.storage.pack_forget()
        button=self.toolbar.get('picker')
        if button is not None and button.winfo_exists():button.configure(text=tr('收起赛事列表' if self.picker_open else '选择赛事'))
    def toggle_picker(self):
        self.picker_open=not self.picker_open;self.app.storage_picker_open=self.picker_open;self.show_picker()
    def toggle_filters(self):
        self.filters_open=not self.filters_open;self.app.data_filters_open=self.filters_open
        if self.filters_open:self.filters.pack(fill='x',pady=8,before=self.table)
        else:self.filters.pack_forget()
        self.sync()
    def ready(self,offline=False):
        from control_batch import running
        items=self.selected()
        return bool(items) and all(e.get('status') not in ('recording','write_error') for e in items) and running(self.app) is None and (not offline or not self.app.active())
    def install_actions(self,host):
        from control_batch import show,running
        app=self.app;section=app.data_tasks.current
        from simulator_profiles import capabilities
        supported=capabilities(getattr(app,'simulator','lmu'))
        if section not in ('packages','storage'):return
        host.pack(fill='x',before=app.shell.scroll.master,pady=(0,6));row=app.row(host);install(row);self.toolbar={};self.conditions={}
        def button(key,title,command,condition,primary=False):
            b=app.button(row,title,command,primary,125);b.configure(height=px(b,38));self.toolbar[key]=b;self.conditions[key]=condition
        if section=='packages':
            button('export','导出赛事包',app.export_package,lambda:self.ready(),True)
            button('import','导入赛事包',app.import_package,lambda:running(app) is None)
            if supported.native_import:button('native','导入官方遥测',app.import_native,lambda:running(app) is None)
        else:
            button('csv','导出原始 CSV',lambda:app.storage_operation('csv'),lambda:self.ready(True),True)
            if supported.full_review:button('html','导出独立复盘页',lambda:app.storage_operation('html'),lambda:self.ready(True))
            button('picker','收起赛事列表' if self.picker_open else '选择赛事',self.toggle_picker,lambda:True)
            self.picker_button=self.toolbar['picker'];b=self.picker_button;b.configure(width=max(b.font.measure(tr(text))+px(b,36) for text in ('选择赛事','收起赛事列表')))
        trigger=app.button(row,'更多操作 ▾',lambda:menu.toggle(),False,110);trigger.configure(height=px(trigger,38))
        from control_event_filters import edit_note
        from control_split_checks import show as split
        from control_maintenance import reports,caches
        actions=[MenuAction('tasks','批量任务与失败重试',lambda:show(app),'任务'),
            MenuAction('reports','报告任务与分步重试',lambda:reports(app,[item['folder'] for item in self.selected()]),'任务'),
            MenuAction('caches','缓存与导出文件',lambda:caches(app),'存储'),
            MenuAction('all','全选当前列表',lambda:self.table.selection_set(self.table.get_children()),'选择',lambda:bool(self.table.rows)),
            MenuAction('clear','清除选择',lambda:self.table.selection_set(()),'选择',lambda:bool(self.table.selection())),
            MenuAction('note','收藏与标签',lambda:app.with_selection(lambda items:edit_note(app,items[0],app.refresh)),'整理',lambda:len(self.selected())==1 and running(app) is None),
            MenuAction('split','检查疑似拆分',lambda:split(app),'整理',visible=lambda:supported.full_review)]
        if section=='storage':
            actions.extend([MenuAction('compress','压缩选中赛事',app.compress_selected,'存储',lambda:self.ready()),
                MenuAction('columnar','转换选中赛事为列式',lambda:app.storage_operation('columnar'),'存储',lambda:self.ready(True)),
                MenuAction('restore','恢复选中赛事为 CSV',lambda:app.storage_operation('restore'),'存储',lambda:self.ready(True))])
        from control_table_layouts import actions as column_actions
        actions.extend(column_actions(self.table));menu=ActionMenu(trigger,actions,'数据操作',lambda:app.selected_count.get());self.menu=menu;self.sync()
    def sync(self):
        if not self.alive():return
        self.filters.sync_chips()
        from event_filters import DEFAULTS
        from control_batch import running
        import i18n
        ids=tuple(self.table.selection());token=(ids,id(self.app.items),i18n.language)
        if token!=self.token:
            self.token=token;items=self.selected()
            names=[e.get('date','')[:19].replace('T',' ')+' · '+display(e.get('track',''))+' · '+e.get('vehicle','') for e in items]
            self.count.set(tr('已选 {count} 场赛事').format(count=len(items)))
            self.summary.set(tr('已选 {count} 场赛事').format(count=len(items))+'\n'+'\n'.join(names) if items else tr('尚未选择赛事；可在本页列表勾选。'))
            self.selection_text.configure(state='normal');self.selection_text.delete('1.0','end');self.selection_text.insert('1.0',self.summary.get());self.selection_text.configure(state='disabled')
        active=sum(v!=DEFAULTS.get(k) for k,v in self.filters.state.items() if k not in ('query','sort'))
        title=tr('筛选条件')+(f' · {active}' if active else '')
        if self.filter_button.label!=title or self.filter_button.selected!=self.filters_open:self.filter_button.configure(text=title,selected=self.filters_open)
        for key,b in self.toolbar.items():
            if b.winfo_exists():
                state='normal' if self.conditions[key]() else 'disabled'
                if b.cget('state')!=state:b.configure(state=state)
        ready=self.ready(True)
        for key,b in getattr(self.app,'storage_buttons',{}).items():
            enabled=self.ready() if key=='compress' else ready
            if b.winfo_exists() and b.enabled!=enabled:b.configure(state='normal' if enabled else 'disabled')
    def translate(self):
        self.token=None;self.sync();self.show_picker()
        for b in [self.filter_button,*self.toolbar.values(),*getattr(self.app,'storage_buttons',{}).values()]:
            if b.winfo_exists():b.configure(width=max(px(b,110),b.font.measure(tr(b.label))+px(b,36)));b.paint()
