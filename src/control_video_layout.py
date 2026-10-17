"""Video wizard layout; task logic and extraction remain in their own modules."""
import tkinter as tk
from tkinter import ttk
from control_theme import T
from control_widgets import GlassCard,Switch,px
from control_fields import Field,Select
from control_feedback import StatusFeedback
from control_video_widgets import Action,Steps,ChoiceStrip,TaskProgress,ScrollPage
from i18n import Label,tr


def note(parent,text,size=9,color=None,bold=False):
    label=Label(parent,text=text,bg=parent.cget('bg'),fg=color or T.MUTED,font=(T.FONT,size,'bold' if bold else 'normal'),justify='left',anchor='w')
    label.pack(fill='x',pady=(px(parent,3),px(parent,7)))
    label.bind('<Configure>',lambda e:label.configure(wraplength=max(120,e.width)))
    return label


def section(parent,title,subtitle=''):
    card=GlassCard(parent);card.pack(fill='x',pady=(0,px(parent,12)))
    note(card.body,title,12,T.FG,True)
    if subtitle:note(card.body,subtitle)
    return card,card.body


def row(parent):
    frame=tk.Frame(parent,bg=parent.cget('bg'));frame.pack(fill='x',pady=px(parent,3));return frame


def entry(w,parent,title,key,default='',browse=None):
    frame=row(parent);frame.columnconfigure(1,weight=1)
    Label(frame,text=title,bg=frame.cget('bg'),fg=T.MUTED,font=(T.FONT,10),anchor='w',width=23).grid(row=0,column=0,sticky='w',padx=(0,px(frame,10)))
    variable=tk.StringVar(w.window,value=default);w.fields[key]=variable
    field=Field(frame,textvariable=variable);field.grid(row=0,column=1,sticky='ew')
    if browse:Action(frame,'选择文件' if browse!='directory' else '选择目录',lambda:w.choose(key,browse),105).grid(row=0,column=2,padx=(px(frame,8),0))
    return field


def build(w,modes):
    window=w.window
    title=tk.Frame(window,bg=T.BG);title.pack(fill='x',padx=px(window,24),pady=(px(window,15),px(window,6)))
    w.heading_frame=title;w.heading_meta=note(title,'STINTRIX / VIDEO LAB',9,T.ACCENT,True)
    w.heading_title=note(title,'视频提取油刹曲线',21,T.FG,True)
    w.heading_hint=note(title,'选择一圈，标定输入，让驾驶过程变得清晰。')
    footer=tk.Frame(window,bg=T.BG);footer.pack(side='bottom',fill='x',padx=px(window,22),pady=(px(window,5),px(window,12)))
    w.start=Action(footer,'开始提取',w.run,145,True);w.start.pack(side='left',padx=(0,px(window,8)))
    w.stop=Action(footer,'取消任务',w.cancel_current,112);w.stop.configure(state='disabled');w.stop.pack(side='left',padx=(0,px(window,8)))
    w.compare_button=Action(footer,'比较提取结果',w.compare,160);w.compare_button.pack(side='left',padx=(0,px(window,8)))
    w.history_button=Action(footer,'对比历史圈速',w.compare_history,150);w.history_button.pack(side='left',padx=(0,px(window,8)))
    w.open=Action(footer,'打开结果',w.open_result,120);w.open.configure(state='disabled');w.open.pack(side='left')
    status_area=tk.Frame(window,bg=T.BG);status_area.pack(side='bottom',fill='x',padx=px(window,24),pady=(0,px(window,5)))
    w.feedback=StatusFeedback(status_area,w.status);w.feedback.pack(fill='x',pady=(px(window,7),0));w.feedback.label.configure(height=2)
    w.percent=Label(status_area,text='就绪',bg=T.BG,fg=T.MUTED,font=('Consolas',9),anchor='e');w.percent.pack(side='right')
    w.bar=TaskProgress(status_area);w.bar.pack(fill='x',pady=px(window,5))
    w.tabs=Steps(window);w.tabs.pack(fill='both',expand=True,padx=px(window,22),pady=(px(window,3),px(window,5)))
    setup_page=ScrollPage(w.tabs);advanced_page=ScrollPage(w.tabs);w.calibration=tk.Frame(w.tabs,bg=T.BG)
    w.scroll_pages=[setup_page,advanced_page]
    w.tabs.add(setup_page,text='01 · 视频与赛道');w.tabs.add(w.calibration,text='02 · 圈段与 HUD 标定');w.tabs.add(advanced_page,text='03 · 高级设置（可选）')
    w.tabs.bind('<<NotebookTabChanged>>',lambda _:w.pause_hidden_scroll())
    window.bind('<MouseWheel>',lambda e:w.wheel(e),add='+')
    window.bind('<Configure>',w.responsive,add='+')
    setup=setup_page.body;advanced=advanced_page.body
    _,body=section(setup,'视频与输入方式','选择本地单圈视频；画面须保持原速、无剪辑，HUD 的位置与缩放固定。')
    entry(w,body,'视频文件','video',browse='video')
    Label(body,textvariable=w.media_hint,bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),wraplength=840,anchor='w',justify='left').pack(fill='x',pady=px(body,6))
    r=row(body);Label(r,text='输入条件',bg=T.CARD,fg=T.MUTED,width=23,anchor='w',font=(T.FONT,10)).pack(side='left',padx=(0,px(r,10)))
    w.modebox=Select(r,textvariable=w.mode,values=list(modes),state='readonly');w.modebox.pack(side='left',fill='x',expand=True);w.modebox.bind('<<ComboboxSelected>>',lambda _:w.mode_changed())
    _,body=section(setup,'单圈时间范围','选择文件后自动填入完整视频时长；也可在第 2 步拖动预览条，直接标记圈起点和终点。')
    for title,key,value in [('开始时间','start','0'),('结束时间','end',''),('标定帧时间','sample','0')]:entry(w,body,title,key,value)
    r=row(body);Action(r,'预览 / 调整圈段 →',w.next_preview,190,True).pack(side='left',padx=(0,px(r,10)));Action(r,'加载已有标定',w.load_calibration,160).pack(side='left')
    _,body=section(setup,'赛道与布局','优先从已有记录选择布局；赛道原始名称与长度将一并带入。')
    w.identities={};w.identity=tk.StringVar(window)
    w.identitybox=Select(body,textvariable=w.identity,state='readonly');w.identitybox.pack(fill='x',pady=px(body,4));w.identitybox.bind('<<ComboboxSelected>>',lambda _:w.use_identity())
    Action(body,'手动填写 / 修正布局',w.toggle_manual,200).pack(anchor='w',pady=px(body,5))
    w.manual_body=tk.Frame(body,bg=T.CARD)
    for title,key in [('赛道原始名称','track'),('具体布局原始名','layout'),('布局长度 / m','length')]:entry(w,w.manual_body,title,key)
    _,body=section(setup,'解码工具（通常无需设置）','默认查找本机 FFmpeg；找不到工具时再展开填写。')
    Action(body,'展开工具路径设置',w.toggle_tools,190).pack(anchor='w')
    w.tools_body=tk.Frame(body,bg=T.CARD)
    entry(w,w.tools_body,'FFmpeg 工具文件夹','ffmpeg',browse='directory')
    calibration(w);advanced_layout(w,advanced)


def calibration(w):
    parent=w.calibration
    card=tk.Frame(parent,bg=T.CARD,highlightthickness=1,highlightbackground=T.EDGE);card.pack(fill='x',padx=px(parent,2),pady=(0,px(parent,10)))
    body=tk.Frame(card,bg=T.CARD);body.pack(fill='x',padx=px(parent,12),pady=px(parent,10))
    choices=[('油门圆弧','throttle'),('刹车圆弧','brake'),('固定文字','anchor'),('距离读数','distance_box'),('圈内计时','timer_box')]
    w.targets=ChoiceStrip(body,w.target,choices,w.target_changed);w.targets.pack(fill='x')
    w.hint=tk.StringVar(w.window,value='读取标定帧后开始操作。不要用视频中观察到的最大刹车代替真正的 100%。')
    hint=Label(body,textvariable=w.hint,bg=T.CARD,fg=T.ACCENT,font=(T.FONT,9),justify='left',anchor='w',height=2);hint.pack(fill='x',pady=px(body,3));hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(120,e.width)))
    tools=tk.Frame(body,bg=T.CARD);tools.pack(fill='x')
    r=tk.Frame(tools,bg=T.CARD)
    for name,title in [('throttle','油门顺时针'),('brake','刹车顺时针')]:
        cell=tk.Frame(r,bg=T.CARD,width=px(r,168),height=px(r,48));cell.pack(side='left',padx=(0,px(r,10)));cell.pack_propagate(False)
        Switch(cell,title,w.clockwise[name],w.redraw).pack(fill='x')
    controls=tk.Frame(tools,bg=T.CARD)
    Label(controls,text='弧宽 / px',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9)).pack(side='left',padx=(0,px(body,8)))
    Field(controls,textvariable=w.thickness,width=4).pack(side='left',padx=(0,px(body,12)))
    Label(controls,text='放大',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9)).pack(side='left',padx=(0,px(body,8)))
    zoom=Select(controls,textvariable=w.zoom,values=[.5,.75,1,1.5,2,3],width=9);zoom.pack(side='left');zoom.bind('<<ComboboxSelected>>',lambda _:w.redraw())
    Action(controls,'适合视窗',w.fit_preview,105).pack(side='left',padx=(px(body,5),0))
    actions=tk.Frame(tools,bg=T.CARD)
    Action(actions,'撤销一步',w.undo_calibration,100).pack(side='left');Action(actions,'清除标定',w.clear_target,105).pack(side='left',padx=px(body,5));Action(actions,'检查标定',w.check_calibration,105).pack(side='left')
    def arrange(event):
        wide=event.width>=px(tools,1000)
        for group in (r,controls,actions):group.grid_forget()
        r.grid(row=0,column=0,columnspan=1 if wide else 2,sticky='w')
        controls.grid(row=0 if wide else 1,column=1 if wide else 0,sticky='w')
        actions.grid(row=0 if wide else 1,column=2 if wide else 1,sticky='e')
        tools.columnconfigure(1,weight=1)
    tools.bind('<Configure>',arrange)
    timeline=tk.Frame(parent,bg=T.CARD);timeline.pack(fill='x',padx=px(parent,2),pady=(0,px(parent,6)))
    Label(timeline,textvariable=w.seek_text,bg=T.CARD,fg=T.MUTED,font=('Consolas',9),width=11).pack(side='left',padx=px(parent,6))
    w.seek_scale=tk.Scale(timeline,from_=0,to=1,resolution=.001,orient='horizontal',showvalue=False,variable=w.seek,
        command=w.seek_changed,bg=T.CARD,fg=T.FG,troughcolor=T.FIELD,highlightthickness=0,activebackground=T.ACCENT,relief='flat',sliderlength=18,width=10)
    w.seek_scale.pack(side='left',fill='x',expand=True)
    w.seek_scale.bind('<ButtonRelease-1>',lambda _:w.request_frame());w.seek_scale.bind('<KeyRelease>',lambda _:w.request_frame())
    Action(timeline,'设为圈起点',lambda:w.mark_range('start'),115).pack(side='left',padx=px(parent,4))
    Action(timeline,'设为圈终点',lambda:w.mark_range('end'),115).pack(side='left',padx=(0,px(parent,6)))
    holder=tk.Frame(parent,bg=T.EDGE);holder.pack(fill='both',expand=True,padx=px(parent,2))
    w.canvas=tk.Canvas(holder,bg='#111111',highlightthickness=0,width=1,height=1,cursor='crosshair')
    xs=ttk.Scrollbar(holder,orient='horizontal',command=w.canvas.xview,style='Lab.Horizontal.TScrollbar');ys=ttk.Scrollbar(holder,orient='vertical',command=w.canvas.yview,style='Lab.Vertical.TScrollbar')
    w.canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set);w.canvas.grid(row=0,column=0,sticky='nsew');xs.grid(row=1,column=0,sticky='ew');ys.grid(row=0,column=1,sticky='ns')
    holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
    w.canvas.bind('<ButtonPress-1>',w.press);w.canvas.bind('<ButtonRelease-1>',w.release);w.canvas.bind('<B1-Motion>',w.dragging)
    w.canvas.bind('<Configure>',lambda _:w.empty_preview())
    w.geometry_label=note(parent,'尚未标定；读取视频后，这里会显示标定状态。')


def editor(parent,title,subtitle,height):
    card,body=section(parent,title,subtitle)
    area=tk.Text(body,height=height,bg=T.FIELD,fg=T.FG,insertbackground=T.FG,relief='flat',borderwidth=0,
                 padx=px(body,12),pady=px(body,10),highlightthickness=1,highlightbackground=T.EDGE,highlightcolor=T.ACCENT,font=('Consolas',10),undo=True)
    area.pack(fill='x',pady=px(body,3));return card,body,area


def advanced_layout(w,parent):
    _,body=section(parent,'按输入条件准备同步信息')
    w.mode_hint=note(body,'',10,T.FG)
    w.telemetry_card,body,w.sync=editor(parent,'同圈遥测与同步点','每行：视频秒数 = 遥测圈内秒数。至少两点，覆盖 80% 以上圈时；建议三个独立事件。',3)
    entry(w,body,'同圈遥测 .lap.json','telemetry',browse='telemetry')
    w.landmark_card,body,w.marks=editor(parent,'固定地标','每行：名称 = 视频时间，例如 T1入口线 = 0:23.450。比较时匹配同名地标。',4)
    note(body,'使用相同物理标线与过线判据；不要用各自的刹车点替代固定地标。')
    w.options_card,body=section(parent,'提取选项','结果只保存本机，不计入原生最快圈、领奖台或训练结论。')
    r=row(body);Label(r,text='提取上限 / Hz',bg=T.CARD,fg=T.MUTED,font=(T.FONT,10)).pack(side='left',padx=(0,px(r,12)))
    Select(r,textvariable=w.hz,values=[5,10,20,30],width=7).pack(side='left')
    w.distance_options=tk.Frame(r,bg=T.CARD);w.distance_options.pack(side='left',padx=px(r,24))
    Label(w.distance_options,text='距离单位',bg=T.CARD,fg=T.MUTED,font=(T.FONT,10)).pack(side='left',padx=(0,px(r,12)))
    Select(w.distance_options,textvariable=w.unit,values=['m','km'],width=6).pack(side='left')
    note(body,'保留原视频与赛事数据；关闭窗口会取消当前任务。CSV / JSON / 网页与标定文件独立保存。')
