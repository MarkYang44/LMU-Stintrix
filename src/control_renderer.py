"""Manual renderer settings retain drafts across pages and guard application exit."""
import tkinter as tk
from tkinter import filedialog
import renderer_config
from control_fields import Field
from control_theme import T
from control_sections import Disclosure
from control_flow import install
from i18n import tr


class RendererEditor:
    def __init__(self,app,body):
        self.app=app;self.frame=body;self.loading=False;self.baseline=self.read()
        values={**self.baseline,**(getattr(app,'renderer_draft',None) or {})}
        app.renderer_mode=tk.StringVar(body,value=values['renderer_mode']);app.renderer_path=tk.StringVar(body,value=values['renderer_path']);app.renderer_baseline=dict(self.baseline)
        self.variables=dict(renderer_mode=app.renderer_mode,renderer_path=app.renderer_path);body.renderer_variables=self.variables
        app.choice(body,'生成方式',app.renderer_mode,['racecom','native'],labels={'racecom':'RaceCom 原版','native':'Stintrix 兼容版'})
        self.path=Field(body,textvariable=app.renderer_path,font=('Segoe UI',10));self.path.pack(fill='x',pady=8)
        row=app.row(body);install(row);app.button(row,'选择生成器',self.choose,False,140);self.button=app.button(row,'保存配置',self.save,True,140)
        self.status=tk.StringVar(body);body.renderer_status=self.status;self.feedback=app.label(body,self.status,9,T.MUTED);self.feedback.pack(fill='x',pady=4);self.feedback.bind('<Configure>',lambda e:self.feedback.configure(wraplength=max(100,e.width)))
        details=Disclosure(body,app,'renderer-details','格式标识与组件说明')
        label=app.label(details.body,'racecom = 原版版式；native = Stintrix 兼容版式。\nGitHub 下载包不包含 RaceCom 程序、商标图片或个人记录。',9,T.MUTED);label.pack(fill='x',pady=4);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
        self.traces=[(v,v.trace_add('write',self.changed)) for v in self.variables.values()]
        self.binding=app.root.bind('<Control-s>',self.key,add='+');body.bind('<Destroy>',self.dispose,add='+');self.changed()
    def read(self):
        value=renderer_config.load(self.app.data_path);return dict(renderer_mode=value['mode'],renderer_path=value['executable'])
    def alive(self):return bool(self.frame.winfo_exists())
    def snapshot(self):return {key:v.get() for key,v in self.variables.items()}
    def capture(self):
        values=self.snapshot();self.app.renderer_draft={key:value for key,value in values.items() if value!=self.baseline[key]} or None
        return self.app.renderer_draft
    def changed(self,*_):
        if self.loading:return
        dirty=bool(self.capture());self.button.configure(state='normal' if dirty else 'disabled');self.feedback.configure(fg=T.ACCENT if dirty else T.MUTED)
        self.status.set(tr('生成器有未保存修改' if dirty else '生成器与已保存配置一致'))
    def fill(self,value):
        self.loading=True
        try:
            for key,v in self.variables.items():v.set(value[key])
        finally:self.loading=False
    def choose(self):
        value=filedialog.askopenfilename(parent=self.app.root,title=tr('选择 RaceCom 的 Image Generate.exe'),filetypes=[('RaceCom 图像生成器','*.exe')])
        if value:self.variables['renderer_path'].set(value)
    def clear_memory(self):
        self.app.renderer_draft=None;self.app.browsing.states.setdefault(3,{})['drafts']={}
    def save(self):
        if not self.capture():return True
        values=self.snapshot()
        try:renderer_config.save(dict(mode=values['renderer_mode'],executable=values['renderer_path']),self.app.data_path)
        except (ValueError,OSError) as error:
            self.feedback.configure(fg=T.RED);self.status.set(tr('生成器未保存：{error}').format(error=tr(str(error)) or type(error).__name__));self.app.status.set(self.status.get());return False
        self.baseline=self.read();self.app.renderer_baseline=dict(self.baseline);self.fill(self.baseline);self.clear_memory();self.changed();self.status.set(tr('图像生成器已配置；下一场结束自动生成到赛事文件夹'));self.app.status.set(self.status.get());return True
    def discard(self):
        self.baseline=self.read();self.app.renderer_baseline=dict(self.baseline);self.fill(self.baseline);self.clear_memory();self.changed()
    def key(self,_):
        if self.app.page==3 and self.app.data_tasks.current=='renderer':self.save();return 'break'
    def dispose(self,event):
        if event.widget is self.frame:
            self.app.root.unbind('<Control-s>',self.binding)
            for variable,token in self.traces:variable.trace_remove('write',token)
            self.status.__del__();self.status._tk=None


def capture(app):
    editor=getattr(app,'renderer_editor',None)
    if editor is not None and editor.alive():return editor.capture()
    return getattr(app,'renderer_draft',None)


def close_draft(app,done):
    if not capture(app):done();return
    from control_confirm import ask
    answer=ask(app.root,'生成器有未保存修改','生成方式或路径尚未保存。退出前请选择保存或放弃。',[('save','保存生成器并继续'),('discard','放弃生成器修改'),('cancel','继续编辑')])
    if answer=='cancel':return
    if answer=='discard':
        editor=getattr(app,'renderer_editor',None)
        if editor is not None and editor.alive():editor.discard()
        else:app.renderer_draft=None;app.browsing.states.setdefault(3,{})['drafts']={}
        done();return
    app.show_page(3);app.data_tasks.select('renderer');app.root.update_idletasks();app.scroll.yview_moveto(0)
    if app.renderer_editor.save():done()
