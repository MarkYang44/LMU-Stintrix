"""Follow a chosen zone across future sessions against one frozen reference."""
import tkinter as tk
from control_theme import T
from control_fields import Select
from control_list import SessionList
from control_history_chart import ProgressChart
from record_presentation import number
from training_goals import goals,evaluate,close
from i18n import tr

def show(app):
    window=tk.Toplevel(app.root);window.title(tr('训练目标跟进'));window.geometry('1120x780');window.configure(bg=T.BG)
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=(0,18))
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    app.label(body,'训练目标跟进',18,T.FG,True).pack(anchor='w',pady=8)
    selected=tk.StringVar(window);box=Select(body,textvariable=selected,width=60);box.pack(fill='x',pady=8)
    message=tk.StringVar(window);label=app.label(body,message,10);label.pack(fill='x',pady=6);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    chart=ProgressChart(body,lambda e:None,height=190);chart.pack(fill='x',pady=8)
    table=SessionList(body,columns=('date','loss','gain','std','count','quality'),height=5)
    for k,title,w in (('date','时间（UTC）',180),('loss','区间典型损失 / s',160),('gain','相比基准提升 / s',170),('std','波动 / s',110),('count','有效样本',110),('quality','样本与条件',160)):
        table.heading(k,text=title);table.column(k,width=w,minwidth=70,stretch=True)
    table.pack(fill='both',expand=True,pady=8);state={'goals':{},'request':0}
    def analyse(*_):
        goal=state['goals'].get(selected.get());state['request']+=1;request=state['request']
        if not goal:return
        message.set(tr('正在评估目标之后的新赛事…'))
        def done(value,error):
            if not window.winfo_exists() or request!=state['request']:return
            if error:message.set(error);return
            values=value['sessions'];chart.set(values);table.replace([(str(i),(e['observed_utc'][:19].replace('T',' '),number(e['median_loss_s'],'',3),number(e['gain_s'],'',3),number(e['std_s'],'',3),e['count'],tr('可比样本') if e['qualified'] else tr('样本不足或仅供探索'))) for i,e in enumerate(values)],())
            b=goal['baseline'];message.set(tr('固定参考圈与区间，基准典型损失')+f" {b['median_loss_s']:.3f} s / "+tr('样本圈数')+f" {b['count']} · "+(tr('尚无目标建立后的可用赛事') if not values else tr('正的提升值表示区间损失减少，不能归因于单一动作'))+f" / {tr('冲突记录')} {value['conflicts']}")
        app.run_background(lambda:evaluate(app.data_path,goal),done)
    def refresh():
        state['request']+=1;request=state['request'];message.set(tr('正在读取训练目标…'))
        def done(values,error):
            if not window.winfo_exists() or request!=state['request']:return
            if error:message.set(error);return
            state['goals']={v['created_utc'][:19]+' · '+v['entry']['track']+' · '+v['zone']['name']+' · '+v['id'][:6]:v for v in values};box.configure(values=list(state['goals']));selected.set(next(iter(state['goals']),''));table.replace([],());chart.set([])
            if values:analyse()
            else:message.set(tr('先在训练优先级报告里选择区间，设为本次训练目标。'))
        app.run_background(lambda:goals(app.data_path),done)
    def finish():
        goal=state['goals'].get(selected.get())
        if goal:app.run_background(lambda:close(app.data_path,goal),lambda value,error:message.set(error) if error else refresh() if window.winfo_exists() else None)
    box.bind('<<ComboboxSelected>>',analyse);actions=app.row(footer);app.button(actions,'刷新跟进',refresh,True,140);app.button(actions,'结束当前目标',finish,False,150)
    refresh();return window
