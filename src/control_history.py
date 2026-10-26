"""PB history with persistent selection, direct opening and reusable curve exports."""
import tkinter as tk
from functools import partial
from pathlib import Path
from i18n import tr
from control_theme import T
from control_list import SessionList
from control_record_browser import RecordPage,CurveExport
from track_names import display,layout
from record_history import history
from history_view import series
from control_history_chart import ProgressChart,lap_time
from control_feedback import CountBadge
from race_mode import mode,LABELS
from control_event_filters import edit_note
from event_catalog import attach

COLUMNS=(('date','时间 (UTC)',180),('track','赛道',155),('layout','布局 / 长度',170),('class','组别',80),('mode','参赛方式',90),('car','车辆',225),('lap','圈',55),('time','最快圈',110),('gain','提升',120))


def read_history(root):
    value=history(root,per_vehicle=True);return dict(value,entries=attach(root,value['entries']))


def show(app):return HistoryPage(app)


class HistoryPage(RecordPage):
    def __init__(self,app):
        body=app.card('纪录履历','同赛道布局、同车型分别统计刷新过程；默认最新记录优先');super().__init__(app,'history',body)
        self.identity=lambda e:(str(e['folder']),e['lap']['number']);self.entries=[];row=app.row(body);self.search(row)
        tools=self.row(body);self.button(tools,'refresh','刷新记录',self.loader.read,lambda:not self.loader.running,True);self.button(tools,'note','收藏与标签',lambda:edit_note(app,self.selected,lambda:self.loader.read(True)),lambda:self.selected is not None and not self.loader.running)
        self.hint(body,'双击记录或按 Enter 打开完整圈曲线；刷新保留选择与滚动位置。')
        from control_mode_filters import ModeControls
        self.modes=ModeControls(body,app,self.populate_history,'history_event_filters');self.modes.bind_query(self.query);self.count=CountBadge(body);self.count.pack(fill='x',pady=4)
        self.table=SessionList(body,columns=tuple(k for k,_,_ in COLUMNS),height=5)
        for key,_,width in COLUMNS:self.table.column(key,width=width*self.table.s,minwidth=(80 if key=='class' else 45)*self.table.s,stretch=key in ('track','layout','car'))
        from control_table_preferences import install
        install(app,self.table,'history',self.modes);self.table.pack(fill='x',pady=8)
        chart_body=app.card('成绩提升曲线','按时间展示同布局、同车型的纪录；圈速越低越快，点击数据点可定位赛事')
        self.chosen=self.variable('chosen');self.hint(chart_body,self.chosen,11,T.FG);self.summary=self.variable('summary');self.hint(chart_body,self.summary,10,T.ACCENT)
        self.chart=ProgressChart(chart_body,self.select_point);self.chart.pack(fill='x',pady=8)
        self.exporter=getattr(app,'history_curve_export',None) or CurveExport(app);app.history_curve_export=self.exporter
        actions=self.row(chart_body);actions.pack_configure(before=self.chart);self.button(actions,'curve','打开完整圈曲线',self.curve,lambda:self.selected is not None and not self.exporter.busy,True)
        self.button(actions,'folder','打开赛事目录',lambda:self.open(self.selected['folder']),lambda:self.selected is not None)
        self.button(actions,'card','生成个人战绩卡',self.card,lambda:self.selected is not None);self.button(actions,'comparable','同条件进步分析',self.comparable,lambda:self.selected is not None)
        self.button(actions,'reopen','打开上次曲线',lambda:self.exporter.open(self),lambda:bool(self.exporter.path) and not self.exporter.busy);self.button(actions,'export-folder','打开导出目录',lambda:self.open(Path(self.exporter.path).parent),lambda:bool(self.exporter.path) and not self.exporter.busy)
        self.saved=self.variable('saved');self.saved_frame=tk.Frame(chart_body,bg=T.CARD);self.report_caption=app.label(self.saved_frame,'',9,T.MUTED);self.report_caption.pack(fill='x',pady=4);self.report_caption.bind('<Configure>',lambda e:self.report_caption.configure(wraplength=max(100,e.width)))
        entry=tk.Entry(self.saved_frame,textvariable=self.saved,state='readonly',readonlybackground=T.FIELD,bg=T.FIELD,fg=T.FG,selectbackground=T.SELECT,selectforeground=T.FG,font=(T.FONT,9),relief='flat');entry.pack(fill='x',pady=4);entry.bind('<Control-a>',lambda _:(entry.selection_range(0,'end'),'break')[1])
        self.query.trace_add('write',self.populate_history);self.render=self.render_selection;self.refresh_rows=self.populate_history;self.primary=self.curve;self.exporter.attach(self);self.finish(partial(read_history,app.data_path))
    def hint(self,parent,text,size=9,color=None):
        label=self.app.label(parent,text,size,color);label.pack(fill='x',pady=5);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)));return label
    def headers(self):
        for key,title,width in COLUMNS:self.table.heading(key,text=tr(title))
        self.table.set_empty('没有匹配的纪录；可清除搜索或重置筛选。')
    def accept(self,value):
        self.entries=value['entries'];self.modes.update_options(self.entries);self.populate_history();self.say('纪录刷新 {count} · 缺失日期排除 {missing} · 冲突记录 {conflicts}',count=len(self.entries),missing=value['missing_dates'],conflicts=value['conflicts'])
    def populate_history(self,*_):
        if not self.alive():return
        rows=[]
        for i,e in self.modes.pairs(self.entries,self.query.get()):
            gain=e['improvement_s'];rows.append((str(i),e,(e['observed_utc'][:19].replace('T',' '),display(e['track']),layout(e['track'],e['layout'],e['length_m']),e['vehicle_class'],tr(LABELS[mode(e)]),e['session'].get('vehicle',''),e['lap']['number'],lap_time(e['time_s']),tr('首次记录') if gain is None else f'-{gain:.3f} s')))
        self.count.set(len(rows));self.populate(rows)
    def render_selection(self):
        e=self.selected;self.modes.describe(e)
        if not e:self.chosen.set('');self.summary.set('');self.chart.set([]);return
        self.chosen.set(display(e['track'])+' · '+layout(e['track'],e['layout'],e['length_m'])+' · '+e['vehicle_class']+' · '+e['session'].get('vehicle',''))
        values=series([v for _,v in self.modes.pairs(self.entries,self.query.get())],e);self.chart.set(values)
        if not values:self.summary.set('');return
        gain=values[0]['time_s']-values[-1]['time_s'];self.summary.set(tr('累计提升')+f' {gain:.3f} s  /  '+tr('当前纪录')+' '+lap_time(values[-1]['time_s'])+'  /  '+str(len(values))+' '+tr('次纪录刷新')+(' · '+tr('仅一条纪录，等待下一次突破') if len(values)==1 else ''))
    def select_point(self,entry):
        key=next((key for key,e,_ in self.rows if e is entry),None)
        if key is not None:self.table.selection_set((key,));self.table.yview('moveto',max(0,self.table.order.index(key)-1)/max(1,len(self.table.order)))
    def report_update(self):
        self.saved.set(self.exporter.path);self.report_caption.configure(text=tr('最近生成的曲线')+' · '+self.exporter.caption)
        if self.exporter.path:self.saved_frame.pack(fill='x',pady=6)
    def curve(self):self.exporter.create(self,self.selected)
    def card(self):
        from control_achievement import show
        show(self.app,self.selected)
    def comparable(self):
        from control_comparable import show
        show(self.app,self.selected)
