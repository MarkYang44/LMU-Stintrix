"""Full-record operations retain their original backends and GUI-thread snapshots."""
import os,tkinter as tk
from pathlib import Path
from tkinter import filedialog
from control_theme import T
from control_fields import Select
from control_widgets import Switch
from control_flow import install
from control_action_menu import ActionMenu,MenuAction
from control_immediate_save import ImmediateSave
from i18n import tr


class Actions:
    def __init__(self,view,render_review,make_report):
        self.v=view;self.app=view.app;self.owner=view.owner;self.root=view.root_path;self.render_review=render_review;self.make_report=make_report
        self.capabilities=view.capabilities
        self.kind=tk.StringVar(view.window,value=self.reference_owner().reference_kind.get() if self.capabilities.reference_laps else 'fastest')
        import archive_preferences
        preferences=archive_preferences.load(self.root);self.format=tk.StringVar(view.window,value='ZIP' if preferences['format']=='zip' else '7z');self.verify=tk.BooleanVar(view.window,value=False)
        self.options=tk.Frame(view.table.master,bg=T.CARD);row=self.app.row(self.options);install(row)
        self.app.label(row,'导出格式',9,T.MUTED).pack(side='left');box=Select(row,textvariable=self.format,values=['ZIP','7z'],width=8);box.pack(side='left')
        if self.capabilities.reference_laps:
            self.app.label(row,'对比与参考圈',9,T.MUTED).pack(side='left');Select(row,textvariable=self.kind,values=['fastest','stable'],labels=dict(fastest='最快圈',stable='稳定圈'),width=12).pack(side='left')
        Switch(self.options,'导入时完整校验',self.verify,lambda:None,compact=True).pack(fill='x')
        path=self.root
        def persist(changes,draft):archive_preferences.save(path,draft['format'].lower(),False);return dict(format='ZIP' if archive_preferences.load(path)['format']=='zip' else '7z')
        self.preference=ImmediateSave(self.app,self.options,dict(format=self.format),persist,'library-archive');box.bind('<<ComboboxSelected>>',lambda _:self.preference.submit())
        from control_batch import running,jobs,show
        from control_maintenance import offline_ready
        from control_evo_compare import last_multi,open_multi
        idle=lambda:not view.working and not view.loading and running(self.app) is None;single=lambda:idle() and len(view.selected_items())==1
        view.action('open','打开赛事复盘',self.open_review,155,True,lambda:single() and (Path(self.one()['folder'])/'review.html').is_file())
        view.action('laps','圈速单',lambda:self.image('圈速单.png'),105,enabled=single);view.action('journal','比赛日志',lambda:self.image('比赛日志.png'),110,enabled=single)
        view.action('note','收藏与标签',self.note,145,enabled=single)
        from control_participation import eligible
        view.action('mode','更正参赛方式',self.correct_mode,150,enabled=lambda:idle() and bool(view.selected_items()) and all(eligible(self.app,e) for e in view.selected_items()))
        trigger=view.action('more','更多操作 ▾',lambda:self.menu.toggle(),135)
        self.menu=ActionMenu(trigger,[
            MenuAction('copy-cell','复制此单元格',view.table.copy_cell,'复制',lambda:bool(view.selected_items()),'Ctrl+Shift+C；复制当前单元格的完整文字'),
            MenuAction('copy-rows','复制选中行',view.table.copy_rows,'复制',lambda:bool(view.selected_items()),'Ctrl+C；复制显示列，可粘贴到表格'),
            MenuAction('cell-details','单元格详情',lambda:self.cell_details(),'查看与对比',lambda:bool(view.selected_items()),'左右键选择列，F2 查看完整文字'),
            MenuAction('folder','打开赛事目录',self.open_directory,'查看与对比',single),
            MenuAction('compare','多选对比' if self.capabilities.reference_laps else '圈 A / 圈 B',self.compare,'查看与对比',lambda:idle() and 1<=len(view.selected_items())<=(6 if self.capabilities.reference_laps else 2),'选择 1–6 场记录，使用已有最快圈或稳定圈' if self.capabilities.reference_laps else '选择 1–2 场赛事，再选择已验证的完整有效圈'),
            MenuAction('compare-best','跨场最快圈对比',self.fastest_compare,'查看与对比',lambda:idle() and offline_ready(self.app) and 2<=len(view.selected_items())<=6 and all(item.get('fastest_file') for item in view.selected_items()),'选择 2–6 场同布局赛事，直接比较各场最快有效圈',visible=lambda:not self.capabilities.reference_laps),
            MenuAction('same','同场圈 A／B',self.same,'查看与对比',single),
            MenuAction('lap-overview','圈速总览与节奏',self.lap_overview,'查看与对比',lambda:single() and offline_ready(self.app),visible=lambda:not self.capabilities.full_review),
            MenuAction('fastest','最快圈页',lambda:self.open_file('fastest_lap.html'),'查看与对比',lambda:single() and (Path(self.one()['folder'])/'fastest_lap.html').is_file()),
            MenuAction('reference','设为锁定参考',self.reference,'查看与对比',lambda:single() and bool(self.one().get('stable_file' if self.kind.get()=='stable' else 'fastest_file')),visible=lambda:self.capabilities.reference_laps),
            MenuAction('multi-reopen','打开上次多圈对比',lambda:open_multi(self.app),'最近对比',lambda:last_multi(self.app) is not None,'打开已生成的文件，保留当前选择与 A/B 记忆',visible=lambda:not self.capabilities.reference_laps),
            MenuAction('analyze','分析 / 完整复盘',self.analyze,'整理与管理',single,visible=lambda:self.capabilities.full_review),
            MenuAction('reports','报告任务与分步重试',self.reports,'整理与管理',lambda:bool(view.selected_items())),
            MenuAction('images','重新生成报告图片',self.regenerate,'整理与管理',single),
            MenuAction('fastest-csv','导出最快圈 CSV（可多选）',self.fastest_csv,'整理与管理',lambda:idle() and bool(view.selected_items()) and offline_ready(self.app),visible=lambda:not self.capabilities.full_review),
            MenuAction('export','导出比赛包（可多选）',self.export,'整理与管理',lambda:idle() and bool(view.selected_items())),
            MenuAction('import','导入比赛包（可多选）',self.import_packages,'整理与管理',idle),
            MenuAction('compress','压缩备份',self.compress,'整理与管理',single),
            MenuAction('recover','恢复中断记录',self.recover,'整理与管理',lambda:single() and self.one()['status']!='recording',visible=lambda:self.capabilities.full_review),
            MenuAction('options','导出与参考选项' if self.capabilities.reference_laps else '归档选项',self.toggle_options,'列表与选项'),
            MenuAction('progress','查看批量任务',lambda:show(self.app),'列表与选项',lambda:bool(jobs(self.app))),
            MenuAction('all','全选当前列表',lambda:view.table.selection_set(view.table.get_children()),'列表与选项'),
            MenuAction('clear','清除选择',lambda:view.table.selection_set(()),'列表与选项'),
            MenuAction('refresh','刷新',view.refresh,'列表与选项')],'记录管理操作',lambda:view.count.get())
        from control_list_context import install as context_actions
        context_actions(view.table,self.menu,view.selected)
    def one(self):return self.v.selected_items()[0]
    def cell_details(self):
        from control_cell_details import show
        return show(self.v.table)
    def open_directory(self):
        if len(self.v.selected_items())!=1 or self.v.working:return
        folder=Path(self.one()['folder']).resolve()
        try:
            if not folder.is_relative_to(self.root) or not folder.is_dir():raise ValueError('文件或目录已移动或删除')
            os.startfile(str(folder))
        except (OSError,ValueError) as error:self.v.say(tr('打开失败：{error}').format(error=tr(str(error)) or type(error).__name__))
    def reference_owner(self):
        hud=getattr(self.owner,'hud',None)
        return hud if hud is not None and not hud.closing and hud.root.winfo_exists() else self.owner
    def sync(self):
        busy=self.v.working or self.v.loading
        for widget in self.options.winfo_children():
            if isinstance(widget,Switch):widget.configure(state='disabled' if busy else 'normal')
    def translate(self):
        self.menu.close(False)
        for row in [self.options,*[c for c in self.options.winfo_children() if isinstance(c,tk.Frame)]]:
            row.event_generate('<Configure>',width=row.winfo_width())
    def toggle_options(self):self.options.pack_forget() if self.options.winfo_manager() else self.options.pack(fill='x',before=self.v.table)
    def open_file(self,name):
        if len(self.v.selected_items())!=1 or self.v.working:return
        folder=Path(self.one()['folder']).resolve();path=folder/name
        try:
            if not folder.is_relative_to(self.root) or not path.resolve().is_relative_to(folder) or not path.is_file():raise ValueError('结果文件不存在或已移动')
            os.startfile(str(path))
        except (OSError,ValueError) as error:self.v.say(tr(str(error)) or type(error).__name__)
    def open_review(self):return self.open_file('review.html')
    def image(self,name):
        if len(self.v.selected_items())!=1 or self.v.working:return
        from control_report_images import show
        return show(self.app,self.one()['folder'],name)
    def regenerate(self):
        from control_report_images import generate
        if len(self.v.selected_items())==1:generate(self.app,self.one()['folder'],True)
    def reports(self):
        from control_maintenance import reports
        return reports(self.app,[item['folder'] for item in self.v.selected_items()])
    def lap_overview(self):
        if self.capabilities.full_review or len(self.v.selected_items())!=1:return
        from control_evo_lap_overview import show
        return show(self.app,self.one()['folder'])
    def fastest_csv(self):
        if self.capabilities.full_review:return
        from control_evo_exports import fastest_csv
        return fastest_csv(self.app,[dict(item) for item in self.v.selected_items()])
    def note(self):
        if len(self.v.selected_items())!=1 or self.v.working:return
        from control_notes import show
        return show(self.app,self.one(),self.updated)
    def correct_mode(self):
        from control_participation import edit
        return edit(self.app,[dict(e) for e in self.v.selected_items()],self.updated)
    def updated(self):
        if self.v.alive():self.v.refresh()
        refresh=getattr(self.owner,'refresh',None)
        if refresh and not self.owner.closing:refresh()
    def same(self):
        if not self.capabilities.reference_laps:
            from control_lap_pair import show
            if len(self.v.selected_items())==1:return show(self.app,self.root,[self.one()['folder']])
            return
        from management import show_lap_selection
        if len(self.v.selected_items())==1:return show_lap_selection(self.app,self.root,self.one()['folder'])
    def background(self,work,done):
        if self.v.working:return
        self.v.working=True;self.v.say('后台处理中…');self.v.sync()
        def finished(value,error):
            self.v.working=False
            if not self.v.alive():return
            if error is not None:self.v.say(str(error))
            else:
                try:done(value)
                except (OSError,ValueError) as issue:self.v.say(tr('文件已生成，打开失败：')+(str(issue) or type(issue).__name__))
            self.v.sync()
            if self.v.pending_refresh:self.v.pending_refresh=False;self.v.refresh()
        self.owner.run_background(work,finished)
    def compare(self):
        values=[dict(item) for item in self.v.selected_items()];kind=self.kind.get();root=self.root
        if not self.capabilities.reference_laps:
            from control_lap_pair import show
            if 1<=len(values)<=2:return show(self.app,root,[item['folder'] for item in values])
            return
        if not 1<=len(values)<=6:return
        def work():
            from json_store import load
            from laps import write_compare
            from paths import ASSETS
            records=[]
            for item in values:
                file=item['stable_file'] if kind=='stable' else item['fastest_file']
                if not file:raise ValueError(item['track']+' 没有所选类型的参考圈')
                records.append(load(Path(item['folder'])/file))
            path=root/'LibraryCompare.html';write_compare(path,ASSETS/'compare.html',records);return path
        self.background(work,lambda path:os.startfile(str(path)))
    def fastest_compare(self):
        if self.capabilities.reference_laps or self.v.working or not self.v.alive():return
        from control_evo_compare import fastest
        def notify(message):
            if self.v.alive():self.v.say(message)
            else:self.app.status.set(message)
        def finished():
            self.v.working=False
            if self.v.alive():
                self.v.sync()
                if self.v.pending_refresh:self.v.pending_refresh=False;self.v.refresh()
        if fastest(self.app,self.v.selected_items(),notify=notify,finished=finished):self.v.working=True;self.v.sync()
    def reference(self):
        if not self.capabilities.reference_laps:return
        item=dict(self.one());kind=self.kind.get();target=self.reference_owner()
        def work():
            from reference import ReferenceLap
            file=item['stable_file'] if kind=='stable' else item['fastest_file']
            if not file:raise ValueError('没有所选类型的参考圈；稳定圈需先分析且至少有三圈')
            return ReferenceLap.load(Path(item['folder'])/file)
        def done(ref):
            from reference import DistanceAligner
            owner=target
            if owner.closing or not owner.root.winfo_exists():self.v.say('参考目标已关闭，请重新选择参考圈');return
            with owner.engine.lock:owner.engine.reference=ref;owner.engine.aligner=DistanceAligner()
            owner.reference_kind.set(kind);owner.reference_settings['path']=ref.path;owner.reference_locked.set(True);owner.reference_on.set(True);owner.reference_auto.set(False);owner.apply_reference();self.v.say(tr('已锁定第 ')+str(ref.info['number'])+tr(' 圈为 HUD 参考'))
        self.background(work,done)
    def analyze(self):
        if not self.capabilities.full_review:return
        folder=Path(self.one()['folder']);render=self.render_review
        def work():
            from sessionlab import analyze_session
            analyze_session(folder);render(folder);return folder/'review.html'
        self.background(work,lambda path:(os.startfile(str(path)),self.updated()))
    def compress(self):
        from storage import compress_session
        folder=self.one()['folder'];self.background(lambda:compress_session(folder),lambda value:self.v.say(tr('已校验压缩备份：')+f"{value['compressed_bytes']/1048576:.2f}"+tr(' MB；保留原 CSV')))
    def recover(self):
        if not self.capabilities.full_review:return
        from storage import recover_session
        folder=self.one()['folder'];root=self.root;report=self.make_report
        def work():result=recover_session(folder,root);report(result);return result
        self.background(work,lambda _:self.updated())
    def export(self):
        from control_batch import start
        from session_archive import export_session
        values=[item['key'] for item in self.v.selected_items()]
        if not values:return
        destination=filedialog.askdirectory(parent=self.v.window,title=tr('选择赛事包导出目录'))
        if not destination:return
        root=self.root;format=self.format.get().lower();start(self.app,'赛事包导出任务',values,lambda key:export_session(root,key,destination,format=format),destination=destination,on_done=lambda _:self.updated());self.v.sync()
    def import_packages(self):
        from control_batch import start
        from session_archive import import_session
        paths=filedialog.askopenfilenames(parent=self.v.window,title=tr('导入赛事包'),filetypes=[('Stintrix ZIP / 7z','*.zip *.7z')])
        if not paths:return
        root=self.root;verify=self.verify.get();start(self.app,'赛事包导入任务',paths,lambda path:import_session(root,path,verify=verify),on_done=lambda _:self.updated());self.v.sync()
    def dispose(self):
        self.menu.close(False)
        for variable in (self.kind,self.format,self.verify):variable.__del__();variable._tk=None
