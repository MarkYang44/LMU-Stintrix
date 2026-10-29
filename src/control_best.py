"""Personal bests use the same bounded browsing and export workflow as history."""
import json
import tkinter as tk
from functools import partial
from pathlib import Path
from control_record_browser import RecordPage,CurveExport,curve_identity
from control_record_details import DetailLoader
from control_list import SessionList
from control_metrics import Metrics
from control_record_art import RecordHeader
from control_feedback import record_improvements
from control_mode_filters import ModeControls
from control_event_filters import edit_note
from control_theme import T
from control_widgets import px
from control_flow import install
from i18n import tr
from race_mode import mode,LABELS
from record_presentation import present
from track_names import display,layout

COLUMNS=(('track','赛道',165),('time','最快圈',110),('layout','布局 / 长度',160),('class','组别',80),('mode','参赛方式',90),('car','车辆',225))


def detail_key(entry):
    return curve_identity(entry),json.dumps(dict(lap=entry['lap'],conditions=entry.get('conditions')),sort_keys=True,default=str)


def read_records(root):
    import control_records as source
    return source.attach(root,source.entries(root))


def read_detail(entry):
    import control_records as source
    return source.detail(entry)


class BestPage(RecordPage):
    def __init__(self,app):
        body=app.card('',compact=True);super().__init__(app,'best',body)
        self.identity=lambda e:(str(e['folder']),e['lap']['number'],e['identity'])
        self.entries=[];self.state=dict(data=None,error=None,loading=False,vehicle=None);self.fixed={}
        row=app.row(body);self.search(row,command=self.populate_best)
        self.button(row,'filters','筛选条件',self.toggle_filters)
        self.button(row,'refresh','刷新记录',self.refresh_records,lambda:not self.loader.running)
        self.modes=ModeControls(body,app,self.populate_best,'best_mode_filters');self.modes.bind_query(self.query)
        self.query.trace_add('write',lambda *_:self.modes.state.update(query=self.query.get()))
        if not self.context.get('filters_open',False):self.modes.pack_forget()
        self.modes.hint.configure(text='每个赛道布局、车辆组别各保留最快有效圈；No BOP 特殊版本单独保留。天气与车辆条件仅代表已记录有效圈。')
        self.table=SessionList(body,columns=tuple(k for k,_,_ in COLUMNS),height=4)
        for key,_,width in COLUMNS:self.table.column(key,width=width*self.table.s,minwidth=(80 if key=='class' else 65)*self.table.s,stretch=key in ('track','layout','car'))
        from control_table_preferences import install as preferences
        preferences(app,self.table,'best',self.modes,frozen=('track','time'));self.table.pack(fill='x',pady=8)
        self.modes.compact(self.table)
        info=app.card('纪录详情','双击记录或按 Enter 打开完整圈曲线；刷新保留选择与滚动位置。',compact=True)
        from control_best_view import Layout
        self.view_layout=Layout(self,info)
        self.header=RecordHeader(info,app);self.header.pack(fill='x',pady=(4,8))
        self.track_title=self.hint(self.header.text,'尚无选择',17,T.FG,True)
        self.time_label=self.hint(self.header.text,'—',32,T.ACCENT,True)
        self.car_label=self.hint(self.header.text,'',11,T.FG,True)
        self.date_label=self.hint(self.header.text,'')
        self.badge=self.hint(self.header.text,'',10,T.ACCENT,True)
        self.message=self.variable('message');self.hint(info,self.message)
        navigation=self.row(info)
        self.button(navigation,'previous','← 上一条',lambda:self.neighbor(-1),lambda:self.can_step(-1))
        self.position=self.variable('position');app.label(navigation,self.position,10,T.MUTED).pack(side='left',padx=8)
        self.button(navigation,'next','下一条 →',lambda:self.neighbor(1),lambda:self.can_step(1))
        self.button(navigation,'list','返回纪录列表',self.view_layout.listing)
        actions=self.row(info)
        self.exporter=getattr(app,'best_curve_export',None) or CurveExport(app);app.best_curve_export=self.exporter
        ready=lambda:self.selected is not None
        self.button(actions,'curve','打开完整圈曲线',self.curve,lambda:ready() and not self.exporter.busy,True)
        evo=getattr(app,'simulator','lmu')=='ac_evo'
        from simulator_profiles import capabilities
        supported=capabilities(getattr(app,'simulator','lmu'))
        if supported.training:self.button(actions,'training','训练优先级报告',self.training,ready)
        self.button(actions,'card','生成个人战绩卡',self.card,ready)
        from control_action_menu import ActionMenu,MenuAction
        more=self.button(actions,'more','更多操作 ▾',lambda:self.menu.toggle())
        from control_maintenance import offline_ready
        self.menu=ActionMenu(more,[
            MenuAction('lap-overview','圈速总览与节奏',self.lap_overview,'分析与训练',lambda:ready() and offline_ready(app),visible=lambda:evo),
            MenuAction('lap-pair','圈 A / 圈 B',self.lap_pair,'分析与训练',ready,visible=lambda:supported.selected_laps),
            MenuAction('comparable','同条件进步分析',self.comparable,'分析与训练',ready,visible=lambda:supported.training),
            MenuAction('goals','训练目标跟进',self.goals,'分析与训练',visible=lambda:supported.training),
            MenuAction('note','收藏与标签',lambda:edit_note(app,self.selected,lambda:self.loader.read(True)),'整理纪录',lambda:ready() and not self.loader.running),
            MenuAction('mode','更正参赛方式',self.correct_mode,'整理纪录',lambda:ready() and not self.loader.running),
            MenuAction('folder','打开赛事目录',lambda:self.open(self.selected['folder']),'整理纪录',ready),
            MenuAction('delete-source','删除来源赛事',self.delete_source,'整理纪录',lambda:ready() and not self.loader.running and not self.exporter.busy,danger=True,visible=lambda:evo),
            MenuAction('reopen','打开上次曲线',lambda:self.exporter.open(self),'最近导出',lambda:bool(self.exporter.path) and not self.exporter.busy),
            MenuAction('export-folder','打开导出目录',lambda:self.open(Path(self.exporter.path).parent),'最近导出',lambda:bool(self.exporter.path))
        ],'纪录操作',lambda:self.track_title.cget('text')+' · '+self.time_label.cget('text'))
        from control_list_context import install as context_menu
        context_menu(self.table,self.menu)
        # Retry occupies space only when a detail read actually failed.
        retry=tk.Frame(info,bg=T.CARD);retry.pack(fill='x');self.retry_row=retry
        self.button(retry,'retry','重试详情',lambda:self.details.select(self.selected,True),lambda:ready() and self.state['error'] is not None and not self.state['loading'])
        self.saved=self.variable('saved');self.saved_frame=tk.Frame(info,bg=T.CARD)
        self.report_caption=self.hint(self.saved_frame,'')
        path_entry=tk.Entry(self.saved_frame,textvariable=self.saved,state='readonly',readonlybackground=T.FIELD,fg=T.FG,selectbackground=T.SELECT,selectforeground=T.FG,font=(T.FONT,9),relief='flat')
        path_entry.pack(fill='x',pady=4);path_entry.bind('<Control-a>',lambda _:(path_entry.selection_range(0,'end'),'break')[1])
        self.detail_heading=self.hint(info,'赛道条件',12,T.FG,True)
        self.track_metrics=Metrics(info,[('layout','布局 / 长度'),('track_temp','赛道温度'),('air_temp','气温'),('wetness','路面湿度'),('rain','降雨强度')]);self.track_metrics.pack(fill='x')
        self.hint(info,'车辆与轮胎',12,T.FG,True)
        self.car_metrics=Metrics(info,[('fuel','圈起点油量'),('front','前轮胎种'),('rear','后轮胎种'),('remaining','最低轮胎余量'),('assists','驾驶辅助')]);self.car_metrics.pack(fill='x')
        self.canvas=tk.Canvas(info,bg=T.FIELD,highlightthickness=0,height=250);self.canvas.pack(fill='x',pady=8);self.canvas.bind('<Configure>',self.draw)
        readers=getattr(app,'record_detail_loaders',{});app.record_detail_loaders=readers
        readers.setdefault('best',DetailLoader(app,detail_key)).attach(self,read_detail)
        self.render=self.render_selection;self.refresh_rows=self.populate_best;self.primary=self.curve
        self.exporter.attach(self);self.finish(partial(read_records,app.data_path))

    def hint(self,parent,text,size=9,color=None,bold=False):
        label=self.app.label(parent,text,size,color,bold);label.pack(fill='x',pady=4)
        label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)));return label

    def headers(self):
        for key,title,_ in COLUMNS:self.table.heading(key,text=tr(title))
        self.view_layout.empty()

    def accept(self,values):
        from personal_records import select_records
        baseline,improved=record_improvements(select_records(values),getattr(self.app,'record_best_baseline',None));self.app.record_best_baseline=baseline
        self.entries=values;self.modes.update_options(values);self.populate_best()
        self.badge.configure(text=tr('新纪录')+' · '+display(improved[0]['track']) if improved else '')
        self.say('{count} 条个人赛道纪录',count=len(self.rows));self.app.status.set(str(len(self.rows))+' '+tr('条个人赛道纪录'))

    def populate_best(self,*_):
        if not self.alive():return
        if self.search_field.pending:self.search_field.after_cancel(self.search_field.pending);self.search_field.pending=None
        self.search_field.last=self.query.get()
        from personal_records import select_records
        candidates=select_records([e for _,e in self.modes.pairs(self.entries,self.query.get())]);rows=[]
        for i,e in self.modes.pairs(candidates):
            t=e['time_s'];rows.append((str(i),e,(display(e['track']),f'{int(t//60)}:{t%60:06.3f}',layout(e['track'],e['layout'],e['length_m']),e['vehicle_class'],tr(LABELS[mode(e)]),e['session'].get('vehicle',''))))
        self.populate(rows)
        self.view_layout.empty();self.view_layout.schedule()
        from event_filters import DEFAULTS
        active=sum(value!=DEFAULTS.get(key) for key,value in self.modes.state.items() if key not in ('query','sort'))
        self.buttons['filters'].configure(text=tr('筛选条件')+(f' · {active}' if active else ''),selected=bool(self.modes.winfo_manager()))
        self.say('{count} 条个人赛道纪录',count=len(rows))

    def toggle_filters(self):
        opened=not bool(self.modes.winfo_manager());self.context['filters_open']=opened
        if opened:self.modes.pack(fill='x',pady=8,before=self.table)
        else:self.modes.pack_forget()
        self.buttons['filters'].configure(selected=opened)
        self.modes.sync_chips()
        self.view_layout.schedule()

    def can_step(self,delta):
        chosen=next(iter(self.table.selection()),None)
        return chosen in self.table.order and 0<=self.table.order.index(chosen)+delta<len(self.table.order)

    def neighbor(self,delta):
        if not self.can_step(delta):return
        index=self.table.order.index(self.table.selection()[0])+delta;key=self.table.order[index]
        self.table.selection_set((key,));self.table.cursor=key;self.table.anchor=key
        # Keep the list ready for Return to list without scrolling the detail.
        top=index*self.table.rowheight;bottom=top+self.table.rowheight
        if top<self.table.offset:self.table.set_offset(top)
        elif bottom>self.table.offset+self.table.viewport.winfo_height():self.table.set_offset(bottom-self.table.viewport.winfo_height())

    def render_selection(self):
        e=self.selected;self.state.update(data=None,error=None,loading=False);self.modes.describe(e)
        vehicle=(e['session'].get('vehicle',''),e['track'],e['layout']) if e and getattr(self.app,'simulator','lmu')=='ac_evo' else e['session'].get('vehicle','') if e else ''
        if vehicle!=self.state['vehicle']:self.header.show_vehicle(vehicle);self.state['vehicle']=vehicle
        self.track_metrics.set();self.car_metrics.set()
        if e:
            self.app.record_selected_folder=e['folder'];v=present(e,{})
            participation=tr(LABELS[mode(e)])+(' · '+tr('人工确认') if e['session'].get('race_mode_manual') else '')
            self.track_title.configure(text=v['track']);self.time_label.configure(text=v['time']);self.car_label.configure(text=v['car']);self.date_label.configure(text=v['context']+' · '+participation+' · '+v['session_type'])
        else:
            self.track_title.configure(text=tr('尚无选择'));self.time_label.configure(text='—');self.car_label.configure(text='');self.date_label.configure(text='');self.message.set(tr('先选择一条纪录，再打开曲线或分析。'))
        self.details.select(e);self.draw()

    def detail_waiting(self):
        self.state.update(loading=True,error=None);self.message.set(tr('正在读取纪录详情…'));self.sync()

    def apply_detail(self,data,error):
        self.state.update(data=data if error is None else None,error=error,loading=False)
        if error is not None:self.message.set(tr('详情读取失败，可重试：{error}').format(error=error))
        elif self.selected:
            v=present(self.selected,data);self.track_metrics.set(v['track_metrics']);self.car_metrics.set(v['car_metrics']);self.message.set('')
        self.draw();self.sync()

    def draw(self,_=None):
        if not hasattr(self,'canvas'):return
        canvas=self.canvas;canvas.delete('all');w=max(100,canvas.winfo_width());left=52;right=w-18;data=self.state['data']
        if data is None:
            text='先选择一条纪录查看曲线' if self.selected is None else '详情读取失败，可在上方重试' if self.state['error'] is not None else '正在读取纪录详情…'
            canvas.create_text(w/2,125,text=tr(text),fill=T.MUTED);return
        for i,(name,color) in enumerate(((tr('油门'),T.GREEN),(tr('刹车'),T.RED))):
            top=24+i*105;canvas.create_text(8,top,text=name,fill=color,anchor='w');canvas.create_line(left,top+75,right,top+75,fill=T.EDGE);points=[]
            for index,low,high in data['curve']:
                x=left+index/599*(right-left);points.extend((x,top+75*(1-low[i]),x,top+75*(1-high[i])))
            if len(points)>=4:canvas.create_line(*points,fill=color,width=1.5)
        if not data['curve']:canvas.create_text(w/2,125,text=tr('没有可用的油门 / 刹车采样'),fill=T.MUTED)
        if self.selected:
            for i in range(5):canvas.create_text(left+i/4*(right-left),242,text=f"{self.selected['length_m']*i/4:.0f} m",fill=T.MUTED)

    def refresh_records(self):
        if self.loader.running:return
        if self.state['error'] is not None and self.selected:self.details.select(self.selected,True)
        self.loader.read()

    def refresh_key(self,_=None):
        if self.alive():self.refresh_records();return 'break'

    def lap_pair(self):
        if self.selected is None:return
        from control_lap_pair import show
        show(self.app,self.app.data_path,[Path(self.selected['folder'])])

    def report_update(self):
        self.saved.set(self.exporter.path);self.report_caption.configure(text=tr('最近生成的曲线')+' · '+self.exporter.caption)
        if self.exporter.path:self.saved_frame.pack(fill='x',pady=6,before=self.detail_heading)

    def curve(self):
        if self.selected is None:self.say('先选择一条纪录，再打开曲线或分析。');return
        self.exporter.create(self,self.selected)

    def training(self):
        from control_training import show
        if self.selected:show(self.app,self.selected)
    def card(self):
        from control_achievement import show
        if self.selected:show(self.app,self.selected)
    def comparable(self):
        from control_comparable import show
        if self.selected:show(self.app,self.selected)
    def goals(self):
        from control_training_goals import show
        show(self.app)
    def correct_mode(self):
        if self.selected is None or self.loader.running:return
        from control_race_mode import show
        return show(self.app,self.selected,lambda:self.loader.read(True))

    def delete_source(self):
        if self.selected is None or self.loader.running or self.exporter.busy:return
        from control_delete import remove_source
        snapshot=self.selected.copy();snapshot['session']=dict(self.selected['session'])
        try:remove_source(self.app,snapshot,lambda:self.loader.read(True))
        except (OSError,ValueError) as error:self.say('读取或同步未完成，可重试：{error}',error=str(error))

    def install_actions(self,host):
        host.pack(fill='x',before=self.app.shell.scroll.master,pady=(0,6));row=self.app.row(host);install(row);self.fixed={}
        from simulator_profiles import capabilities
        supported=capabilities(getattr(self.app,'simulator','lmu'))
        for key,title,command in [('curve','打开完整圈曲线',self.curve),('training','训练优先级报告',self.training),('card','生成个人战绩卡',self.card),('mode','更正参赛方式',self.correct_mode),('details','纪录详情',self.view_layout.details)]:
            if key=='training' and not supported.training:continue
            b=self.app.button(row,title,command,key=='curve',100 if key=='details' else 140);b.configure(height=px(b,38));self.fixed[key]=b
        self.sync()

    def sync(self):
        super().sync()
        if not self.alive():return
        selected=next(iter(self.table.selection()),None);index=self.table.order.index(selected)+1 if selected in self.table.order else 0
        self.position.set(tr('第 {index} / {count} 条').format(index=index,count=len(self.table.order)))
        retry=self.buttons['retry']
        if retry.enabled and not retry.winfo_manager():retry.pack(side='left')
        elif not retry.enabled:retry.pack_forget()
        for key,b in self.fixed.items():
            if b.winfo_exists():b.configure(state='normal' if self.selected is not None and (key!='curve' or not self.exporter.busy) and (key!='mode' or not self.loader.running) else 'disabled')

    def translate(self):
        super().translate()
        for b in self.fixed.values():
            if b.winfo_exists():b.configure(width=max(px(b,140),b.font.measure(tr(b.label))+px(b,36)));b.paint()
