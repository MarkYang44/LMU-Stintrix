"""Item-boundary cancellation and retry; workers publish data, never touch Tk."""
import os,threading,queue,tkinter as tk
from pathlib import Path
from control_theme import T
from control_list import SessionList
from i18n import tr
from control_search import SearchField
from control_fields import Select


def jobs(app):
    owners=[app,getattr(app,'hud',None),getattr(app,'control_center',None),getattr(getattr(app,'on_menu',None),'__self__',None)];entries=[];seen=set()
    for owner in owners:
        for job in getattr(owner,'batch_jobs',[]):
            if id(job) not in seen and job.window.winfo_exists():entries.append(job);seen.add(id(job))
    return entries


def running(app):return next((job for job in jobs(app) if job.busy),None)


def history(app):
    entries=jobs(app)
    for job in entries:
        mapping={f'{item.sequence:02} · {tr(item.title)}':item for item in entries};job.history_items=mapping
        job.history_box.configure(values=list(mapping));job.history_choice.set(next(label for label,item in mapping.items() if item is job))
        if job.result_mode:
            if len(entries)>1:job.history_box.pack(fill='x',padx=12,pady=(0,4),before=job.summary_label)
            else:job.history_box.pack_forget()


def issue_text(error):
    text=str(error)
    return text if text.strip() else type(error).__name__ if isinstance(error,BaseException) else '未提供错误详情'


def run_items(values,operation,stop,notify):
    results=[]
    for index,value in values:
        if stop.is_set():break
        notify(index,'正在处理','')
        try:
            result=operation(value);errors=result.get('errors',[]) if isinstance(result,dict) else []
            error='; '.join(issue_text(e) for e in errors)
            status='部分失败' if errors else '已完成'
        except Exception as exception:result=None;error=issue_text(exception);status='失败'
        results.append((index,result,error));notify(index,status,error)
    return results


def show(app):
    job=getattr(app,'batch_job',None)
    if job and job.window.winfo_exists():job.window.deiconify();job.window.lift()
    else:app.status.set(tr('暂无批量任务'))


def start(app,title,values,operation,names=None,destination=None,on_done=None,result_actions=False):
    previous=running(app)
    if previous and previous.busy:app.batch_job=previous;show(app);app.status.set(tr('请等待当前批量任务结束'));return previous
    entries=jobs(app);completed=[j for j in entries if all(s=='已完成' for s in j.states)]
    for old in completed[:-4]:old.window.destroy();entries.remove(old)
    job=BatchJob(app,title,list(values),operation,names,destination,on_done,result_actions);entries.append(job);app.batch_jobs=entries;app.batch_job=job;history(app);return job


class BatchJob:
    def __init__(self,app,title,values,operation,names,destination,on_done,result_actions=False):
        self.title=title;self.sequence=getattr(app,'batch_sequence',0)+1;app.batch_sequence=self.sequence
        self.app=app;self.values=values;self.operation=operation;self.destination=destination;self.on_done=on_done;self.result_mode=bool(result_actions);self.summary_base=''
        self.states=['等待处理']*len(values);self.errors=['']*len(values);self.results={};self.outputs={};self.result_actions=None;self.busy=False;self.stop=threading.Event();self.events=queue.SimpleQueue();self.timer=None
        self.names=names or [Path(str(value)).name for value in values]
        self.window=w=tk.Toplevel(app.root);w.title(tr(title));w.geometry('1000x640');w.minsize(720,560);w.configure(bg=T.BG)
        footer=tk.Frame(w,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=18)
        body=tk.Frame(w,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=(18,0))
        app.label(body,title,15 if result_actions else 18,T.FG,True).pack(anchor='w',padx=12,pady=(8,3) if result_actions else 12)
        self.history_choice=tk.StringVar(w);self.history_box=Select(body,textvariable=self.history_choice,values=[],width=30);self.history_box.pack(fill='x',padx=12,pady=(0,8))
        def switch(_):
            selected=self.history_items.get(self.history_choice.get())
            if selected:
                self.window.withdraw();app.batch_job=selected;show(app)
            history(app)
        self.history_box.bind('<<ComboboxSelected>>',switch)
        self.text=tk.StringVar(w);summary=self.summary_label=app.label(body,self.text,10);summary.pack(fill='x',padx=12,pady=5);summary.bind('<Configure>',lambda e:summary.configure(wraplength=max(100,e.width)))
        self.query=tk.StringVar(w);self.view=tk.StringVar(w,value='all');self.visible_count=tk.StringVar(w)
        tools=tk.Frame(body,bg=T.CARD);tools.pack(fill='x',padx=12,pady=5)
        self.view_box=Select(tools,textvariable=self.view,values=['all','failed','pending'],labels=dict(all='全部任务',failed='失败 / 部分失败',pending='未完成任务'),width=18)
        self.view_box.pack(side='left',padx=(0,8));self.view_box.bind('<<ComboboxSelected>>',lambda _:self.render())
        self.search_field=SearchField(tools,self.query,self.render);self.search_field.pack(side='left',fill='x',expand=True)
        hint=app.label(body,'筛选只影响显示；重试处理全部失败项。' if result_actions else '搜索文件名或错误；仅筛选显示，重试仍处理全部失败项。',9,T.MUTED);hint.pack(fill='x',padx=12)
        hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(100,e.width)))
        if not result_actions:app.label(body,self.visible_count,9,T.MUTED).pack(fill='x',padx=12,pady=(4,0))
        w.bind('<Control-f>',lambda _:(self.search_field.entry.focus_set(),'break')[1])
        self.table=SessionList(body,columns=('name','state','error'),height=7,selectmode='extended')
        for key,label,width in [('name','赛事 / 文件',350),('state','处理状态',130),('error','详情',420)]:self.table.heading(key,label);self.table.column(key,width,70,key in ('name','error'))
        self.table.pack(fill='both',expand=True,padx=12,pady=8)
        if result_actions:
            from control_batch_results import BatchResults
            self.result_actions=BatchResults(self,footer)
        actions=app.row(footer);self.stop_button=app.button(actions,'当前项完成后停止',self.stop_after,False,190)
        self.retry_button=app.button(actions,'仅重试失败项',lambda:self.run([i for i,s in enumerate(self.states) if s in ('失败','部分失败')]),False,165)
        self.resume_button=app.button(actions,'继续剩余项',lambda:self.run([i for i,s in enumerate(self.states) if s=='等待处理']),False,150)
        self.copy_button=app.button(actions,'复制全部失败详情',self.copy_errors,False,190)
        if destination:app.button(actions,'打开输出目录',lambda:os.startfile(destination),False,155)
        def arrange(event):
            gap=8;x=y=height=0
            for child in actions.winfo_children():
                child.pack_forget();child.place_forget()
                if not getattr(child,'batch_visible',True):continue
                width=child.winfo_reqwidth();h=child.winfo_reqheight()
                if x and x+width>event.width:y+=height+gap;x=height=0
                child.place(x=x,y=y,width=min(event.width,width),height=h);x+=width+gap;height=max(height,h)
            actions.pack_propagate(False);actions.configure(height=max(1,y+height))
        actions.bind('<Configure>',arrange)
        self.actions_frame=actions
        w.bind('<Destroy>',self.dispose,add='+')
        def translate():
            w.title(tr(self.title))
            for key,label in [('name','赛事 / 文件'),('state','处理状态'),('error','详情')]:self.table.heading(key,label)
            self.render();history(app)
            for child in actions.winfo_children():
                if hasattr(child,'paint'):child.paint()
        w.retranslate=translate
        self.run(list(range(len(values))));w.protocol('WM_DELETE_WINDOW',self.hide)
    def render(self):
        words=self.query.get().casefold().split();view=self.view.get();rows=[]
        for i,state in enumerate(self.states):
            if view=='failed' and state not in ('失败','部分失败'):continue
            if view=='pending' and state not in ('等待处理','正在处理'):continue
            text=(self.names[i]+' '+self.errors[i]+' '+tr(self.errors[i])).casefold()
            if not all(word in text for word in words):continue
            # Cells have one row of height; copying retains the complete raw lines.
            detail=' · '.join(tr(self.errors[i]).splitlines())
            rows.append((str(i),(self.names[i],tr(state),detail)))
        self.table.replace(rows,self.table.selection())
        if self.query.get().strip():self.table.set_empty('没有匹配的任务','清空搜索',self.search_field.clear)
        elif view in ('failed','pending'):self.table.set_empty('没有失败项' if view=='failed' else '没有未完成任务','查看全部任务',self.reset_view)
        else:self.table.set_empty('暂无任务')
        self.visible_count.set(tr('显示 {shown}/{total} 项').format(shown=len(rows),total=len(self.states)))
        if self.result_mode:self.text.set(self.summary_base+' · '+self.visible_count.get())
        if self.result_actions:self.result_actions.sync()
    def reset_view(self):self.view.set('all');self.render()
    def copy_errors(self):
        rows=[f'{self.names[i]}\n{tr(state)}\n{tr(self.errors[i])}' for i,state in enumerate(self.states) if state in ('失败','部分失败')]
        if rows:
            self.table.copy_text('\n\n'.join(rows));self.app.status.set(tr('已复制全部失败详情'))
    def dispose(self,event):
        if event.widget is not self.window:return
        if self.timer:self.window.after_cancel(self.timer);self.timer=None
        for variable in (self.query,self.view,self.visible_count,self.text,self.history_choice):variable.__del__();variable._tk=None
    def draw(self):
        if not self.window.winfo_exists():return
        self.render()
        completed=sum(s not in ('等待处理','正在处理') for s in self.states);current=next((i for i,s in enumerate(self.states) if s=='正在处理'),None)
        text=tr('已处理')+f' {completed}/{len(self.values)}'
        failed=sum(s in ('失败','部分失败') for s in self.states)
        if failed:text+=' · '+tr('失败')+f' {failed}'
        saved=sum(value.get('saved_bytes',0) for value in self.results.values() if isinstance(value,dict))
        if saved:text+=' · '+tr('已无损节省 ')+f'{saved/1048576:.1f} MiB'
        if current is not None:text+=' · '+tr('当前')+f' {current+1}/{len(self.values)} · '+self.names[current]
        if self.stop.is_set() and self.busy:text+=' · '+tr('当前项完成后停止')
        self.summary_base=text;self.text.set(text+(' · '+self.visible_count.get() if self.result_mode else ''));self.app.status.set(text)
        self.stop_button.configure(state='normal' if self.busy and not self.stop.is_set() else 'disabled')
        self.retry_button.configure(state='normal' if not self.busy and any(s in ('失败','部分失败') for s in self.states) else 'disabled')
        self.resume_button.configure(state='normal' if not self.busy and '等待处理' in self.states else 'disabled')
        self.copy_button.configure(state='normal' if failed else 'disabled')
        if self.result_actions:
            for button,visible in [(self.stop_button,self.busy),(self.retry_button,bool(failed)),(self.resume_button,not self.busy and '等待处理' in self.states),(self.copy_button,bool(failed))]:button.batch_visible=visible
            self.actions_frame.event_generate('<Configure>')
    def drain(self):
        changed=False
        while not self.events.empty():
            index,status,error=self.events.get();self.states[index]=status;self.errors[index]=error;changed=True
        if changed:self.draw()
    def poll(self):
        self.timer=None;self.drain()
        if self.busy:self.timer=self.window.after(120,self.poll)
    def run(self,indices):
        if self.busy or not indices:return
        other=running(self.app)
        if other is not None and other is not self:
            self.app.batch_job=other;show(self.app);self.app.status.set(tr('请等待当前批量任务结束'));return
        self.busy=True;self.stop.clear()
        for i in indices:self.states[i]='等待处理';self.errors[i]=''
        values=[(i,self.values[i]) for i in indices];self.draw()
        def done(result,error):
            self.busy=False
            if self.timer:self.window.after_cancel(self.timer);self.timer=None
            self.drain()
            if error:self.app.status.set(error)
            else:
                for index,value,issue in result:
                    if isinstance(value,dict) and value.get('path'):self.outputs[index]=value
                    if self.states[index]=='已完成':self.results[index]=value
                    else:self.results.pop(index,None)
                if self.on_done:self.on_done(dict(items=list(self.results.values()),errors=[dict(item=self.names[i],error=issue_text(self.errors[i])) for i,state in enumerate(self.states) if state in ('失败','部分失败')]))
            self.draw()
        self.app.run_background(lambda:run_items(values,self.operation,self.stop,lambda *event:self.events.put(event)),done);self.poll()
    def stop_after(self):self.stop.set();self.draw()
    def hide(self):
        self.window.withdraw()
    def allow_exit(self):
        if not self.busy:return True
        from control_confirm import ask
        answer=ask(self.app.root,'批量任务正在处理','当前文件完成前请保持程序运行。可请求处理完当前项后停止。',[('stop','当前项完成后停止'),('cancel','继续处理')])
        if answer=='stop':self.stop_after()
        self.window.deiconify();self.window.lift();return False
