"""Immediate local report browsing, independent of the external image viewer."""
from collections import OrderedDict
from pathlib import Path
import os,tkinter as tk
from control_theme import T
from control_widgets import px,backdrop
from control_video_widgets import Action
from control_flow import install
from control_feedback import StatusFeedback
from control_image_viewport import ImageViewport
from report_images import ImageLoader,stamp
from i18n import tr,Label

NAMES={'圈速单.png':'圈速单','比赛日志.png':'赛事日志'}


def show(app,folder,name):
    if app.closing:return None
    folder=Path(folder).resolve();root=Path(app.data_path).resolve()
    if name not in NAMES or folder==root or not folder.is_relative_to(root):raise ValueError('报告不在当前记录目录')
    if not (folder/name).resolve().is_relative_to(folder):raise ValueError('报告不在当前记录目录')
    viewer=getattr(app,'report_image_viewer',None)
    if viewer is None or not viewer.window.winfo_exists():
        loader=getattr(app,'report_image_loader',None)
        if loader is None or loader.closed:loader=ImageLoader();app.report_image_loader=loader
        viewer=ReportViewer(app,loader);app.report_image_viewer=viewer
    viewer.open(folder,name);return viewer.window


def generate(app,folder,force=False):
    if app.closing:return
    if getattr(app,'image_report_job',None) is not None:return
    job=dict(folder=Path(folder),force=force);app.image_report_job=job
    app.status.set(tr('正在后台生成报告图片…'))
    def work():
        from race_report import generate as render
        return render(folder,force=True) if force else render(folder)
    def done(result,error):
        if getattr(app,'image_report_job',None) is job:app.image_report_job=None
        if app.closing:return
        app.status.set(str(error) if error else tr('报告图片已生成'))
        viewer=getattr(app,'report_image_viewer',None)
        if viewer is not None and viewer.window.winfo_exists():viewer.generated(folder,error)
    app.run_background(work,done)


class ReportViewer:
    def __init__(self,app,loader):
        self.app=app;self.loader=loader;self.folder=None;self.name=None;self.key=None;self.poll_job=None;self.awaiting=False;self.views=OrderedDict();self.buttons={};self.message_key='';self.detail='';self.open_started=0;self.display_ms=None
        w=tk.Toplevel(app.root);self.window=w;w.configure(bg=T.BG);w.transient(app.root)
        w.geometry(f'{min(px(w,1180),w.winfo_screenwidth()-80)}x{min(px(w,820),w.winfo_screenheight()-100)}');w.minsize(min(px(w,780),w.winfo_screenwidth()-60),min(px(w,560),w.winfo_screenheight()-80))
        self.context=tk.StringVar(w);self.status=tk.StringVar(w);self.percent=tk.StringVar(w,value='100%')
        footer=tk.Frame(w,bg=T.BG);footer.pack(side='bottom',fill='x',padx=18,pady=(6,12));self.feedback=StatusFeedback(footer,self.status);self.feedback.pack(fill='x')
        hint=Label(footer,text='滚轮浏览 · Ctrl+滚轮缩放 · 拖动平移 · ←/→ 切换报告 · Esc 关闭',bg=T.BG,fg=T.MUTED,font=(T.FONT,9),anchor='w',justify='left');hint.pack(fill='x',pady=(4,0));hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(80,e.width)))
        context=Label(w,textvariable=self.context,bg=T.BG,fg=T.MUTED,font=(T.FONT,9),anchor='w',justify='left');context.pack(fill='x',padx=18,pady=(12,4));context.bind('<Configure>',lambda e:context.configure(wraplength=max(80,e.width)))
        actions=tk.Frame(w,bg=T.BG);actions.pack(fill='x',padx=16,pady=(0,6));self.actions=actions
        commands=[('圈速单.png','圈速单',lambda:self.open(self.folder,'圈速单.png'),105),('比赛日志.png','赛事日志',lambda:self.open(self.folder,'比赛日志.png'),105),
            ('width','适应宽度',lambda:self.viewport.fit('width'),110),('all','适应整图',lambda:self.viewport.fit('all'),110),('one','100%',lambda:self.viewport.fit('one'),75),
            ('minus','−',lambda:self.viewport.zoom(1/1.2),48),('plus','＋',lambda:self.viewport.zoom(1.2),48),
            ('system','系统查看器',self.open_system,125),('folder','赛事目录',self.open_folder,110),('reload','重新读取',self.reread,110),('generate','重新生成图片',self.regenerate,145)]
        for key,label,command,width in commands:
            b=Action(actions,label,command,width);b.pack(side='left');self.buttons[key]=b
        Label(actions,textvariable=self.percent,bg=T.BG,fg=T.ACCENT,font=(T.FONT,10),width=6).pack(side='left');install(actions)
        self.viewport=ImageViewport(w,self.view_changed);self.viewport.pack(fill='both',expand=True,padx=18)
        self.hint=self.viewport.canvas.create_text(0,0,text='',fill=T.MUTED,font=(T.FONT,11),justify='center')
        self.viewport.canvas.bind('<Configure>',self.hint_resized,add='+')
        w.bind('<Escape>',lambda _:(w.destroy(),'break')[1]);w.bind('<Left>',lambda _:self.key_action(lambda:self.switch(-1)));w.bind('<Right>',lambda _:self.key_action(lambda:self.switch(1)))
        for key,command in [('plus',lambda:self.viewport.zoom(1.2)),('equal',lambda:self.viewport.zoom(1.2)),('minus',lambda:self.viewport.zoom(1/1.2)),('0',lambda:self.viewport.fit('all')),('1',lambda:self.viewport.fit('one')),('f',lambda:self.viewport.fit('width')),('Home',lambda:self.viewport.edge()),('End',lambda:self.viewport.edge(True)),('Up',lambda:self.viewport.pan(dy=px(w,80))),('Down',lambda:self.viewport.pan(dy=-px(w,80))),('Prior',lambda:self.viewport.pan(dy=self.viewport.canvas.winfo_height()*.85)),('Next',lambda:self.viewport.pan(dy=-self.viewport.canvas.winfo_height()*.85))]:w.bind('<'+key+'>',lambda _,action=command:self.key_action(action))
        w.bind('<F5>',lambda _:self.key_action(self.reread));w.bind('<Destroy>',self.dispose,add='+');w.retranslate=self.translate;w.report_viewer=self;backdrop(w);self.translate()
    def hint_resized(self,event):
        self.viewport.canvas.coords(self.hint,event.width/2,event.height/2);self.viewport.canvas.itemconfigure(self.hint,width=max(80,event.width-50))
    def key_action(self,action):
        from control_motion import keyboard_action
        keyboard_action(self.window,action);return 'break'
    def switch(self,direction):
        names=list(NAMES);self.open(self.folder,names[(names.index(self.name)+direction)%len(names)])
    def alive(self):return not self.app.closing and bool(self.window.winfo_exists())
    def say(self,key,detail=''):
        self.message_key=key;self.detail=str(detail);self.status.set(tr(key)+(' · '+self.detail if detail else ''))
    def sync(self):
        job=getattr(self.app,'image_report_job',None);ready=self.viewport.image is not None
        for key in ('width','all','one','minus','plus'):self.buttons[key].configure(state='normal' if ready else 'disabled')
        self.buttons['generate'].configure(state='disabled' if job else 'normal')
        for name in NAMES:self.buttons[name].configure(selected=name==self.name)
        self.feedback.busy('generation',bool(job and job['folder']==self.folder))
    def view_changed(self):
        self.percent.set(f'{self.viewport.scale*100:.0f}%')
        self.viewport.canvas.itemconfigure(self.hint,state='hidden' if self.viewport.image is not None else 'normal')
    def remember_view(self):
        if self.key and self.viewport.image is not None:
            self.views[self.key]=self.viewport.snapshot();self.views.move_to_end(self.key)
            while len(self.views)>12:self.views.popitem(last=False)
    def open(self,folder,name):
        self.remember_view();self.folder=Path(folder);self.name=name;self.context.set(self.folder.name);self.window.title(tr('Stintrix · 报告图片')+' · '+tr(NAMES[name]));self.window.deiconify();self.window.lift();self.window.update_idletasks();self.load();self.viewport.canvas.focus_set()
    def load(self,allow_generate=True):
        import time
        if not self.alive():return
        if self.poll_job is not None:self.window.after_cancel(self.poll_job);self.poll_job=None
        self.remember_view();path=self.folder/self.name;self.open_started=time.perf_counter();self.display_ms=None;self.awaiting=False
        try:
            key=stamp(path)
            if key==self.key and self.viewport.image is not None:
                self.feedback.busy('image',False);self.say('已打开保存的图片',f'{self.viewport.image.width}×{self.viewport.image.height}');self.sync();return
            self.key=key;image=self.loader.request(path)
            if image is not None:self.present(image);return
            self.viewport.clear();self.say('正在读取报告图片…');self.viewport.canvas.itemconfigure(self.hint,text=tr('正在读取报告图片…'));self.feedback.busy('image');self.sync();self.poll_job=self.window.after(16,self.poll)
        except FileNotFoundError:
            self.key=None;self.loader.cancel();self.viewport.clear();self.feedback.busy('image',False)
            if allow_generate:
                self.awaiting=True;job=getattr(self.app,'image_report_job',None)
                self.say('正在后台生成报告图片…' if not job or job['folder']==self.folder else '另一场图片正在生成，完成后将处理当前赛事。');generate(self.app,self.folder)
            else:self.say('这张图片尚未生成；无完成圈时请切换赛事日志。')
            self.viewport.canvas.itemconfigure(self.hint,text=tr('报告图片尚未生成'));self.sync()
        except OSError as error:
            self.key=None;self.loader.cancel();self.viewport.clear();self.failed(str(error))
    def poll(self):
        self.poll_job=None
        if not self.alive():return
        image,error=self.loader.poll()
        if error:self.failed(error)
        elif image is not None:self.present(image)
        else:self.poll_job=self.window.after(16,self.poll)
    def present(self,image):
        import time
        self.awaiting=False;self.feedback.busy('image',False);self.viewport.show(image,self.views.get(self.key));self.display_ms=(time.perf_counter()-self.open_started)*1000
        self.say('已打开保存的图片',f'{image.width}×{image.height}');self.sync()
    def failed(self,error):
        self.feedback.busy('image',False);self.say('图片读取失败，可重新读取或使用系统查看器',error);self.viewport.canvas.itemconfigure(self.hint,text=tr('图片读取失败，可重新读取或使用系统查看器'));self.sync()
    def reread(self):
        self.remember_view();self.loader.forget(self.folder/self.name);self.key=None;self.load(False)
    def regenerate(self):
        if getattr(self.app,'image_report_job',None):return
        self.say('正在后台生成报告图片…');generate(self.app,self.folder,True);self.sync()
    def generated(self,folder,error):
        if not self.alive():return
        if Path(folder)==self.folder:
            if error:self.awaiting=False;self.say('图片生成失败，已有文件保留',error);self.sync();return
            self.remember_view()
            for name in NAMES:self.loader.forget(self.folder/name)
            self.key=None;self.load(False)
        elif self.awaiting:self.load()
        else:self.sync()
    def open_system(self):
        path=self.folder/self.name
        try:
            if not path.is_file():self.say('这张图片尚未生成；无完成圈时请切换赛事日志。');return
            os.startfile(str(path))
        except OSError as error:self.say('系统查看器未能打开图片；可继续使用内置查看器',error)
    def open_folder(self):
        try:os.startfile(str(self.folder))
        except OSError as error:self.say('目录打开失败',error)
    def translate(self):
        self.window.title(tr('Stintrix · 报告图片')+' · '+tr(NAMES.get(self.name,'圈速单')));self.say(self.message_key,self.detail)
        for key,b in self.buttons.items():b.configure(width=max(px(b,48 if key in ('minus','plus') else 75),b.font.measure(tr(b.label))+px(b,36)));b.paint()
        self.actions.event_generate('<Configure>',width=self.actions.winfo_width());self.viewport.queue()
        if self.viewport.image is None:self.viewport.canvas.itemconfigure(self.hint,text=tr(self.message_key))
    def dispose(self,event):
        if event.widget is not self.window:return
        if self.poll_job is not None:self.window.after_cancel(self.poll_job);self.poll_job=None
        self.loader.cancel();self.views.clear()
        if getattr(self.app,'report_image_viewer',None) is self:self.app.report_image_viewer=None
        for variable in (self.context,self.status,self.percent):variable.__del__();variable._tk=None
