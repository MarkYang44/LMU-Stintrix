"""Control-center transfers reuse existing lossless operations with item-level feedback."""
from pathlib import Path
from tkinter import filedialog
from i18n import tr
from control_batch import start


def available(app):
    from control_batch import running
    job=running(app)
    if job and job.busy:
        from control_batch import show
        app.batch_job=job;show(app);app.status.set(tr('请等待当前批量任务结束'));return False
    return True


def storage_operation(self,kind):
    if self.active():self.status.set(tr('请先停止 HUD，再整理或导出存储'));return
    if not available(self):return
    from storage_actions import columnar,export,restore
    def action(items):
        destination=filedialog.askdirectory(parent=self.root,title=tr('选择导出目录')) if kind in ('csv','html') else None
        if kind in ('csv','html') and not destination:return
        start(self,'存储处理任务',[item['folder'] for item in items],lambda folder:columnar(folder) if kind=='columnar' else restore(folder) if kind=='restore' else export(folder,destination,kind),destination=destination)
    self.with_selection(action,None)


def compress_selected(self):
    if not available(self):return
    from session_compression import compress
    self.with_selection(lambda items:start(self,'无损压缩任务',[item['folder'] for item in items],compress),None)


def export_package(self):
    if not available(self):return
    from session_archive import export_session
    def action(items):
        directory=filedialog.askdirectory(parent=self.root,title=tr('选择赛事包导出目录'))
        if not directory:return
        import archive_preferences
        format=archive_preferences.load(self.data_path)['format']
        start(self,'赛事包导出任务',[item['key'] for item in items],lambda key:export_session(self.data_path,key,Path(directory),format=format),destination=directory)
    self.with_selection(action,None)


def import_package(self):
    if not available(self):return
    from session_archive import import_session
    from archive_preferences import load
    paths=filedialog.askopenfilenames(parent=self.root,title=tr('导入赛事包'),filetypes=[('Stintrix ZIP / 7z','*.zip *.7z')])
    if paths:
        verify=load(self.data_path)['verify']
        start(self,'赛事包导入任务',paths,lambda path:import_session(self.data_path,path,verify=verify),on_done=lambda _:self.refresh())


def import_native(self):
    if not available(self):return
    from telemetry_import import import_recording
    from session_reports import make_report
    paths=filedialog.askopenfilenames(parent=self.root,title=tr('导入 LMU 官方遥测（只读）'),filetypes=[('LMU 遥测','*.duckdb')])
    if not paths:return
    root=self.data_path;imported={}
    from report_state import LABELS
    labels={key:tr(value) for key,value in LABELS.items()}
    incomplete=tr('报告尚未完成，可重试')
    def operation(path):
        source=Path(path);stat=source.stat();stamp=(stat.st_size,stat.st_mtime_ns);previous=imported.get(str(source))
        if previous and previous[0]==stamp and Path(previous[1]).exists():folder=previous[1]
        else:folder=import_recording(path,root);imported[str(source)]=(stamp,folder)
        try:receipt=make_report(folder)
        except Exception as error:return dict(path=str(folder),errors=[str(error) or type(error).__name__])
        errors=[]
        if isinstance(receipt,dict):
            for name,step in receipt.get('steps',{}).items():
                if step.get('state')!='ready':errors.append(labels.get(name,name)+': '+str(step.get('error') or step.get('state','incomplete')))
            if receipt.get('state') not in (None,'ready') and not errors:errors.append(str(receipt.get('reason') or incomplete))
        return dict(path=str(folder),errors=errors)
    start(self,'官方遥测导入任务',list(dict.fromkeys(paths)),operation,on_done=lambda _:self.refresh(),result_actions=True)
