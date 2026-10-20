"""Control-center storage/import/export actions; recording formats stay unchanged."""
import os
from pathlib import Path
from tkinter import filedialog,messagebox
from i18n import tr


def storage_operation(self,kind):
    if self.active():self.status.set(tr('请先停止 HUD，再整理或导出存储'));return
    from session_archive import transfer_batch
    from storage_actions import columnar,export,restore
    def action(items):
        destination=filedialog.askdirectory(parent=self.root,title=tr('选择导出目录')) if kind in ('csv','html') else None
        if kind in ('csv','html') and not destination:return
        folders=[item['folder'] for item in items]
        def done(value):
            self.status.set(f"{tr('已处理 ')}{len(value['items'])} · {tr('失败 ')}{len(value['errors'])}")
            if value['errors']:messagebox.showwarning('Stintrix','\n'.join(v['error'] for v in value['errors'][:8]),parent=self.root)
        self.work(lambda:transfer_batch(folders,lambda folder:columnar(folder) if kind=='columnar' else restore(folder) if kind=='restore' else export(folder,destination,kind)),done)
    self.with_selection(action,None)

def compress_selected(self):
    from session_compression import compress
    from session_archive import transfer_batch
    def action(items):
        folders=[item['folder'] for item in items]
        def done(value):
            saved=sum(item['saved_bytes'] for item in value['items'])
            failures=len(value['errors'])+sum(len(item['errors']) for item in value['items'])
            self.status.set(f"{tr('已无损节省 ')}{saved/1048576:.1f} MB · {tr('失败 ')}{failures}")
        self.work(lambda:transfer_batch(folders,compress),done)
    self.with_selection(action,None)

def export_package(self):
    from session_archive import export_session,transfer_batch
    if getattr(self,'exporting',False):self.status.set(tr('赛事包正在导出，请等待完成'));return
    def action(items):
        directory=filedialog.askdirectory(parent=self.root,title=tr('选择赛事包导出目录'))
        if not directory:return
        import archive_preferences
        format=archive_preferences.load(self.data_path)['format']
        keys=[item['key'] for item in items];self.exporting=True;self.shell.status_feedback.busy('package-export')
        self.status.set(f"{tr('正在导出 ')}{len(keys)} · {format.upper()}…")
        def done(result,error):
            self.exporting=False;self.shell.status_feedback.busy('package-export',False)
            if error:self.status.set(tr('导出未完成：') + error);messagebox.showerror('Stintrix',error,parent=self.root);return
            self.status.set(f"{tr('已导出 ')}{len(result['items'])}{tr(' 场赛事 · 失败 ')}{len(result['errors'])}{tr(' 场')}")
            if result['items']:os.startfile(directory)
            if result['errors']:
                details='\n'.join(v['item']+'：'+v['error'] for v in result['errors'][:10])
                messagebox.showwarning(tr('部分赛事未导出'),details,parent=self.root)
        self.run_background(lambda:transfer_batch(keys,lambda key:export_session(self.data_path,key,Path(directory),format=format)),done)
    self.with_selection(action,None)

def import_package(self):
    from session_archive import import_session
    from session_archive import transfer_batch
    from archive_preferences import load
    paths=filedialog.askopenfilenames(parent=self.root,title=tr('导入赛事包'),filetypes=[('Stintrix ZIP / 7z','*.zip *.7z')])
    if paths:
        verify=load(self.data_path)['verify']
        def done(value):
            self.refresh()
            mode=tr('完整校验') if verify else tr('快速导入')
            self.status.set(f"{mode} · {tr('成功 ')}{len(value['items'])} · {tr('失败 ')}{len(value['errors'])}")
            if value['errors']:messagebox.showwarning('Stintrix','\n'.join(Path(v['item']).name+'：'+v['error'] for v in value['errors'][:10]),parent=self.root)
        self.work(lambda:transfer_batch(paths,lambda path:import_session(self.data_path,path,verify=verify)),done)

def import_native(self):
    from telemetry_import import import_recording
    from session_reports import make_report
    path=filedialog.askopenfilename(parent=self.root,title=tr('导入 LMU 官方遥测（只读）'),filetypes=[('LMU 遥测','*.duckdb')])
    if path:
        def work():
            folder=import_recording(path,self.data_path);make_report(folder);return folder
        self.work(work,lambda _:self.refresh())
