"""Page-owned record browsing with shared, navigation-safe background jobs."""
import copy,os,tkinter as tk
from functools import partial
from pathlib import Path
from control_flow import install
from control_feedback import StatusFeedback
from control_search import SearchField
from control_widgets import px
from i18n import tr


class Loader:
    """One job per record view, retained across page reconstruction."""
    def __init__(self,app):self.app=app;self.page=None;self.running=False;self.pending=False;self.reader=None;self.writing=False;self.title=''
    def bind(self,page,reader):
        self.page=page;self.reader=reader
        if self.running:page.feedback.busy('load');page.say(self.title);page.sync()
        else:self.read()
    def read(self,force=False):
        if self.running:self.pending=self.pending or force;return
        self.start(self.reader,'正在读取赛事记录…')
    def start(self,worker,title,writing=False):
        if self.running or self.app.closing:return False
        self.running=True;self.writing=writing;self.title=title
        if self.page and self.page.alive():self.page.feedback.busy('load');self.page.say(title);self.page.sync()
        def done(value,error):
            self.running=False;self.writing=False;pending=self.pending;self.pending=False;page=self.page
            if self.app.closing:return
            if page and page.alive():
                page.feedback.busy('load',False)
                if error:page.say('读取或同步未完成，可重试：{error}',error=error)
                else:page.accept(value)
                page.sync()
            elif writing or error:self.app.status.set(tr('读取或同步未完成，可重试：{error}').format(error=error) if error else tr('官方成绩同步完成，可返回查看'))
            self.writing=False
            if pending:self.read()
        self.app.run_background(worker,done);return True


class RecordPage:
    def __init__(self,app,kind,body):
        self.app=app;self.kind=kind;self.host=app.content;self.generation=app.scan_generation;self.disposed=False;self.variables={};self.buttons={};self.conditions={};self.rows=[];self.selected=None;self.notice=('',{});self.actions=[];self.identity=lambda e:e['id'];self.render=lambda:None
        contexts=getattr(app,'record_browser_context',{});app.record_browser_context=contexts;self.context=contexts.setdefault(kind,{})
        loaders=getattr(app,'record_loaders',{});app.record_loaders=loaders;self.loader=loaders.setdefault(kind,Loader(app))
        self.host.record_browser=self;self.restore_job=None;self.captured=False;self.cleanups=[]
        self.status=self.variable('status');self.feedback=StatusFeedback(body,self.status);self.feedback.pack(fill='x',pady=6)
        self.query=self.variable('query',self.context.get('query',''))
        self.populated=False;self.query.trace_add('write',lambda *_:self.context.update(query=self.query.get()))
    def variable(self,name,value=''):
        v=tk.StringVar(self.host,value=value);self.variables[name]=v;return v
    def search(self,row,**options):
        options.setdefault('placeholder','搜索赛道、车辆或日期')
        field=SearchField(row,textvariable=self.query,**options);field.pack(side='left',fill='x',expand=True);self.search_field=field;self.app.search_target=field;return field
    def row(self,parent):
        row=self.app.row(parent);install(row);self.actions.append(row);return row
    def button(self,parent,key,title,command,enabled=lambda:True,primary=False):
        b=self.app.button(parent,title,command,primary,135);self.buttons[key]=b;self.conditions[key]=enabled;return b
    def alive(self):return not self.disposed and not self.app.closing and self.generation==self.app.scan_generation and bool(self.host.winfo_exists())
    def say(self,text,**values):self.notice=(text,values);self.status.set(tr(text).format(**values))
    def sync(self):
        if not self.alive():return
        for key,b in self.buttons.items():b.configure(state='normal' if self.conditions[key]() else 'disabled')
        if hasattr(self,'participation_notice'):self.participation_notice.sync()
        if hasattr(self,'filter_panel'):self.filter_panel.sync()
    def populate(self,rows):
        from control_event_filters import replace_rows
        selected=self.identity(self.selected) if self.selected else self.context.get('selected')
        chosen=next((key for key,e,_ in rows if self.identity(e)==selected),None)
        if chosen is None and rows:chosen=rows[0][0]
        offset=self.table.offset;xoffset=self.table.xoffset
        if not self.populated:offset=self.context.get('offset',offset);xoffset=self.context.get('xoffset',xoffset)
        initial=not self.populated;self.populated=True;self.rows=rows;self.lookup={key:e for key,e,_ in rows};replace_rows(self.table,[(key,values) for key,_,values in rows],(chosen,) if chosen is not None else ())
        self.table.offset=offset;self.table.xoffset=xoffset
        self.mutating=True;self.table.selection_set((chosen,) if chosen is not None else ());self.mutating=False;self.choose()
        if initial and self.context.get('scroll') is not None:self.restore_job=self.host.after_idle(self.restore_scroll)
    def choose(self,*_):
        if getattr(self,'mutating',False):return
        key=next(iter(self.table.selection()),None);self.selected=getattr(self,'lookup',{}).get(key)
        if self.selected:self.context['selected']=self.identity(self.selected)
        self.render();self.sync()
    def capture(self):
        self.captured=True
        if hasattr(self,'table'):self.context.update(offset=self.table.offset,xoffset=self.table.xoffset)
        try:self.context['scroll']=self.app.scroll.yview()[0]
        except tk.TclError:pass
    def hide(self,event):
        if event.widget is self.host and not self.disposed:self.capture()
    def restore_scroll(self):
        self.restore_job=None
        if self.alive():
            self.host.update_idletasks()
            if self.alive():self.app.scroll.yview_moveto(self.context.get('scroll',0))
    def open(self,path):
        try:
            if not Path(path).exists():raise FileNotFoundError(tr('文件或目录已移动或删除'))
            os.startfile(str(path));return True
        except OSError as error:self.say('打开失败：{error}',error=error);return False
    def finish(self,reader):
        if self.kind!='best' and hasattr(self,'modes'):
            from control_record_filter_panel import Panel
            self.filter_panel=Panel(self)
        from control_participation import UnknownNotice
        self.participation_notice=UnknownNotice(self)
        self.owner=tk.Frame(self.host);self.owner.record_variables=self.variables;self.owner.bind('<Destroy>',self.dispose,add='+')
        self.table.bind('<<TreeviewSelect>>',self.choose);self.table.viewport.bind('<Return>',lambda _:(self.primary(),'break')[1]);self.table.viewport.bind('<Double-1>',self.double)
        self.unmap_binding=self.host.bind('<Unmap>',self.hide,add='+');self.refresh_binding=self.app.root.bind('<F5>',self.refresh_key,add='+');self.host.retranslate=self.translate;self.translate();self.sync();self.loader.bind(self,reader)
    def double(self,event):
        key=self.table.at(event)
        if key is not None:self.table.selection_set((key,));self.primary()
        return 'break'
    def refresh_key(self,_=None):
        if self.alive():self.loader.read();return 'break'
    def translate(self):
        if self.disposed:return
        self.headers()
        if self.populated:self.refresh_rows()
        else:self.render()
        if hasattr(self,'report_update'):self.report_update()
        for b in self.buttons.values():b.configure(width=max(px(b,110),b.font.measure(tr(b.label))+px(b,36)))
        for row in self.actions:row.event_generate('<Configure>',width=row.winfo_width())
        self.say(self.notice[0],**self.notice[1])
    def dispose(self,event):
        if event.widget is not self.owner:return
        if self.restore_job is not None:self.host.after_cancel(self.restore_job);self.restore_job=None
        if not self.captured:self.capture()
        self.disposed=True
        for cleanup in self.cleanups:cleanup()
        self.cleanups.clear()
        self.host.unbind('<Unmap>',self.unmap_binding)
        if self.host.record_browser is self:self.host.record_browser=None;self.host.retranslate=lambda:None
        self.app.root.unbind('<F5>',self.refresh_binding)
        if self.loader.page is self:self.loader.page=None
        if getattr(self,'details',None) is not None:self.details.detach(self)
        if getattr(self,'exporter',None) is not None and self.exporter.page is self:self.exporter.page=None
        for v in self.variables.values():
            if v._tk is not None:v.__del__();v._tk=None


def curve_identity(entry):
    file=Path(entry['file'])
    try:s=file.stat();stamp=(s.st_size,s.st_mtime_ns)
    except OSError:stamp=None
    return str(file),str(entry['folder']),entry['lap']['number'],entry['time_s'],stamp


def save_curve(root,entry):
    from laps import write_compare
    from json_store import load
    from paths import ASSETS
    from uuid import uuid4
    folder=Path(root)/'PersonalRecords/History';folder.mkdir(parents=True,exist_ok=True);path=folder/(uuid4().hex+'.html')
    write_compare(path,ASSETS/'compare.html',[load(entry['file'])]);return str(path)


class CurveExport:
    def __init__(self,app):self.app=app;self.busy=False;self.path='';self.identity=None;self.caption='';self.page=None
    def attach(self,page):
        self.page=page;page.report_update();page.sync()
        if self.busy:page.feedback.busy('export');page.say('完整圈曲线正在生成，完成后可打开')
    def create(self,page,entry):
        if self.busy or entry is None:return
        identity=curve_identity(entry)
        if self.identity==identity and self.path and Path(self.path).is_file():self.open(page);return
        self.busy=True;caption=entry['session'].get('vehicle','')+' · '+str(entry['lap']['number']);page.say('正在生成完整圈曲线…');page.feedback.busy('export');page.sync()
        def done(path,error):
            self.busy=False;current=self.page
            if current and current.alive():current.feedback.busy('export',False)
            if error:
                if current and current.alive():current.say('曲线未生成，可重试：{error}',error=error);current.sync()
                elif not self.app.closing:self.app.status.set(tr('曲线未生成，可重试：{error}').format(error=error))
                return
            self.path=path;self.identity=identity;self.caption=caption
            if current and current.alive():current.report_update();current.say('曲线已保存，可打开上次曲线或复制路径');current.sync()
            if current is page and page.alive():self.open(page)
            elif not self.app.closing:self.app.status.set(tr('曲线已保存：{path}').format(path=path))
        snapshot=entry.copy();snapshot['lap']=dict(entry['lap']);snapshot['session']=dict(entry['session'])
        self.app.run_background(partial(save_curve,self.app.data_path,snapshot),done)
    def open(self,page):
        if not self.path or not Path(self.path).is_file():page.say('保存的曲线已移动或删除，请重新生成');return
        if page.open(self.path):page.say('曲线已保存，可打开上次曲线或复制路径')
