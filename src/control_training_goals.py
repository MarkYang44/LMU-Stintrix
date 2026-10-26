"""Stable training follow-up selection with coalesced scans and safe completion."""
import copy,tkinter as tk
from functools import partial
from control_theme import T
from control_fields import Select
from control_list import SessionList
from control_history_chart import ProgressChart
from control_video_widgets import Action,ScrollPage
from control_feedback import StatusFeedback
from control_flow import install
from control_widgets import px,backdrop
from record_presentation import number
from training_goals import goals,evaluate,close
from i18n import tr,Label

COLUMNS=(('date','时间（UTC）',180),('loss','区间典型损失 / s',160),('gain','相比基准提升 / s',170),('std','波动 / s',110),('count','有效样本',110),('quality','样本与条件',160))


def show(app):
    if app.closing:return
    previous=getattr(app,'training_goal_window',None)
    if previous is not None and previous.winfo_exists():previous.deiconify();previous.lift();previous.focus_force();return previous
    panel=GoalWindow(app);app.training_goal_window=panel.window;backdrop(panel.window);return panel.window


class GoalWindow:
    def __init__(self,app):
        self.app=app;self.goals={};self.running=None;self.pending=None;self.result=None;self.loading=False;self.finishing=False;self.notice=('',{});self.refresh_selection=None;self.rows={};self.views={};self.displayed=None
        w=tk.Toplevel(app.root);self.window=w;w.goal_panel=self;w.title(tr('训练目标跟进'));w.configure(bg=T.BG);w.transient(app.root);w.geometry('1100x800');w.minsize(720,540)
        footer=tk.Frame(w,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=(0,14));self.status=tk.StringVar(w);self.feedback=StatusFeedback(footer,self.status);self.feedback.pack(fill='x',padx=10,pady=6)
        self.actions=tk.Frame(footer,bg=T.CARD);self.actions.pack(fill='x',padx=10,pady=(0,8));install(self.actions);self.buttons={}
        for key,title,command in (('refresh','刷新跟进',self.refresh),('finish','结束当前目标',self.finish)):
            b=Action(self.actions,title,command,160,key=='refresh');b.pack(side='left');self.buttons[key]=b
        self.scroll=ScrollPage(w);self.scroll.pack(fill='both',expand=True,padx=18,pady=(14,8));self.scroll.canvas.configure(bg=T.CARD);body=self.scroll.body;body.configure(bg=T.CARD)
        def label(text,size=10):
            l=Label(body,text=text,bg=T.CARD,fg=T.FG if size>10 else T.MUTED,font=(T.FONT,size),anchor='w',justify='left');l.pack(fill='x',padx=12,pady=6);l.bind('<Configure>',lambda e:l.configure(wraplength=max(80,e.width)));return l
        label('训练目标跟进',18);label('固定参考圈与区间；选择目标查看后续赛事，刷新保留当前选择。')
        self.selected=tk.StringVar(w);self.box=Select(body,textvariable=self.selected,width=24);self.box.pack(fill='x',padx=12,pady=8);self.box.bind('<<ComboboxSelected>>',self.analyse)
        self.context=label('');label('区间用时趋势',12)
        self.chart=ProgressChart(body,self.select_session,height=180);self.chart.empty_text='暂无后续赛事；有新记录后可刷新跟进';self.chart.pack(fill='x',padx=12,pady=8)
        self.table=SessionList(body,columns=tuple(k for k,_,_ in COLUMNS),height=5,selectmode='browse');self.table.pack(fill='x',padx=12,pady=8);self.table.viewport.bind('<MouseWheel>',self.table_wheel);self.table.bind('<<TreeviewSelect>>',self.detail)
        self.details=label('')
        w.protocol('WM_DELETE_WINDOW',w.destroy);w.bind('<Escape>',lambda _:(w.destroy(),'break')[1]);w.bind('<F5>',lambda _:(self.refresh(),'break')[1]);w.bind('<MouseWheel>',self.wheel);w.bind('<Destroy>',self.dispose,add='+');w.retranslate=self.translate
        self.translate();self.refresh()
    def alive(self):return not self.app.closing and bool(self.window.winfo_exists())
    def say(self,text,**values):self.notice=(text,values);self.status.set(tr(text).format(**values))
    def sync(self):
        idle=not self.loading and self.running is None and not self.finishing
        self.buttons['refresh'].configure(state='normal' if idle else 'disabled')
        self.buttons['finish'].configure(state='normal' if idle and self.selected.get() in self.goals else 'disabled')
        self.box.configure(state='disabled' if self.loading or self.finishing or not self.goals else 'readonly')
    def goal_label(self,goal):
        from track_names import display
        suffix=goal['id'][:8]
        if sum(key.startswith(suffix) for key in self.goals)>1:suffix=goal['id']
        return goal['created_utc'][:19].replace('T',' ')+' UTC · '+display(goal['entry']['track'])+' · '+goal['zone']['name']+' · '+suffix
    def row_key(self,entry):return entry['folder'],entry['observed_utc']
    def refresh(self):
        if self.loading or self.running is not None or self.finishing:return
        self.loading=True;self.feedback.busy('goals');self.say('正在读取训练目标…');self.sync();selected=self.selected.get();self.refresh_selection=self.row_key(self.rows[self.table.selection()[0]]) if self.table.selection() else None
        def done(values,error):
            if not self.alive():return
            self.loading=False;self.feedback.busy('goals',False)
            if error:self.say('跟进未更新，可重试：{error}',error=error);self.sync();return
            self.goals={g['id']:g for g in values};self.box.labels={key:self.goal_label(g) for key,g in self.goals.items()};self.box.configure(values=list(self.goals));self.selected.set(selected if selected in self.goals else next(iter(self.goals),''));self.context.configure(text=self.box.display(self.selected.get()));self.sync()
            if self.goals:self.analyse()
            else:self.clear();self.chart.empty_text='先在训练优先级报告里选择区间，设为本次训练目标。';self.chart.draw();self.say('先在训练优先级报告里选择区间，设为本次训练目标。')
        self.app.run_background(partial(goals,self.app.data_path),done)
    def clear(self):
        if self.result is not None:self.views[self.displayed]=(self.row_key(self.rows[self.table.selection()[0]]) if self.table.selection() else None,self.table.offset)
        self.result=None;self.rows={};self.table.replace([],());self.chart.set([]);self.details.configure(text='')
    def analyse(self,*_):
        if self.loading or self.finishing:return
        key=self.selected.get();goal=self.goals.get(key);self.context.configure(text=self.goal_label(goal) if goal else '')
        if not goal:return
        self.clear();self.chart.empty_text='正在评估目标之后的新赛事…';self.chart.draw();self.say('正在评估目标之后的新赛事…')
        if self.running is not None:self.pending=key;self.sync();return
        self.start(key)
    def start(self,key):
        goal=copy.deepcopy(self.goals[key]);self.running=key;self.feedback.busy('evaluate');self.sync()
        def done(value,error):
            if not self.alive():return
            self.running=None;self.feedback.busy('evaluate',False);pending=self.pending;self.pending=None
            if pending is not None and pending!=key and pending in self.goals:self.start(pending);return
            if self.selected.get()!=key:self.sync();return
            if error:self.say('跟进未更新，可重试：{error}',error=error)
            else:self.result=value;self.render();self.summary()
            self.sync()
        self.app.run_background(partial(evaluate,self.app.data_path,goal),done)
    def render(self):
        if self.result is None:return
        self.displayed=self.selected.get();view=(None,self.table.offset) if self.rows else self.views.get(self.displayed,(self.refresh_selection,0));keep=self.row_key(self.rows[self.table.selection()[0]]) if self.table.selection() else view[0];self.refresh_selection=None;self.chart.empty_text='暂无后续赛事；有新记录后可刷新跟进'
        values=self.result['sessions'];self.rows={str(i):e for i,e in enumerate(values)}
        chosen=next((key for key,e in self.rows.items() if self.row_key(e)==keep),None)
        if chosen is None and self.rows:chosen=next(reversed(self.rows))
        self.table.replace([(key,(e['observed_utc'][:19].replace('T',' '),number(e['median_loss_s'],'',3),number(e['gain_s'],'',3),number(e['std_s'],'',3),e['count'],tr('可比样本') if e['qualified'] else tr('样本不足或仅供探索'))) for key,e in self.rows.items()],(chosen,) if chosen else ());self.table.set_offset(view[1]);self.chart.set(values);self.detail()
    def summary(self):
        if self.result is None:return
        b=self.result['goal']['baseline'];self.say('基准典型损失 {loss} s · 样本圈数 {count} · 后续赛事 {sessions} · 冲突记录 {conflicts} · 读取异常 {errors}',loss=f"{b['median_loss_s']:.3f}",count=b['count'],sessions=len(self.result['sessions']),conflicts=self.result['conflicts'],errors=len(self.result['errors']))
    def detail(self,*_):
        chosen=next(iter(self.table.selection()),None);e=self.rows.get(chosen)
        self.details.configure(text='' if e is None else e['observed_utc'][:19].replace('T',' ')+' UTC · '+tr('区间用时趋势')+f" {e['time_s']:.3f} s · "+tr('正的提升值表示区间损失减少，不能归因于单一动作'))
    def select_session(self,entry):
        key=next((key for key,e in self.rows.items() if e is entry),None)
        if key is not None:self.table.selection_set((key,));self.table.yview('moveto',max(0,self.table.order.index(key)-1)/max(1,len(self.table.order)));self.detail()
    def finish(self):
        if self.loading or self.running is not None or self.finishing:return
        goal=self.goals.get(self.selected.get())
        if goal is None:return
        from control_confirm import ask
        if ask(self.window,'结束当前目标',self.goal_label(goal)+'\n\n'+tr('结束后不再跟进新赛事，已保存的目标与参考圈会保留。'),[('finish','结束当前目标'),('cancel','继续跟进')])!='finish':return
        self.finishing=True;self.say('正在结束训练目标…');self.feedback.busy('finish');self.sync()
        def done(value,error):
            if not self.alive():
                if error and not self.app.closing:self.app.status.set(tr('目标未结束，可重试：{error}').format(error=error))
                return
            self.finishing=False;self.feedback.busy('finish',False)
            if error:self.say('目标未结束，可重试：{error}',error=error);self.sync()
            else:self.refresh()
        self.app.run_background(partial(close,self.app.data_path,copy.deepcopy(goal)),done)
    def translate(self):
        self.window.title(tr('训练目标跟进'));self.box.labels={key:self.goal_label(g) for key,g in self.goals.items()};self.box.paint();self.context.configure(text=self.box.display(self.selected.get()))
        for key,title,width in COLUMNS:self.table.heading(key,text=tr(title));self.table.column(key,width=width,minwidth=75,stretch=True)
        self.render();self.chart.draw()
        for b in self.buttons.values():b.configure(width=max(px(b,120),b.font.measure(tr(b.label))+px(b,36)))
        self.actions.event_generate('<Configure>',width=self.actions.winfo_width());self.say(self.notice[0],**self.notice[1])
    def table_wheel(self,event):
        t=self.table
        if not event.state&1 and (t.limit()<=0 or event.delta>0 and t.offset<=0 or event.delta<0 and t.offset>=t.limit()):self.scroll.wheel(event.delta);return 'break'
        return t.wheel(event)
    def wheel(self,event):
        widget=event.widget
        while widget is not None and widget is not self.window:
            if widget in (self.table,self.box):return
            if widget is self.scroll:self.scroll.wheel(event.delta);return 'break'
            widget=getattr(widget,'master',None)
    def dispose(self,event):
        if event.widget is not self.window:return
        self.app.training_goal_window=None;self.pending=None;self.result=None
        for v in (self.selected,self.status):v.__del__();v._tk=None
