"""Stable, coalesced achievement previews with recoverable local PNG export."""
import os,tkinter as tk
from pathlib import Path
import i18n
from i18n import tr,Label
from control_theme import T
from control_motion import reveal_window,motion_allowed,keyboard_action
from control_widgets import Switch,px,backdrop
from control_video_widgets import Action,ScrollPage
from control_flow import install
from track_names import display
from control_feedback import StatusFeedback,ImageSurface


def record_key(entry):
    def stamp(file):
        try:s=Path(file).stat();return s.st_size,s.st_mtime_ns
        except OSError:return None
    folder=Path(entry['folder']).resolve();file=entry.get('file','')
    session=entry['session'];summary=entry.get('summary') or {}
    identity=tuple(entry.get(k) for k in ('track','layout','length_m','vehicle_class','place','time_s','fastest_s'))
    return str(folder),str(file),identity,entry.get('lap',{}).get('number'),summary.get('grid_class_place'),tuple(session.get(k) for k in ('vehicle','driver','started_utc','session')),stamp(file) if file else None,stamp(folder/'session.json')


def show(app,entry):
    if not entry:app.status.set(tr('请选择一条纪录'));return
    windows=getattr(app,'achievement_windows',{});app.achievement_windows=windows;key=record_key(entry);previous=windows.get(key)
    if previous is not None and previous.winfo_exists():previous.deiconify();previous.lift();previous.focus_force();return previous
    window=tk.Toplevel(app.root);windows[key]=window;window.title(tr('生成个人战绩卡'));window.configure(bg=T.BG);window.transient(app.root)
    w=min(px(window,1060),window.winfo_screenwidth()-80);h=min(px(window,680),window.winfo_screenheight()-100)
    window.geometry(f'{w}x{h}');window.minsize(min(w,px(window,760)),min(h,px(window,500)))
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=px(window,18),pady=(0,px(window,18)))
    status=tk.StringVar(window);privacy=tk.StringVar(window);output=tk.StringVar(window);name=tk.BooleanVar(window,value=False);date=tk.BooleanVar(window,value=False)
    feedback=StatusFeedback(footer,status);feedback.pack(fill='x',padx=12,pady=(10,6))
    saved_row=tk.Frame(footer,bg=T.CARD);Label(saved_row,text='最近保存',bg=T.CARD,fg=T.MUTED).pack(side='left',padx=(0,8))
    path_field=tk.Entry(saved_row,textvariable=output,state='readonly',readonlybackground=T.FIELD,bg=T.FIELD,fg=T.FG,selectbackground=T.SELECT,selectforeground=T.FG,font=(T.FONT,9),relief='flat')
    path_field.pack(side='left',fill='x',expand=True)
    def select_path(_):path_field.selection_range(0,'end');return 'break'
    path_field.bind('<Control-a>',select_path)
    actions=tk.Frame(footer,bg=T.CARD);actions.pack(fill='x',padx=10,pady=(0,8))
    body=tk.Frame(window,bg=T.BG);body.pack(fill='both',expand=True,padx=px(window,18),pady=px(window,18));body.columnconfigure(0,weight=1);body.columnconfigure(1,minsize=px(window,290));body.rowconfigure(0,weight=1)
    preview=tk.Frame(body,bg=T.CARD);preview.grid(row=0,column=0,sticky='nsew',padx=(0,px(window,16)))
    Label(preview,text='战绩卡预览',bg=T.CARD,fg=T.FG,font=(T.FONT,15,'bold')).pack(anchor='w',padx=18,pady=(18,4))
    Label(preview,text='白色简约版 · 1920 × 1080 PNG',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9)).pack(anchor='w',padx=18,pady=(0,10))
    canvas=ImageSurface(preview);canvas.pack(fill='both',expand=True,padx=16,pady=(0,16))
    options=ScrollPage(body);options.grid(row=0,column=1,sticky='nsew');options.configure(bg=T.CARD);options.canvas.configure(bg=T.CARD);inner=options.body;inner.configure(bg=T.CARD)
    def wrapped(text,size=10,color=None,bold=False):
        label=Label(inner,textvariable=text,bg=T.CARD,fg=color or T.MUTED,font=(T.FONT,size,'bold' if bold else 'normal')) if isinstance(text,tk.Variable) else Label(inner,text=text,bg=T.CARD,fg=color or T.MUTED,font=(T.FONT,size,'bold' if bold else 'normal'))
        label.pack(fill='x',padx=12,pady=6);label.configure(justify='left',anchor='w');label.bind('<Configure>',lambda e:label.configure(wraplength=max(80,e.width)));return label
    wrapped('分享设置',16,T.FG,True);wrapped(display(entry['track']),12,T.ACCENT,True);wrapped(entry['session'].get('vehicle',''),10,T.FG)
    wrapped('预览会随设置更新；只导出图片，不上传赛事数据。',9);wrapped(privacy,9)
    state=dict(details=None,image=None,revision=0,rendered=-1,job=None,preview_running=False,busy=False,loading=False,error=False,result=None,message='',language=i18n.language,animate=True)
    buttons={};switches=[]
    data_path=Path(app.data_path);folder=data_path/'PersonalRecords/AchievementCards'
    def alive():return not app.closing and bool(window.winfo_exists())
    def say(message):state['message']=str(message);status.set(tr(str(message)))
    def update_privacy():
        visible=[tr(label) for enabled,label in ((name.get(),'车手姓名'),(date.get(),'比赛日期')) if enabled]
        privacy.set(tr('显示字段')+': '+' / '.join(visible) if visible else tr('姓名与日期已隐藏'))
    def sync():
        if not buttons:return
        ready=state['image'] is not None and state['rendered']==state['revision'] and not state['busy']
        buttons['export'].configure(state='normal' if ready else 'disabled');buttons['open'].configure(state='normal' if state['result'] else 'disabled')
        buttons['folder'].configure(state='normal' if folder.is_dir() else 'disabled');buttons['retry'].configure(state='normal' if state['error'] and not state['busy'] else 'disabled')
        for switch in switches:switch.configure(state='disabled' if state['busy'] else 'normal')
        if state['error']:
            from control_validation import reveal
            buttons['retry'].pack(fill='x',padx=12,pady=8);options.scroller.cancel();reveal(buttons['retry'])
        else:buttons['retry'].pack_forget()
    def cancel_job():
        if state['job'] is not None:window.after_cancel(state['job']);state['job']=None
    def start_preview():
        cancel_job()
        if state['preview_running'] or state['details'] is None:return
        from achievement_card import payload,compose
        value=payload(entry,state['details'],name.get(),date.get(),root=data_path);revision=state['revision'];state['preview_running']=True
        def done(result,error):
            if not alive():return
            state['preview_running']=False
            if revision!=state['revision']:start_preview();return
            feedback.busy('preview',False);state['error']=bool(error)
            if error:
                say(error)
                if state['image'] is None:canvas.pending(tr('预览失败，请重试'))
            else:
                state['image']=result;state['rendered']=revision;canvas.show(result,animate=state['animate'])
                if not state['busy']:say('预览已更新；图片仅保存本机')
            sync()
        app.run_background(lambda:compose(value),done)
    def request():
        update_privacy();state['revision']+=1;state['error']=False;state['animate']=motion_allowed(window);cancel_job();sync()
        if state['details'] is None:return
        feedback.busy('preview');say('正在更新预览；完成后可导出当前版本。')
        state['job']=window.after(100,start_preview)
    for text,var in (('显示车手姓名',name),('显示比赛日期',date)):
        switch=Switch(inner,text,var,request);switch.pack(fill='x',padx=12,pady=4);switches.append(switch)
    wrapped('导出规格',11,T.FG,True);wrapped('16:9 · PNG · 全高清',10);wrapped('导出与当前预览一致；已有战绩卡不会覆盖。',9)
    def open_last():
        path=state['result']
        if not path:return
        if not Path(path).is_file():say('上次图片已移动或删除；可重新生成，或打开导出目录查找。');return
        try:os.startfile(path)
        except OSError as error:say(tr('图片已保存，打开失败；可重试打开或查看导出目录。')+' '+str(error))
    def open_folder():
        if not folder.is_dir():say('导出目录尚未创建，请先生成图片。');sync();return
        try:os.startfile(str(folder))
        except OSError as error:say(error)
    def generate():
        if state['busy'] or state['image'] is None or state['rendered']!=state['revision']:return
        from achievement_card import save_image
        image=state['image'];revision=state['revision'];state['busy']=True;feedback.busy('export');say('正在生成战绩卡…');sync()
        def done(result,error):
            if not app.closing:
                app.status.set(str(error) if error else tr('已保存本机')+' · '+str(result))
            if not alive():return
            state['busy']=False;feedback.busy('export',False)
            if error:say(error);sync();return
            state['result']=str(result);output.set(str(result));saved_row.pack(fill='x',padx=12,pady=(0,8),before=actions)
            message='已保存本机' if revision==state['revision'] else '已保存生成时的版本；当前预览已有更新。' if state['rendered']==state['revision'] else '图片已保存；当前预览更新失败，请重试预览。' if state['error'] else '图片已保存；当前预览仍在更新。'
            say(message);feedback.success();sync();open_last()
        app.run_background(lambda:save_image(data_path,image),done)
    def read():
        if 'place' in entry:
            from podium_records import detail
            return detail(entry)
        from personal_records import detail
        return detail(entry,curve=False)
    def load_data():
        if state['loading']:return
        state['loading']=True;state['error']=False;feedback.busy('load');say('正在读取赛事信息…');sync()
        def loaded(result,error):
            if not alive():return
            state['loading']=False;feedback.busy('load',False)
            if error:state['error']=True;say(error);canvas.pending(tr('读取失败，请重试'));sync();return
            state['details']=result;request()
        app.run_background(read,loaded)
    for name_key,label,command,width,primary in [('export','生成并打开图片',generate,190,True),('open','打开上次图片',open_last,160,False),('folder','打开导出目录',open_folder,160,False)]:
        buttons[name_key]=Action(actions,label,command,width,primary);buttons[name_key].pack(side='left')
    buttons['retry']=Action(inner,'重试读取 / 预览',lambda:load_data() if state['details'] is None else request(),180)
    install(actions)
    def translate():
        update_privacy()
        for button in buttons.values():button.configure(width=max(px(button,160),button.font.measure(tr(button.label))+px(button,36)));button.paint()
        actions.event_generate('<Configure>',width=actions.winfo_width())
        if state['language']!=i18n.language:state['language']=i18n.language;request()
        else:status.set(tr(state['message']))
    window.retranslate=translate
    window.bind('<Control-s>',lambda _:(keyboard_action(window,generate),'break')[1]);window.bind('<Escape>',lambda _:(window.destroy(),'break')[1])
    def wheel(event):
        widget=event.widget
        while widget is not None and widget is not window:
            if widget is options:options.wheel(event.delta);return 'break'
            widget=getattr(widget,'master',None)
    window.bind('<MouseWheel>',wheel)
    def dispose(event):
        if event.widget is not window:return
        cancel_job();windows.pop(key,None);state['image']=None
        for variable in (status,privacy,output,name,date):variable.__del__();variable._tk=None
    window.bind('<Destroy>',dispose,add='+');update_privacy();load_data();backdrop(window);reveal_window(window)
    window.achievement_controls=dict(state=state,buttons=buttons,switches=switches,name=name,date=date,request=request,generate=generate,load=load_data,canvas=canvas,status=status,privacy=privacy,output=output,path=path_field,footer=footer,options=options)
    return window
