"""Native selector for comparing a video result with an existing local lap."""
from pathlib import Path
import os,threading,tkinter as tk
from tkinter import filedialog
from control_theme import T
from control_fields import Select
from control_widgets import Switch,px
from control_video_widgets import Action,ScrollPage
from control_video_layout import note,section
from control_feedback import StatusFeedback
from management import panel
from video_signal import clock
from i18n import tr
from control_confirm import ask,register


def show(app,root,video_path=None):
    old=getattr(app,'video_history_window',None)
    if old is not None and old.winfo_exists():
        old.deiconify();old.lift()
        if video_path is None or Path(video_path).resolve()==old.history_path:return old
        if old.history_state['busy']:
            old.history_message('当前对比正在处理，请完成后再切换视频结果。');return old
        if old.history_dirty() and ask(old,'切换视频结果','切换会放弃尚未生成的对比设置。已生成的报告保留。',[('discard','放弃设置并切换'),('cancel','继续当前对比')])!='discard':return old
        old.destroy()
    if video_path is None:
        video_path=filedialog.askopenfilename(parent=app.root,title=tr('选择视频提取结果'),filetypes=[(tr('视频结果'),'curve.json')])
        if not video_path:return
    window=panel(app,'Stintrix · 视频与历史单圈对比',1030,760);window.minsize(940,700);app.video_history_window=window
    root=Path(root);video_path=Path(video_path).resolve();window.history_path=video_path
    state=dict(video=None,items={},busy=True,result=None,cancel=threading.Event(),baseline=None);window.history_state=state
    footer=tk.Frame(window,bg=T.BG);footer.pack(side='bottom',fill='x',padx=px(window,24),pady=px(window,15))
    page=ScrollPage(window);page.pack(fill='both',expand=True,padx=px(window,24),pady=px(window,16));body=page.body
    window.bind('<MouseWheel>',lambda e:page.wheel(e.delta),add='+')
    note(body,'视频与历史单圈',20,T.FG,True)
    note(body,'A 为视频估算，B 为已验证历史圈。按圈起点叠加真实时间，不拉伸圈时。')
    source_label=note(body,tr('当前视频结果：{name}').format(name=video_path.parent.name),10,T.ACCENT)
    _,card=section(body,'选择历史圈速','读取同一赛道已有的最快圈和已导出完整圈；不会扫描全部赛事采样。')
    selected=tk.StringVar(window);box=Select(card,textvariable=selected,values=[],state='disabled');box.pack(fill='x',pady=px(window,5))
    identity_label=note(card,'正在读取视频与历史圈身份…')
    channels={'游戏过滤后输入':'filtered','原始输入':'raw'};channel=tk.StringVar(window,value=next(iter(channels)))
    select=Select(card,textvariable=channel,values=list(channels),state='readonly');select.pack(fill='x',pady=px(window,5))
    binding=tk.BooleanVar(window,value=False)
    line=tk.Frame(card,bg=T.CARD);line.pack(fill='x',pady=px(window,6))
    toggle=Switch(line,'',binding,lambda:None);toggle.configure(width=px(window,70));toggle.pack(side='left')
    note(line,'确认视频采用所选历史布局；只关联本次对比标签，原视频结果不变。').pack_configure(padx=px(window,10))
    _,markcard=section(body,'固定地标（可选）','历史圈填写“视频中已有地标名 = 历史圈内时间”。仅有时间轴也能叠加曲线；分段耗时需要两个以上同名地标。')
    marks=tk.Text(markcard,height=3,bg=T.FIELD,fg=T.FG,insertbackground=T.FG,relief='flat',font=(T.FONT,10));marks.pack(fill='x')
    status=tk.StringVar(window,value=tr('正在加载…'));window.history_status=status;feedback=StatusFeedback(body,status);feedback.pack(fill='x',pady=px(window,10));feedback.busy('load')
    state['message']=('正在加载…',{})
    def message(text,**values):
        state['message']=(text,values);status.set(tr(text).format(**values) if values else tr(text))
    window.history_message=message
    def snapshot():return (selected.get(),channel.get(),binding.get(),marks.get('1.0','end-1c'))
    def dirty():return state['baseline'] is not None and snapshot()!=state['baseline']
    window.history_dirty=dirty
    def close(after=None,exiting=False):
        if dirty() and ask(window,'有未生成的对比设置','关闭会放弃尚未生成的对比设置。已生成的报告保留。',[('discard','放弃设置并关闭'),('cancel','继续编辑')])!='discard':return
        window.destroy()
        if after:after()
    window.protocol('WM_DELETE_WINDOW',close);window.bind('<Escape>',lambda _:close());register(app,window,close)
    def alive():return not app.closing and window.winfo_exists()
    def identity_text():
        item=state['items'].get(selected.get())
        if item:
            ident=item['identity'];exact=item['exact']
            identity_label.configure(text=f"{ident['track']} / {ident['track_layout']} · {ident['length_m']:.3f} m\n"+
                tr('布局身份匹配。' if exact else '视频标注与历史布局不同；请核对实际布局，再勾选确认关联。'))
    def changed(*_):binding.set(False);identity_text()
    box.bind('<<ComboboxSelected>>',changed)
    def item_label(item,index):
        lap=tr('第 {number} 圈').format(number=item['number'])
        return f"{str(item['date'])[:19]} · {item['vehicle']} · {lap} · {item['time_s']:.3f} s · {item['identity']['track_layout']} / {item['identity']['length_m']:.1f} m [{index}]"
    def add(item):
        label=item_label(item,len(state['items'])+1);state['items'][label]=item;return label
    def refresh():
        box.labels={label:item_label(item,i) for i,(label,item) in enumerate(state['items'].items(),1)}
        box.configure(values=list(state['items']),state='readonly' if not state['busy'] else 'disabled')
        start.configure(state='normal' if state['items'] and not state['busy'] else 'disabled')
        browse.configure(state='normal' if not state['busy'] else 'disabled')
    def choose():
        path=filedialog.askopenfilename(parent=window,title=tr('选择已验证历史圈'),filetypes=[(tr('历史完整圈'),'*.lap.json')])
        if not path:return
        def work():
            from video_history import native_header,identity,compatible
            header=native_header(path);ident=identity(header);session=header['session'];lap=header['lap']
            return dict(file=path,identity=ident,date=session.get('started_utc',''),vehicle=session.get('vehicle',''),
                number=lap['number'],time_s=float(lap['time_s']),exact=compatible(state['video']['identity'],ident))
        def done(value,error):
            if not alive():return
            state['busy']=False;feedback.busy('file',False)
            if error:message(str(error))
            else:selected.set(add(value));changed();message('已添加历史单圈。')
            refresh()
        state['busy']=True;refresh();feedback.busy('file');app.run_background(work,done)
    def run():
        if state['busy']:return
        if app.active():message('请先停止 HUD 记录，再进行离线对比。');return
        item=state['items'].get(selected.get())
        if not item:return
        try:
            landmarks=[]
            for line in marks.get('1.0','end').splitlines():
                if line.strip():
                    name,t=line.rsplit('=',1);landmarks.append(dict(name=name.strip(),lap_time_s=clock(t)))
            state['cancel']=threading.Event()
            args=(video_path,item['file'],root,channels[channel.get()],binding.get(),landmarks,state['cancel'])
        except (ValueError,KeyError):message('地标格式：名称 = 历史圈内时间，例如 T1入口 = 0:12.500');return
        submitted=snapshot();state['busy']=True;refresh();feedback.busy('compare');message('正在读取所选历史单圈并生成对比…')
        def work():
            from video_history import export_comparison
            return export_comparison(*args)
        def done(value,error):
            if not alive():return
            state['busy']=False;feedback.busy('compare',False)
            if error:message(str(error))
            else:state['result']=value;state['baseline']=submitted;opener.configure(state='normal');message('对比已保存；点击“打开对比报告”。')
            refresh()
        app.run_background(work,done)
    def open_result():
        if state['result']:
            try:os.startfile(state['result']['report'])
            except OSError as error:message(str(error))
    start=Action(footer,'生成历史圈对比',run,180,True);start.pack(side='left',padx=(0,px(window,10)));start.configure(state='disabled')
    browse=Action(footer,'选择 .lap.json',choose,160);browse.pack(side='left',padx=(0,px(window,10)));browse.configure(state='disabled')
    opener=Action(footer,'打开对比报告',open_result,170);opener.pack(side='left');opener.configure(state='disabled')
    window.history_controls=dict(selected=selected,box=box,binding=binding,channel=channel,start=start,marks=marks,changed=changed,close=close,source=source_label)
    state['baseline']=snapshot()
    def source_text():
        name=Path((state['video'] or {}).get('video_file') or str(video_path.parent)).name
        source_label.configure(text=tr('当前视频结果：{name}').format(name=name)+' · '+video_path.parent.name)
    def loaded(value,error):
        if not alive():return
        state['busy']=False;feedback.busy('load',False)
        if error:message(str(error));return
        video,items=value;state['video']=video
        for item in items:add(item)
        if state['items']:selected.set(next(iter(state['items'])));changed()
        state['baseline']=(selected.get(),next(iter(channels)),False,'')
        source_text()
        ident=video['identity'];message('视频：{track} / {layout} · {length} m；找到 {count} 份同赛道历史曲线。',track=ident['track'],layout=ident['track_layout'],length=ident['length_m'],count=len(items))
        if not items:identity_label.configure(text='尚无同赛道的已导出有效圈；可先在赛事复盘导出完整圈，或选择 .lap.json。')
        refresh()
    def load():
        from video_history import load_video,history_laps
        video=load_video(video_path);return video,history_laps(root,video,state['cancel'])
    app.run_background(load,loaded)
    def translate():
        source_text();identity_text();refresh()
        key,values=state['message'];message(key,**values)
        for action in (start,browse,opener):action.paint()
    window.retranslate=translate
    window.bind('<Destroy>',lambda e:state['cancel'].set() if e.widget is window else None,add='+')
    return window
