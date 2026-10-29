"""One reusable full-record manager, sharing native lists and protected editors."""
from pathlib import Path
import tkinter as tk
from control_worklist import WorkList
from control_fields import Select
from control_theme import T
from control_widgets import px
from i18n import tr
from library import inventory
from track_names import display,search_text
from record_presentation import session_type
from race_mode import mode,LABELS

STATES=dict(complete='已结束',recording='正在记录',interrupted='记录中断',write_error='写入错误')


class Host:
    """The HUD and control center use the same widgets and owner close registry."""
    def __init__(self,owner,root):object.__setattr__(self,'owner',owner);self.data_path=root;self.status=Notice(self);self.view=None
    def __getattr__(self,name):return getattr(self.owner,name)
    def __setattr__(self,name,value):
        if name in ('owner','data_path','status','view'):object.__setattr__(self,name,value)
        else:setattr(self.owner,name,value)
    def label(self,*args,**kwargs):
        from control_center import ControlCenter
        return ControlCenter.label(self,*args,**kwargs)
    def row(self,*args,**kwargs):
        from control_center import ControlCenter
        return ControlCenter.row(self,*args,**kwargs)
    def button(self,*args,**kwargs):
        from control_center import ControlCenter
        return ControlCenter.button(self,*args,**kwargs)


class Notice:
    def __init__(self,host):self.host=host;self.value=''
    def set(self,text):
        self.value=text;host=self.host
        if host.view is not None and host.view.alive():host.view.say(text)
        status=getattr(host.owner,'status',None)
        if isinstance(status,tk.Variable) and status._tk is not None and not host.owner.closing:status.set(text)


def show(owner,root,render_review,make_report,initial=()):
    root=Path(root).resolve();windows=getattr(owner,'library_windows',{});owner.library_windows=windows;old=windows.get(str(root))
    if old is None or not old.winfo_exists():
        for peer in (getattr(owner,'hud',None),getattr(owner,'control_center',None),getattr(getattr(owner,'on_menu',None),'__self__',None)):
            candidate=getattr(peer,'library_windows',{}).get(str(root))
            if candidate is not None and candidate.winfo_exists():old=candidate;windows[str(root)]=old;contexts=getattr(owner,'library_context',{});contexts[str(root)]=old.library.context;owner.library_context=contexts;break
    if old is not None and old.winfo_exists():
        old.deiconify();old.lift()
        if initial:old.library.locate(initial)
        return old
    view=Library(owner,root,render_review,make_report);windows[str(root)]=view.window
    view.refresh()
    if initial:view.locate(initial)
    return view.window


class Library(WorkList):
    def __init__(self,owner,root,render_review,make_report):
        self.owner=owner;self.root_path=root;self.working=False;self.pending_refresh=False;self.targets=set();self.pending_selection=();self.return_view=None;self.did_locate=False
        from simulators import root_identity
        from simulator_profiles import capabilities
        self.capabilities=capabilities(root_identity(root))
        contexts=getattr(owner,'library_context',{});owner.library_context=contexts;self.context=contexts.setdefault(str(root),{})
        self.restore_position=self.context.get('offset',0),self.context.get('xoffset',0)
        host=Host(owner,root)
        if not hasattr(owner,'configure_styles'):
            from control_center import ControlCenter
            ControlCenter.configure_styles(host)
        columns=[('date','记录日期',165),('track','赛道',180)]
        if not self.capabilities.reference_laps:columns.append(('layout','具体布局',165))
        columns.extend([('vehicle','车辆',165),('best','最快圈 s',95),('phase','阶段',85),('mode','参赛方式',100)])
        if self.capabilities.reference_laps:columns.append(('stable','稳定性 σ s',100))
        columns.extend([('source','来源',110),('state','状态',100),('note','备注 / 交通',240)])
        super().__init__(host,'Stintrix · 比赛记录管理',columns,
            lambda item:str(Path(item['folder']).resolve()),self.format_entry,filters=dict(all='全部来源',Logs='Logs',ImportedLogs='ImportedLogs',RecoveredLogs='RecoveredLogs',DemoLogs='DemoLogs'),accept=self.matches,detail=self.describe,
            hint='搜索阶段、日期、车手或备注；可多选 1–6 场对比，原始记录保留。' if self.capabilities.reference_laps else 'AC EVO：搜索赛道、布局、车辆或备注；可选择 1–2 场进行圈 A / 圈 B 对比。',searchable=lambda item:search_text(item['track'])+' '+item.get('driver',''),include=lambda item:str(Path(item['folder']).resolve()) in self.targets)
        host.view=self;self.window.library=self;self.window.geometry('1160x730');self.window.minsize(900,650);self.details.configure(height=2)
        self.search.placeholder='搜索赛道、布局、车辆、日期或备注';self.search.paint()
        self.track=tk.StringVar(self.window,value=self.context.get('track',''));self.car=tk.StringVar(self.window,value=self.context.get('car',''))
        self.participation=tk.StringVar(self.window,value=self.context.get('mode',''))
        self.query.set(self.context.get('query',''));self.view.set(self.context.get('source','all'));self.remembered=tuple(self.context.get('selected',()))
        self.table.configure_columns(self.context.get('columns',self.table.columns),self.context.get('frozen',()),self.context.get('widths',{}))
        self.table.sort_state=tuple(self.context['sort']) if self.context.get('sort') else None
        parent=self.table.master;self.facets=tk.Frame(parent,bg=T.CARD);self.facet_boxes={}
        for key,title,var in [('track','赛道',self.track),('car','车辆',self.car)]:
            tile=tk.Frame(self.facets,bg=T.CARD);tile.pack(side='left',fill='x',expand=True,padx=(0,8));host.label(tile,title,9,T.MUTED).pack(anchor='w');box=Select(tile,textvariable=var,values=[''],labels={'':'全部赛道' if key=='track' else '全部车辆'},width=16);box.pack(fill='x',pady=3);box.bind('<<ComboboxSelected>>',self.filters_changed);self.facet_boxes[key]=box
        tile=tk.Frame(self.facets,bg=T.CARD);tile.pack(side='left',fill='x',expand=True);host.label(tile,'参赛方式',9,T.MUTED).pack(anchor='w');box=Select(tile,textvariable=self.participation,values=['','unknown','online','single'],labels={'':'全部参赛方式',**LABELS},width=16);box.pack(fill='x',pady=3);box.bind('<<ComboboxSelected>>',self.filters_changed);self.facet_boxes['mode']=box
        self.facet_button=host.button(self.search.master,'筛选条件',self.toggle_facets,False,110);self.facet_button.pack(side='right',padx=(8,0))
        if self.context.get('facets'):self.facets.pack(fill='x',before=self.table)
        self.location=tk.Frame(parent,bg=T.CARD);host.label(self.location,'已定位赛事；当前筛选保持不变',9,T.ACCENT).pack(side='left');host.button(self.location,'返回原筛选',self.restore_location,False,140).pack(side='right')
        self.query_trace=self.query.trace_add('write',self.query_changed);self.filter.bind('<<ComboboxSelected>>',self.filters_changed)
        from control_library_actions import Actions
        self.operations=Actions(self,render_review,make_report)
        self.on_loaded=self.loaded;self.window.protocol('WM_DELETE_WINDOW',self.close);self.window.bind('<Escape>',lambda _:(self.close(),'break')[1]);self.window.bind('<F5>',lambda _:(self.refresh(),'break')[1]);self.window.retranslate=self.translate
        self.table.bind('<Return>',lambda _:self.operations.open_review());self.table.bind('<Double-1>',lambda _:self.operations.open_review());self.restoring=True
    def format_entry(self,item):
        note=(tr('交通 · ') if item['traffic'] else '')+item['note']
        values=dict(date=item['date'][:19].replace('T',' '),track=display(item['track']),layout=item.get('track_layout') or '—',vehicle=item['vehicle'],best=f"{item['time_s']:.3f}" if item['time_s'] else '—',phase=session_type(item['session_type']),mode=tr(LABELS[mode(item)]),stable=f"{item['stability_s']:.3f}" if item['stability_s'] is not None else tr('未分析'),source=item['source'],state=tr(STATES.get(item['status'],item['status'])),note=' · '.join(note.splitlines()))
        return tuple(values[key] for key,_,_ in self.columns)
    def describe(self,item):return ' · '.join(v for v in (display(item['track']),item.get('track_layout'),item['vehicle']) if v)+'\n'+item['folder']+('\n'+item['note'] if item['note'] else '')
    def matches(self,item,source):return (source=='all' or item['source']==source) and (not self.track.get() or item['track']==self.track.get()) and (not self.car.get() or item['vehicle']==self.car.get()) and (not self.participation.get() or mode(item)==self.participation.get())
    def capture(self):
        base=self.return_view or dict(selected=self.remembered,offset=self.table.offset,xoffset=self.table.xoffset)
        facets=bool(self.facets.winfo_manager()) if self.facets.winfo_exists() else self.context.get('facets',False)
        self.context.update(query=self.query.get(),source=self.view.get(),track=self.track.get(),car=self.car.get(),mode=self.participation.get(),selected=list(base['selected']),offset=base['offset'],xoffset=base['xoffset'],widths=dict(self.table.widths),columns=list(self.table.displaycolumns),frozen=list(self.table.frozen_columns),sort=self.table.sort_state,facets=facets)
    def selected(self,event=None):
        super().selected(event)
        if event is not None and hasattr(self,'track'):self.capture()
    def toggle_facets(self):
        self.facets.pack_forget() if self.facets.winfo_manager() else self.facets.pack(fill='x',before=self.table)
        self.capture()
    def query_changed(self,*_):
        self.context['query']=self.query.get();self.targets.clear();self.pending_selection=();self.did_locate=False;self.return_view=None;self.location.pack_forget()
    def filters_changed(self,_=None):self.targets.clear();self.pending_selection=();self.did_locate=False;self.return_view=None;self.location.pack_forget();self.render();self.capture()
    def reset_filters(self):self.track.set('');self.car.set('');self.participation.set('');self.view.set('all');self.query.set('');self.search.flush(True);self.filters_changed()
    def render(self):
        if not self.alive():return
        super().render()
        count=bool(self.track.get())+bool(self.car.get())+bool(self.participation.get());self.facet_button.configure(text=tr('筛选条件')+(f' · {count}' if count else ''))
        if not self.loading and not self.error and self.items and not self.table.rows:self.table.set_empty('没有匹配的项目','重置筛选',self.reset_filters)
        if self.pending_selection:
            chosen=tuple(key for key in self.pending_selection if key in self.table.rows)
            if chosen:
                self.pending_selection=();self.remembered=chosen;self.table.selection_set(chosen);self.window.update_idletasks();self.table.scroller.move(self.table.order.index(chosen[0])*self.table.rowheight)
        if hasattr(self,'track'):self.capture()
    def locate(self,folders):
        values=tuple(str(Path(folder).resolve()) for folder in folders if Path(folder).resolve().is_relative_to(self.root_path))
        if not values:return
        temporary=bool(self.query.get().strip() or self.view.get()!='all' or self.track.get() or self.car.get() or self.participation.get() or self.remembered and set(self.remembered)!=set(values))
        if temporary and not self.return_view:self.return_view=dict(selected=self.remembered,offset=self.table.offset,xoffset=self.table.xoffset)
        self.targets=set(values) if temporary else set();self.pending_selection=values;self.did_locate=True
        self.location.pack(fill='x',before=self.table) if temporary else self.location.pack_forget()
        self.render()
        if not self.loading and any(key not in self.items for key in values):self.refresh()
    def restore_location(self):
        old=self.return_view;self.targets.clear();self.pending_selection=();self.return_view=None;self.location.pack_forget()
        if old:self.remembered=old['selected']
        self.render()
        if old:self.table.scroller.move(old['offset']);self.table.xoffset=old['xoffset'];self.table.schedule()
    def refresh(self):
        if self.loading or self.working:self.pending_refresh=True;return
        path=self.root_path;self.load(lambda:inventory(path),'记录清单已更新；搜索、选择与位置保留。')
    def loaded(self):
        if self.restoring:
            self.restoring=False
            if not self.did_locate:self.table.scroller.move(self.restore_position[0]);self.table.xoffset=self.restore_position[1];self.table.schedule()
        for key,var,field in [('track',self.track,'track'),('car',self.car,'vehicle')]:
            values=sorted({item[field] for item in self.items.values()});values=['',*values] if not var.get() or var.get() in values else ['',var.get(),*values];box=self.facet_boxes[key];box.labels={'':'全部赛道' if key=='track' else '全部车辆',**{v:display(v) if key=='track' else v for v in values if v}};box.configure(values=values)
        if self.pending_selection and not self.error:self.say('尚未在列表找到目标赛事，可刷新或返回原筛选')
        if self.pending_refresh:self.pending_refresh=False;self.refresh()
    def sync(self):
        super().sync()
        if self.alive() and hasattr(self,'operations'):self.operations.sync()
    def translate(self):
        super().translate()
        if hasattr(self,'facet_boxes'):
            box=self.facet_boxes['track'];box.labels={value:display(value) if value else '全部赛道' for value in box.values};box.paint()
        if hasattr(self,'operations'):self.operations.translate()
    def close(self):self.capture();self.window.destroy()
    def dispose(self,event):
        if event.widget is self.window:
            self.capture();self.query.trace_remove('write',self.query_trace)
            self.operations.dispose()
            for var in (self.track,self.car,self.participation):var.__del__();var._tk=None
        super().dispose(event)
