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
    w.field_widgets[key]=field
    if browse:Action(frame,'选择文件' if browse!='directory' else '选择目录',lambda:w.choose(key,browse),105).grid(row=0,column=2,padx=(px(frame,8),0))
    return field


def build(w,modes):
    window=w.window
    title=tk.Frame(window,bg=T.BG);title.pack(fill='x',padx=px(window,24),pady=(px(window,15),px(window,6)))
    Action(title,'最近提取结果',w.recent_results,170).place(relx=1,anchor='ne')
    w.heading_frame=title;w.heading_meta=note(title,'STINTRIX / VIDEO LAB',9,T.ACCENT,True)
    w.heading_title=note(title,'视频提取油刹曲线',21,T.FG,True)
    w.heading_hint=note(title,'跟着三步完成：选视频与赛道 → 圈段与 HUD 标定 → 检查并提取。所有处理都在本机。')
    footer=tk.Frame(window,bg=T.BG);footer.pack(side='bottom',fill='x',padx=px(window,22),pady=(px(window,5),px(window,12)))
    w.back=Action(footer,'上一步',w.previous_step,90);w.back.pack(side='left',padx=(0,px(window,8)))
    w.start=Action(footer,'下一步：圈段与标定',w.primary_action,220,True);w.start.pack(side='left',padx=(0,px(window,8)))
    w.stop=Action(footer,'取消任务',w.cancel_current,112);w.stop.configure(state='disabled');w.stop.pack(side='left',padx=(0,px(window,8)))
    w.open=Action(footer,'打开结果',w.open_result,120);w.open.configure(state='disabled');w.open.pack(side='left')
    Action(footer,'操作示意 / 帮助',w.show_help,155).pack(side='right')
    status_area=tk.Frame(window,bg=T.BG);status_area.pack(side='bottom',fill='x',padx=px(window,24),pady=(0,px(window,5)))
    w.feedback=StatusFeedback(status_area,w.status);w.feedback.pack(fill='x',pady=(px(window,7),0));w.feedback.label.configure(height=2)
    w.percent=Label(status_area,text='就绪',bg=T.BG,fg=T.MUTED,font=('Consolas',9),anchor='e');w.percent.pack(side='right')
    w.bar=TaskProgress(status_area);w.bar.pack(fill='x',pady=px(window,5))
    w.tabs=Steps(window);w.tabs.pack(fill='both',expand=True,padx=px(window,22),pady=(px(window,3),px(window,5)))
    setup_page=ScrollPage(w.tabs);advanced_page=ScrollPage(w.tabs);w.calibration=tk.Frame(w.tabs,bg=T.BG)
    w.scroll_pages=[setup_page,advanced_page]
    w.tabs.add(setup_page,text='01 · 视频与赛道');w.tabs.add(w.calibration,text='02 · 圈段与 HUD 标定');w.tabs.add(advanced_page,text='03 · 检查并提取')
    w.tabs.bind('<<NotebookTabChanged>>',lambda _:w.pause_hidden_scroll())
    window.bind('<MouseWheel>',lambda e:w.wheel(e),add='+')
    window.bind('<Configure>',w.responsive,add='+')
    setup=setup_page.body;advanced=advanced_page.body
    _,body=section(setup,'视频与输入方式','选择本地单圈视频；画面须保持原速、无剪辑，HUD 的位置与缩放固定。')
    entry(w,body,'视频文件','video',browse='video')
    help_label=Label(body,textvariable=w.guide_detail,bg=T.CARD,fg=T.ACCENT,font=(T.FONT,10),anchor='w',justify='left');help_label.pack(fill='x',pady=5)
    help_label.bind('<Configure>',lambda e:help_label.configure(wraplength=max(120,e.width)))
    Label(body,textvariable=w.media_hint,bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),wraplength=840,anchor='w',justify='left').pack(fill='x',pady=px(body,6))
    r=row(body);Label(r,text='输入条件',bg=T.CARD,fg=T.MUTED,width=23,anchor='w',font=(T.FONT,10)).pack(side='left',padx=(0,px(r,10)))
    w.modebox=Select(r,textvariable=w.mode,values=list(modes),state='readonly');w.modebox.pack(side='left',fill='x',expand=True);w.modebox.bind('<<ComboboxSelected>>',lambda _:w.mode_changed())
    note(body,'第一次使用保持“普通 POV”即可。距离 OCR 需要专用距离和计时 HUD；遥测同步需要视频中同一圈的原生记录。')
    _,body=section(setup,'赛道与布局','优先从已有记录选择布局；列表为空时手动填写。名称需与游戏中的赛道和布局一致，长度单位为米。')
    w.identities={};w.identity=tk.StringVar(window)
    w.identitybox=Select(body,textvariable=w.identity,state='readonly');w.identitybox.pack(fill='x',pady=px(body,4));w.identitybox.bind('<<ComboboxSelected>>',lambda _:w.use_identity())
    Action(body,'手动填写 / 修正布局',w.toggle_manual,200).pack(anchor='w',pady=px(body,5))
    w.manual_body=tk.Frame(body,bg=T.CARD)
    for title,key in [('赛道原始名称','track'),('具体布局原始名','layout'),('布局长度 / m','length')]:entry(w,w.manual_body,title,key)
    _,body=section(setup,'解码工具（通常无需设置）','默认查找本机 FFmpeg；找不到工具时再展开填写。')
    Action(body,'展开工具路径设置',w.toggle_tools,190).pack(anchor='w')
    w.tools_body=tk.Frame(body,bg=T.CARD)
    entry(w,w.tools_body,'FFmpeg 工具文件夹','ffmpeg',browse='directory')
    calibration(w)
    _,body=section(advanced,'提取前检查','有未完成项时，下方主按钮会带你回到对应位置；已有标定不会被清空。')
    for var in w.review_values:
        label=Label(body,textvariable=var,bg=T.CARD,fg=T.FG,font=(T.FONT,10),anchor='w',justify='left');label.pack(fill='x',pady=7)
        label.bind('<Configure>',lambda e,l=label:l.configure(wraplength=max(120,e.width)))
    Action(advanced,'同步、地标与提取选项（可选）',w.toggle_advanced,300).pack(anchor='w',pady=(0,10))
    w.advanced_body=tk.Frame(advanced,bg=T.BG);advanced_layout(w,w.advanced_body)
    w.result_card,body=section(advanced,'完成后，先检查报告')
    label=Label(body,textvariable=w.result_note,bg=T.CARD,fg=T.MUTED,font=(T.FONT,10),anchor='w',justify='left');label.pack(fill='x')
    label.bind('<Configure>',lambda e:label.configure(wraplength=max(120,e.width)))
    r=row(body);w.compare_button=Action(r,'比较提取结果',w.compare,160);w.compare_button.pack(side='left',padx=(0,8))
    w.history_button=Action(r,'对比历史圈速',w.compare_history,160);w.history_button.pack(side='left')
    Action(body,'最近提取结果',w.recent_results,170).pack(anchor='w',pady=(8,0))
    note(body,'比较提取结果：依次选择 A、B 两个 curve.json。对比历史圈速：选择已有完整圈记录，按报告说明判断可比较范围。')


def calibration(w):
    parent=w.calibration
    card=tk.Frame(parent,bg=T.CARD,highlightthickness=1,highlightbackground=T.EDGE);card.pack(fill='x',padx=px(parent,2),pady=(0,px(parent,10)))
    body=tk.Frame(card,bg=T.CARD);body.pack(fill='x',padx=px(parent,12),pady=px(parent,10))
    choices=[('油门圆弧','throttle'),('刹车圆弧','brake'),('固定文字','anchor'),('距离读数','distance_box'),('圈内计时','timer_box')]
    w.targets=ChoiceStrip(body,w.target,choices,w.target_changed);w.targets.pack(fill='x')
    w.hint=w.guide_detail
    Label(body,textvariable=w.guide_heading,bg=T.CARD,fg=T.FG,font=(T.FONT,11,'bold'),anchor='w').pack(fill='x',pady=(5,0))
    hint=Label(body,textvariable=w.hint,bg=T.CARD,fg=T.ACCENT,font=(T.FONT,9),justify='left',anchor='w',height=2);hint.pack(fill='x',pady=px(body,3));hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(120,e.width)))
    tools=tk.Frame(body,bg=T.CARD);tools.pack(fill='x')
    w.calibration_options=tk.Frame(body,bg=T.CARD)
    r=tk.Frame(w.calibration_options,bg=T.CARD);r.pack(side='left')
    for name,title in [('throttle','油门顺时针'),('brake','刹车顺时针')]:
        cell=tk.Frame(r,bg=T.CARD,width=px(r,168),height=px(r,48));cell.pack(side='left',padx=(0,px(r,10)));cell.pack_propagate(False)
        Switch(cell,title,w.clockwise[name],w.redraw).pack(fill='x')
    controls=tk.Frame(tools,bg=T.CARD)
    Label(w.calibration_options,text='弧宽 / 原视频 px',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9)).pack(side='left',padx=(0,px(body,8)))
    Field(w.calibration_options,textvariable=w.thickness,width=4).pack(side='left',padx=(0,px(body,12)))
    Label(controls,text='滚轮缩放',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9)).pack(side='left',padx=(0,px(body,8)))
    zoom=Select(controls,textvariable=w.zoom,values=[.25,.5,.75,1,1.5,2,3,4,6,8,12],width=9);zoom.pack(side='left');zoom.bind('<<ComboboxSelected>>',lambda _:w.manual_zoom())
    Action(controls,'适合视窗',w.fit_preview,105).pack(side='left',padx=(px(body,5),0))
    actions=tk.Frame(tools,bg=T.CARD)
    Action(actions,'撤销一步',w.undo_calibration,95).pack(side='left');Action(actions,'重做本项',w.clear_target,95).pack(side='left',padx=px(body,5));Action(actions,'检查标定',w.check_calibration,95).pack(side='left')
    Action(actions,'方向与弧宽',w.toggle_calibration_options,120).pack(side='left',padx=px(body,5))
    from control_video_close import save as save_draft
    Action(actions,'保存标定草稿',lambda:save_draft(w),130).pack(side='left')
    def arrange(event):
        wide=event.width>=controls.winfo_reqwidth()+actions.winfo_reqwidth()+px(tools,24)
        for group in (controls,actions):group.grid_forget()
        controls.grid(row=0,column=0,sticky='w')
        actions.grid(row=0 if wide else 1,column=1 if wide else 0,sticky='w')
        tools.columnconfigure(1,weight=1)
    tools.bind('<Configure>',arrange)
    timeline=tk.Frame(parent,bg=T.CARD);timeline.pack(fill='x',padx=px(parent,2),pady=(0,px(parent,6)))
    Label(timeline,textvariable=w.seek_text,bg=T.CARD,fg=T.MUTED,font=('Consolas',9),width=11).pack(side='left',padx=px(parent,6))
    w.seek_scale=tk.Scale(timeline,from_=0,to=1,resolution=.001,orient='horizontal',showvalue=False,variable=w.seek,
        command=w.seek_changed,bg=T.CARD,fg=T.FG,troughcolor=T.FIELD,highlightthickness=0,activebackground=T.ACCENT,relief='flat',sliderlength=18,width=10)
    w.seek_scale.pack(side='left',fill='x',expand=True)
    w.seek_scale.bind('<ButtonRelease-1>',lambda _:w.request_frame());w.seek_scale.bind('<KeyRelease>',lambda _:w.request_frame())
    for text,delta in [('−0.02s',-.02),('+0.02s',.02)]:
        Action(timeline,text,lambda d=delta:w.nudge_preview(d),84).pack(side='left',padx=2)
    Action(timeline,'设为圈起点',lambda:w.mark_range('start'),115).pack(side='left',padx=px(parent,4))
    Action(timeline,'设为圈终点',lambda:w.mark_range('end'),115).pack(side='left',padx=(0,px(parent,6)))
    range_row=tk.Frame(parent,bg=T.BG);range_row.pack(fill='x',pady=(0,4))
    Label(range_row,textvariable=w.range_summary,bg=T.BG,fg=T.MUTED,font=('Consolas',9)).pack(side='left',padx=4)
    cell=tk.Frame(range_row,bg=T.BG,width=px(parent,265),height=px(parent,42));cell.pack(side='right');cell.pack_propagate(False)
    w.range_check=Switch(cell,'我已核对完整一圈',w.range_confirmed,w.queue_guidance);w.range_check.pack(fill='x')
    precise=tk.Frame(w.calibration_options,bg=T.CARD)
    def toggle_times():
        if precise.winfo_manager():precise.pack_forget()
        else:precise.pack(fill='x',side='bottom')
    options=tk.Frame(w.calibration_options,bg=T.CARD);options.pack(fill='x',side='bottom')
    Action(options,'精确输入时间',toggle_times,145).pack(side='left',padx=(0,6))
    Action(options,'读取当前时间帧',w.load_preview,160).pack(side='left',padx=(0,6))
    Action(options,'加载已有标定',w.load_calibration,150).pack(side='left')
    for title,key,value in [('圈起点 / 秒或分:秒','start','0'),('圈终点 / 秒或分:秒','end',''),('预览时间（如 1:23.450）','sample','0')]:entry(w,precise,title,key,value)
    w.precise_body=precise
    def open_times():
        if not w.calibration_options.winfo_manager():w.toggle_calibration_options()
        if not precise.winfo_manager():toggle_times()
    Action(range_row,'精确时间 / 旧标定',open_times,175).pack(side='left',padx=8)
    fine=tk.Frame(precise,bg=T.CARD);fine.pack(fill='x',pady=(0,4))
    for text,delta in [('−1 秒',-1),('−0.02 秒',-.02),('+0.02 秒',.02),('+1 秒',1)]:
        Action(fine,text,lambda d=delta:w.nudge_preview(d),92).pack(side='left',padx=(0,4))
    note(fine,'滚轮缩放 · 右键 / 中键拖动 · Shift + 滚轮横移').pack(side='left',padx=6)
    holder=tk.Frame(parent,bg=T.EDGE);holder.pack(fill='both',expand=True,padx=px(parent,2))
    w.canvas=tk.Canvas(holder,bg='#111111',highlightthickness=0,width=1,height=1,cursor='crosshair')
    xs=ttk.Scrollbar(holder,orient='horizontal',command=lambda *a:w.scroll_preview('x',*a),style='Lab.Horizontal.TScrollbar');ys=ttk.Scrollbar(holder,orient='vertical',command=lambda *a:w.scroll_preview('y',*a),style='Lab.Vertical.TScrollbar')
    w.canvas.configure(xscrollcommand=xs.set,yscrollcommand=ys.set);w.canvas.grid(row=0,column=0,sticky='nsew');xs.grid(row=1,column=0,sticky='ew');ys.grid(row=0,column=1,sticky='ns')
    holder.rowconfigure(0,weight=1);holder.columnconfigure(0,weight=1)
    w.canvas.bind('<ButtonPress-1>',w.press);w.canvas.bind('<ButtonRelease-1>',w.release);w.canvas.bind('<B1-Motion>',w.dragging)
    w.canvas.bind('<Configure>',w.preview_resized)
    w.install_viewport()
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
    Switch(body,'另存 120 Hz 平滑曲线（插值估算）',w.smooth_120hz,lambda:None).pack(fill='x',pady=5)
    note(body,'仅补齐已识别点之间的油刹变化；HUD 缺失留空，不增加原始精度。打开 report_120hz.html 切换查看。')
    note(body,'保留原视频与赛事数据；关闭窗口会取消当前任务。CSV / JSON / 网页与标定文件独立保存。')
