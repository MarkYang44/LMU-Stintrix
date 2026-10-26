"""Completed imports and report retries open their existing, ready local results."""
import os,tkinter as tk
from pathlib import Path
from control_theme import T
from control_fields import Field
from control_flow import install
from race_model import read_json
from i18n import tr


class BatchResults:
    def __init__(self,job,parent):
        self.job=job;self.app=job.app;self.frame=tk.Frame(parent,bg=T.CARD);self.frame.pack(fill='x',padx=8,pady=(2,0))
        self.path=tk.StringVar(self.frame);self.frame.result_path=self.path
        field=Field(self.frame,textvariable=self.path,font=(T.FONT,9));field.configure(height=28);field.entry.configure(state='readonly',readonlybackground=T.FIELD);field.pack(fill='x',pady=3)
        row=self.app.row(self.frame);install(row)
        self.buttons={}
        for key,label,command in [('folder','打开赛事目录',self.open_folder),('review','打开赛事复盘',self.open_review),('locate','在赛事列表定位',self.locate)]:self.buttons[key]=self.app.button(row,label,command,key=='review',145)
        job.table.selection_changed=self.sync;job.window.bind('<F5>',lambda _:self.sync())
        job.table.bind('<<TreeviewSelect>>',lambda _:self.sync(),add='+')
        job.table.bind('<Double-1>',lambda _:self.open_review());job.table.bind('<Return>',lambda _:self.open_review())
        self.frame.bind('<Destroy>',self.dispose,add='+');self.sync()
    def selected(self):
        selected=self.job.table.selection()
        if len(selected)!=1:return None
        index=int(selected[0]);value=self.job.outputs.get(index) or self.job.results.get(index)
        if self.job.busy or self.job.states[index] not in ('已完成','部分失败') or not isinstance(value,dict):return None
        folder=Path(value.get('path','')).resolve()
        if not value.get('path') or not folder.is_dir() or not folder.is_relative_to(self.app.data_path.resolve()):return None
        return folder
    def ready(self,folder):
        if folder is None or not (folder/'review.html').is_file():return False
        from report_state import current
        metadata=read_json(folder/'session.json',{})
        steps=current(folder).get('steps',{});review=steps.get('review',{}) if isinstance(steps,dict) else {}
        return isinstance(metadata,dict) and metadata.get('status') not in ('recording','write_error') and isinstance(review,dict) and review.get('state')=='ready'
    def sync(self):
        folder=self.selected();self.path.set(str(folder) if folder else tr('选择一个已完成的任务查看结果'))
        for key,b in self.buttons.items():
            valid=self.ready(folder) if key=='review' else folder is not None and (key!='locate' or (folder/'session.json').is_file())
            b.configure(state='normal' if valid else 'disabled')
    def open(self,review=False):
        folder=self.selected()
        if folder is None or review and not self.ready(folder):self.sync();return False
        try:os.startfile(str(folder/'review.html' if review else folder));return True
        except OSError as error:self.app.status.set(tr('打开失败：{error}').format(error=str(error) or type(error).__name__));return False
    def open_folder(self):return self.open()
    def open_review(self):return self.open(True)
    def locate(self):
        folder=self.selected()
        if folder is None:return False
        from control_session_location import locate
        if locate(self.app,folder):self.job.hide();return True
        return False
    def dispose(self,event):
        if event.widget is self.frame:self.path.__del__();self.path._tk=None
