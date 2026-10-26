"""Official career records with persistent browsing and serialized read-only imports."""
from functools import partial
from pathlib import Path
from i18n import tr
from control_theme import T
from control_fields import Field
from control_list import SessionList
from control_metrics import Metrics
from control_record_browser import RecordPage
from track_names import display,layout
from official_results import load,refresh
from race_mode import mode,LABELS
from control_mode_filters import ModeControls
from control_event_filters import edit_note
from event_catalog import attach
from control_history_chart import lap_time

COLUMNS=(('date','时间 (UTC)',180),('phase','阶段',75),('mode','参赛方式',85),('track','赛道 / 布局',180),('car','车辆',215),('finish','完赛 / 同组',155),('best','最快圈',110),('link','关联',120))
LINKS=dict(matched='已关联',unmatched='无关联遥测',ambiguous='待确认',conflict='成绩冲突')


def place(total,group):
    return ('P'+str(total) if total else '—')+' / '+tr('同组')+' '+('P'+str(group) if group else tr('未知'))


def read_results(root):
    result=load(root);return dict(result,entries=attach(root,result['entries']))


def sync_results(root,source,driver):
    result=refresh(root,source,driver);return dict(result,entries=attach(root,result['entries']))


def show(app):return OfficialPage(app)


class OfficialPage(RecordPage):
    def __init__(self,app):
        body=app.card('官方战绩','只读导入游戏结果 XML；没有遥测的赛事只展示成绩与官方圈计时');super().__init__(app,'official',body)
        row=app.row(body);self.search(row)
        tools=self.row(body);idle=lambda:not self.loader.running
        self.button(tools,'sync','同步游戏成绩',self.sync_game,idle,True);self.button(tools,'folder','导入结果文件夹',self.folder,idle);self.button(tools,'refresh','刷新已导入成绩',self.loader.read,idle)
        driver_row=self.row(body);app.label(driver_row,'多人赛事车手姓名',9).pack(side='left')
        from race_model import read_json
        saved=read_json(app.data_path/'OfficialResults/preferences.json',{});saved=saved if isinstance(saved,dict) else {}
        self.driver=self.variable('driver',self.context.get('driver',saved.get('player_name','')));self.driver.trace_add('write',lambda *_:self.context.update(driver=self.driver.get()))
        self.driver_field=Field(driver_row,textvariable=self.driver,width=25);self.driver_field.pack(side='left')
        self.hint(body,'姓名在同步时应用；留空沿用已有设置或本地记录中的车手姓名。')
        self.modes=ModeControls(body,app,self.populate_results,'official_mode_filters');self.modes.bind_query(self.query)
        self.entries={};self.table=SessionList(body,columns=tuple(k for k,_,_ in COLUMNS),height=7)
        for key,_,width in COLUMNS:self.table.column(key,width=width*self.table.s,minwidth=70*self.table.s,stretch=key in ('track','car'))
        from control_table_preferences import install
        install(app,self.table,'official',self.modes);self.table.pack(fill='x',pady=8)
        info=app.card('官方成绩详情','成绩来自游戏 XML；燃油、油刹曲线和赛道条件只在存在关联遥测时可查看')
        self.link_note=self.hint(info,'双击记录或按 Enter：优先打开关联复盘，否则查看原 XML。')
        actions=self.row(info);self.button(actions,'review','打开关联复盘',self.open_review,lambda:bool(self.review_path()),True);self.button(actions,'xml','查看原始 XML',self.open_xml,lambda:bool(self.xml_path()));self.button(actions,'note','收藏与标签',lambda:edit_note(app,self.selected,lambda:self.loader.read(True)),lambda:self.selected is not None and not self.loader.running)
        self.metrics=Metrics(info,[('driver','车手姓名'),('mode','参赛方式'),('date','比赛时间 (UTC)'),('track','赛道'),('layout','赛道布局 / 长度'),('phase','阶段'),('vehicle','使用车型'),('team','车型所在车队'),('class','车辆类别'),('grid','发车 / 同组'),('finish','完赛 / 同组'),('best','个人最快圈'),('finish_time','官方 FinishTime / 秒'),('laps','完成圈数'),('status','完赛状态'),('source','数据来源')]);self.metrics.pack(fill='x',pady=8)
        self.hint(info,'官方圈计时：XML 未提供完整有效圈验证，不计入遥测圈速纪录。')
        self.lap_table=SessionList(info,columns=('lap','time','s1','s2','s3'),height=5);self.lap_table.pack(fill='x',pady=6)
        for key in ('lap','time','s1','s2','s3'):self.lap_table.column(key,width=140*self.lap_table.s,minwidth=60*self.lap_table.s,stretch=True)
        self.detail_text=self.variable('detail');label=app.label(info,self.detail_text,10);label.pack(fill='x',pady=8);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
        app.label(info,'成绩冲突对照（只展示，不自动覆盖）',12,T.FG,True).pack(anchor='w',pady=8)
        self.conflicts=SessionList(info,columns=('field','telemetry','official','decision'),height=3);self.conflicts.pack(fill='x',pady=5)
        for key in ('field','telemetry','official','decision'):self.conflicts.column(key,width=190*self.conflicts.s,minwidth=90*self.conflicts.s,stretch=True)
        self.query.trace_add('write',self.populate_results);self.render=self.render_selection;self.refresh_rows=self.populate_results;self.primary=lambda:self.open_review() if self.review_path() else self.open_xml();self.finish(partial(read_results,app.data_path))
    def hint(self,parent,text):
        label=self.app.label(parent,text,9);label.pack(fill='x',pady=5);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)));return label
    def headers(self):
        for key,title,width in COLUMNS:self.table.heading(key,text=tr(title))
        for key,title in (('lap','圈'),('time','圈速'),('s1','S1 / s'),('s2','S2 / s'),('s3','S3 / s')):self.lap_table.heading(key,text=tr(title))
        for key,title in (('field','冲突字段'),('telemetry','遥测观测值'),('official','官方 XML 值'),('decision','处理建议')):self.conflicts.heading(key,text=tr(title))
        self.table.set_empty('没有匹配的官方成绩；可清除搜索、重置筛选或同步结果。')
    def accept(self,result):
        self.entries={e['id']:e for e in result['entries']};self.modes.update_options(list(self.entries.values()));self.populate_results();self.say('官方赛事 {count} · 未读取记录 {errors} · 冲突记录 {conflicts}',count=len(self.entries),errors=len(result['errors']),conflicts=len(result['conflicts']))
    def populate_results(self,*_):
        if not self.alive():return
        self.modes.describe();rows=[]
        for _,e in self.modes.pairs(list(self.entries.values()),self.query.get()):
            rows.append((e['id'],e,(e['started_utc'][:19].replace('T',' '),tr(e['phase']),tr(LABELS[mode(e)]),display(e['layout']),e['vehicle'],place(e['finish_place'],e['finish_class_place']),lap_time(e['best_lap_s']) if e['best_lap_s'] else '—',tr(LINKS.get(e.get('link_status'),'无关联遥测')))))
        self.populate(rows)
    def render_selection(self):
        e=self.selected;self.modes.describe(e)
        if not e:self.metrics.set();self.detail_text.set('');self.lap_table.replace([],());self.conflicts.replace([],());return
        self.metrics.set(dict(driver=e['driver'],mode=tr(LABELS[mode(e)]),date=e['started_utc'][:19].replace('T',' ')+' UTC',track=display(e['track']),layout=layout(e['track'],e['layout'],e['length_m']),phase=tr(e['phase']),vehicle=e['vehicle'],team=e['team'] or tr('未知'),**{'class':e['vehicle_class'] or tr('未知')},grid=place(e['grid_place'],e['grid_class_place']),finish=place(e['finish_place'],e['finish_class_place']),best=lap_time(e['best_lap_s']) if e['best_lap_s'] else tr('未知'),finish_time=f"{e['finish_time_s']:.3f}" if e['finish_time_s'] else tr('未知'),laps=str(e['completed_laps']) if e['completed_laps'] is not None else tr('未知'),status=e['finish_status'] or tr('未知'),source='LMU result XML'))
        self.lap_table.replace([(str(i),(l['number'],lap_time(l['time_s']),*[f'{v:.3f}' if v is not None else '—' for v in l['sectors']])) for i,l in enumerate(e['laps'])],())
        from result_conflicts import rows,provenance
        self.conflicts.replace(rows(e),());self.detail_text.set(tr('FinishTime 为官方完赛计时，起跑基准未确认，不能直接当作比赛用时。')+'\n'+tr(LINKS.get(e.get('link_status'),'无关联遥测'))+'\n'+provenance(e)+'\n'+(tr('原 XML 已移动；已导入成绩仍保留') if not self.xml_path() else '')+'\n'+(tr('没有可打开的关联遥测复盘；不会补造曲线') if not self.review_path() else ''))
    def xml_path(self):
        path=Path(self.selected['source_xml']) if self.selected else None;return path if path and path.is_file() else None
    def review_path(self):
        e=self.selected;folder=Path(e['linked_folder']) if e and e.get('linked_folder') and e.get('link_status')=='matched' else None;path=folder/'review.html' if folder else None;return path if path and path.is_file() else None
    def open_xml(self):
        path=self.xml_path()
        if path:self.open(path)
        else:self.say('原 XML 已移动；已导入成绩仍保留')
    def open_review(self):
        path=self.review_path()
        if path:self.open(path)
        else:self.say('没有可打开的关联遥测复盘；不会补造曲线')
    def sync(self):
        super().sync();self.driver_field.entry.configure(state='disabled' if self.loader.writing else 'normal')
    def sync_game(self):
        if self.loader.running:return
        from paths import discover_game
        game=discover_game()
        if game:self.sync_folder(game/'UserData/Log/Results')
        else:self.say('未找到 LMU 安装目录，请选择结果 XML 文件夹');self.folder()
    def folder(self):
        if self.loader.running:return
        from tkinter import filedialog
        path=filedialog.askdirectory(parent=self.app.root,title=tr('选择结果 XML 文件夹'))
        if path:self.sync_folder(path)
    def sync_folder(self,path):
        self.loader.start(partial(sync_results,self.app.data_path,Path(path),self.driver.get().strip() or None),'正在读取官方赛事结果…',True)
