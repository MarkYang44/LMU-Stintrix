"""Reusable analysis sessions: latest-request scans, explicit drafts and frozen exports."""
import json,os,tkinter as tk
from copy import deepcopy
from functools import partial
from pathlib import Path
from control_theme import T
from control_widgets import px,backdrop
from control_video_widgets import Action,ScrollPage
from control_flow import install
from control_feedback import StatusFeedback
from control_motion import keyboard_action,reveal_window
from i18n import tr,Label


def key(entry):
    def stamp(path):
        try:s=Path(path).stat();return s.st_size,s.st_mtime_ns
        except OSError:return None
    folder=Path(entry['folder']).resolve();file=entry.get('file','')
    fields={k:entry.get(k) for k in ('track','layout','length_m','vehicle_class','conditions','time_s')}
    fields['session']=entry.get('session');fields['lap']=entry.get('lap',{}).get('number')
    return str(folder),str(file),json.dumps(fields,sort_keys=True,default=str),stamp(file) if file else None,stamp(folder/'session.json')


def existing(app,kind,entry):
    if app.closing:return None,None
    if not entry:app.status.set(tr('请选择一条纪录'));return None,None
    windows=getattr(app,'analysis_windows',{});app.analysis_windows=windows;identity=(kind,key(entry));window=windows.get(identity)
    if window is not None and window.winfo_exists():window.deiconify();window.lift();window.focus_force();return window,None
    return None,identity


def analyse(scanner,preference,policy):
    from storage import atomic_json
    exists=preference.exists();saved=json.loads(preference.read_text('utf-8-sig')) if exists else {}
    if not isinstance(saved,dict):raise ValueError('分析设置格式异常，请先检查配置文件')
    updated={**saved,**policy}
    if not exists or updated!=saved:preference.parent.mkdir(parents=True,exist_ok=True);atomic_json(preference,updated)
    return scanner(policy)


def continue_scan(previous,scanner,preference,policy):
    if previous is not None:previous.result()
    return analyse(scanner,preference,policy)


class AnalysisWindow:
    def __init__(self,app,identity,title,entry,size=(1100,820)):
        self.app=app;self.identity=identity;self.title=title;self.entry=deepcopy(entry);self.variables=[];self.buttons={};self.conditions={};self.editors=[];self.result=None;self.applied=None;self.running=None;self.pending=None;self.exporting=False;self.writing=False;self.failed=False;self.auto_job=None;self.notice=('',{});self.render=lambda _:None;self.on_translate=lambda:None;self.initial=None;self.submitted=None;self.edited=False;self.version=0;self.future=None
        w=tk.Toplevel(app.root);self.window=w;w.analysis_panel=self;app.analysis_windows[identity]=w;w.configure(bg=T.BG);w.transient(app.root);w.title(tr(title))
        width=min(px(w,size[0]),w.winfo_screenwidth()-80);height=min(px(w,size[1]),w.winfo_screenheight()-100);w.geometry(f'{width}x{height}');w.minsize(min(width,px(w,780)),min(height,px(w,560)))
        self.footer=tk.Frame(w,bg=T.CARD);self.footer.pack(side='bottom',fill='x',padx=18,pady=(0,14));self.status=self.variable();self.output=self.variable()
        self.feedback=StatusFeedback(self.footer,self.status);self.feedback.pack(fill='x',padx=10,pady=(8,4))
        self.saved=tk.Frame(self.footer,bg=T.CARD);Label(self.saved,text='最近保存',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9)).pack(side='left',padx=(0,8))
        self.path=tk.Entry(self.saved,textvariable=self.output,state='readonly',readonlybackground=T.FIELD,bg=T.FIELD,fg=T.FG,selectbackground=T.SELECT,selectforeground=T.FG,font=(T.FONT,9),relief='flat');self.path.pack(side='left',fill='x',expand=True);self.path.bind('<Control-a>',lambda _:(self.path.selection_range(0,'end'),'break')[1])
        self.actions=tk.Frame(self.footer,bg=T.CARD);self.actions.pack(fill='x',padx=10,pady=(0,8));install(self.actions)
        self.scroll=ScrollPage(w);self.scroll.pack(fill='both',expand=True,padx=18,pady=(14,8));self.scroll.canvas.configure(bg=T.CARD);self.body=self.scroll.body;self.body.configure(bg=T.CARD)
        self.heading(title,18,T.FG);from track_names import display
        self.heading(display(entry['track'])+' · '+entry['session'].get('vehicle',''),10,T.ACCENT)
        w.protocol('WM_DELETE_WINDOW',self.close);w.bind('<Escape>',lambda _:(self.close(),'break')[1]);w.bind('<Control-s>',lambda _:(keyboard_action(w,self.export),'break')[1]);w.bind('<F5>',lambda _:(keyboard_action(w,self.apply),'break')[1]);w.bind('<MouseWheel>',self.wheel)
        w.bind('<Destroy>',self.dispose,add='+');w.retranslate=self.translate;backdrop(w)
    def variable(self,value='',boolean=False):
        v=(tk.BooleanVar if boolean else tk.StringVar)(self.window,value=value);self.variables.append(v);return v
    def heading(self,text,size=10,color=None):
        label=Label(self.body,text=text,bg=T.CARD,fg=color or T.MUTED,font=(T.FONT,size),anchor='w',justify='left');label.pack(fill='x',padx=12,pady=6);label.bind('<Configure>',lambda e:label.configure(wraplength=max(80,e.width)));return label
    def button(self,key,label,command,enabled=lambda:True,primary=False):
        b=Action(self.actions,label,command,135,primary);b.pack(side='left');self.buttons[key]=b;self.conditions[key]=enabled;return b
    def alive(self):return not self.app.closing and bool(self.window.winfo_exists())
    def ready(self):return self.result is not None and self.running is None and not self.failed and self.applied==self.draft() and not self.exporting and not self.writing
    def say(self,text,**values):self.notice=(text,values);self.status.set(tr(text).format(**values))
    def sync(self):
        if not self.alive():return
        for key,b in self.buttons.items():b.configure(state='normal' if self.conditions[key]() else 'disabled')
        for widget in self.editors:
            (widget.entry if hasattr(widget,'entry') else widget).configure(state='disabled' if self.exporting or self.writing else 'normal')
    def changed(self,*_):
        if self.exporting or self.writing:return
        self.edited=self.draft()!=self.submitted
        self.say('分析条件有修改，请应用后更新结果' if self.applied!=self.draft() else '分析正在进行，请稍候' if self.running is not None else '上次分析未完成，请重新分析' if self.failed else '当前条件已有分析结果' if self.result is not None else '等待分析');self.sync()
    def schedule(self):
        self.changed()
        if self.auto_job is not None:self.window.after_cancel(self.auto_job)
        self.auto_job=self.window.after(120,self.automatic)
    def automatic(self):self.auto_job=None;self.apply()
    def apply(self):
        if not self.alive() or self.exporting or self.writing:return
        if self.auto_job is not None:self.window.after_cancel(self.auto_job);self.auto_job=None
        try:policy=self.policy()
        except (ValueError,TypeError,OSError) as error:self.failed=True;self.say('分析条件未应用：{error}',error=error);self.sync();return
        request=(deepcopy(self.draft()),deepcopy(policy))
        self.submitted=request[0];self.edited=False
        if self.running is not None:
            self.pending=request if request[0]!=self.running[0] else None;self.say('已更新待处理条件，当前分析完成后继续' if self.pending else '分析正在进行，请稍候');self.sync();return
        self.start(request)
    def start(self,request):
        self.running=request;self.failed=False;self.feedback.busy('scan');self.say(self.loading);self.sync()
        def done(value,error):
            if not self.alive():return
            self.running=None;self.feedback.busy('scan',False);pending=self.pending;self.pending=None
            if pending is not None and pending[0]==self.draft():self.start(pending);return
            if request[0]!=self.draft():self.changed();return
            if error:self.failed=True;self.say('分析未完成：{error}',error=error)
            else:self.result=value;self.applied=request[0];self.failed=False;self.edited=False;self.version+=1;self.render(value)
            self.sync()
        self.future=self.app.run_background(partial(analyse,self.scanner,self.preference,request[1]),done)
    def export(self):
        if not self.ready():return
        value=self.result;writer=self.exporter;self.exporting=True;self.feedback.busy('export');self.say('正在保存当前分析报告…');self.sync()
        def done(path,error):
            if self.alive():self.exporting=False;self.feedback.busy('export',False)
            if error:
                if self.alive():self.say('报告保存失败，可重试：{error}',error=error);self.sync()
                elif not self.app.closing:self.app.status.set(tr('报告保存失败，可重试：{error}').format(error=error))
                return
            if not self.alive():
                if not self.app.closing:self.app.status.set(tr('报告已保存：{path}').format(path=path))
                return
            self.output.set(str(path));self.saved.pack(fill='x',padx=10,pady=(0,6),before=self.actions);self.open_last();self.sync()
        self.app.run_background(partial(writer,value),done)
    def open_last(self):
        path=Path(self.output.get())
        if not self.output.get() or not path.is_file():self.say('保存的报告已移动或删除，请重新导出');return
        try:os.startfile(str(path));self.say('报告已保存，路径可在下方复制')
        except OSError as error:self.say('报告已保存，浏览器未能打开：{error}',error=error)
    def open_folder(self):
        if not self.output.get():return
        try:os.startfile(str(Path(self.output.get()).parent))
        except OSError as error:self.say('目录打开失败：{error}',error=error)
    def finish(self):
        self.table.viewport.bind('<MouseWheel>',self.table_wheel)
        self.initial=deepcopy(self.draft());self.submitted=self.initial;self.button('open','打开上次报告',self.open_last,lambda:bool(self.output.get()));self.button('folder','打开导出目录',self.open_folder,lambda:bool(self.output.get()));self.translate();self.sync();self.apply();reveal_window(self.window)
        from control_confirm import register
        register(self.app,self.window,self.close)
    def close(self,done=None,exiting=False):
        if self.edited:
            from control_confirm import ask
            if ask(self.window,'分析条件尚未应用','当前条件尚未得到分析结果，关闭会丢弃本窗口中的修改。',[('discard','放弃条件修改并关闭'),('cancel','继续编辑')])!='discard':return
        if self.pending is not None:
            request=self.pending;self.pending=None;app=self.app
            def finished(value,error):
                if error and not app.closing:app.status.set(tr('分析未完成：{error}').format(error=error))
            app.run_background(partial(continue_scan,self.future,self.scanner,self.preference,request[1]),finished)
        self.window.destroy()
        if done:done()
    def wheel(self,event):
        widget=event.widget
        while widget is not None and widget is not self.window:
            if widget.__class__.__name__=='SessionList':return
            if widget is self.scroll:self.scroll.wheel(event.delta);return 'break'
            widget=getattr(widget,'master',None)
    def table_wheel(self,event):
        table=self.table;limit=table.limit()
        if not event.state&1 and (limit<=0 or event.delta>0 and table.offset<=0 or event.delta<0 and table.offset>=limit):
            table.tooltip.hide();self.scroll.wheel(event.delta);return 'break'
        return table.wheel(event)
    def translate(self):
        text,values=self.notice;self.window.title(tr(self.title));self.on_translate();self.say(text,**values)
        for b in self.buttons.values():b.configure(width=max(px(b,100),b.font.measure(tr(b.label))+px(b,36)));b.paint()
        self.actions.event_generate('<Configure>',width=self.actions.winfo_width())
    def dispose(self,event):
        if event.widget is not self.window:return
        if self.auto_job is not None:self.window.after_cancel(self.auto_job);self.auto_job=None
        self.app.analysis_windows.pop(self.identity,None);self.pending=None;self.result=None
        for v in self.variables:
            if v._tk is not None:v.__del__();v._tk=None
        self.variables.clear()
