"""Live card preview with DPI-aware layout and a permanently visible export bar."""
import os,tkinter as tk
from i18n import tr
from control_theme import T
from control_motion import reveal_window
from control_widgets import Switch,px,backdrop
from track_names import display
from control_feedback import StatusFeedback,ImageSurface


def show(app,entry):
    if not entry:app.status.set(tr('请选择一条纪录'));return
    window=tk.Toplevel(app.root);window.title(tr('生成个人战绩卡'));window.configure(bg=T.BG)
    w=min(px(window,1060),window.winfo_screenwidth()-80);h=min(px(window,620),window.winfo_screenheight()-100)
    window.geometry(f'{w}x{h}');window.minsize(min(w,px(window,760)),min(h,px(window,500)))
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=px(window,18),pady=(0,px(window,18)))
    status=tk.StringVar(window,value=tr('正在读取赛事信息…'));feedback=StatusFeedback(footer,status);feedback.pack(side='left',fill='x',expand=True,padx=px(window,16),pady=px(window,16));feedback.busy('load')
    body=tk.Frame(window,bg=T.BG);body.pack(fill='both',expand=True,padx=px(window,18),pady=px(window,18));body.columnconfigure(0,weight=1);body.columnconfigure(1,minsize=px(window,280));body.rowconfigure(0,weight=1)
    preview=tk.Frame(body,bg=T.CARD);preview.grid(row=0,column=0,sticky='nsew',padx=(0,px(window,16)))
    app.label(preview,'战绩卡预览',15,T.FG,True).pack(anchor='w',padx=px(window,18),pady=(px(window,18),4))
    app.label(preview,'白色简约版 · 1920 × 1080 PNG',9).pack(anchor='w',padx=px(window,18),pady=(0,px(window,10)))
    canvas=ImageSurface(preview);canvas.pack(fill='both',expand=True,padx=px(window,18),pady=(0,px(window,18)))
    options=tk.Frame(body,bg=T.CARD);options.grid(row=0,column=1,sticky='nsew')
    inner=tk.Frame(options,bg=T.CARD);inner.pack(fill='both',expand=True,padx=px(window,18),pady=px(window,18))
    def wrapped(text,size=10,color=T.MUTED,bold=False):
        label=app.label(inner,text,size,color,bold);label.pack(fill='x',pady=px(window,6));label.bind('<Configure>',lambda e:label.configure(wraplength=max(80,e.width)));return label
    wrapped('分享设置',16,T.FG,True);wrapped(display(entry['track']),12,T.ACCENT,True)
    wrapped(entry['session'].get('vehicle',''),10,T.FG);wrapped('预览会随设置更新；只导出图片，不上传赛事数据。',9)
    name=tk.BooleanVar(window,value=False);date=tk.BooleanVar(window,value=False)
    privacy=tk.StringVar(window);wrapped(privacy,9)
    state=dict(details=None,image=None,photo=None,revision=0,job=None,busy=False)
    def alive():return bool(window.winfo_exists()) and not app.closing
    def update_privacy():
        visible=[tr(label) for enabled,label in ((name.get(),'车手姓名'),(date.get(),'比赛日期')) if enabled]
        privacy.set(tr('显示字段')+': '+' / '.join(visible) if visible else tr('姓名与日期已隐藏'))
    def request():
        update_privacy();state['revision']+=1;revision=state['revision']
        if state['job']:window.after_cancel(state['job']);state['job']=None
        if state['details'] is None:return
        feedback.busy('preview');status.set(tr('正在更新预览…'));canvas.pending(tr('正在更新预览…'))
        def start():
            state['job']=None
            from achievement_card import payload,compose
            value=payload(entry,state['details'],name.get(),date.get())
            def done(result,error):
                if not alive() or revision!=state['revision']:return
                feedback.busy('preview',False)
                if error:status.set(error);return
                state['image']=result;canvas.show(result)
                if not state['busy']:status.set(tr('预览已更新；图片仅保存本机'))
            app.run_background(lambda:compose(value),done)
        state['job']=window.after(100,start)
    for text,var in (('显示车手姓名',name),('显示比赛日期',date)):
        Switch(inner,text,var,request).pack(fill='x',pady=px(window,4))
    wrapped('导出规格',11,T.FG,True);wrapped('16:9 · PNG · 全高清',10);wrapped('每次生成独立文件，已有战绩卡不会覆盖。',9)
    def generate():
        if state['busy'] or state['details'] is None:return
        if state.get('button_job'):window.after_cancel(state['button_job']);state['button_job']=None
        from achievement_card import payload,render
        value=payload(entry,state['details'],name.get(),date.get());state['busy']=True;export_button.label=tr('正在生成战绩卡…');export_button.paint();feedback.busy('export');status.set(tr('正在生成战绩卡…'))
        def done(result,error):
            state['busy']=False
            if not alive():return
            feedback.busy('export',False)
            if error:export_button.label=tr('生成并打开图片');export_button.paint();status.set(error);return
            export_button.label='✓ '+tr('已保存本机');export_button.paint()
            start=export_button.amount
            def confirm(t):export_button.amount=start+.25*(1-start)*(1-t);export_button.paint()
            export_button.motion.animate('complete',confirm,160)
            state['button_job']=window.after(1600,restore_button)
            status.set(tr('已保存本机'));app.status.set(result);app.shell.status_feedback.success();os.startfile(result)
        app.run_background(lambda:render(app.data_path,value),done)
    export_button=app.button(footer,'生成并打开图片',generate,True,190)
    def restore_button():
        state['button_job']=None;export_button.label=tr('生成并打开图片');export_button.paint()
    def read():
        if 'place' in entry:
            from podium_records import detail
        else:
            from personal_records import detail
        return detail(entry)
    def loaded(result,error):
        if not alive():return
        feedback.busy('load',False)
        if error:status.set(error);return
        state['details']=result;request()
    def dispose(event):
        if event.widget is not window:return
        if state['job']:window.after_cancel(state['job']);state['job']=None
        if state.get('button_job'):window.after_cancel(state['button_job']);state['button_job']=None
        state['photo']=None;state['image']=None
    window.bind('<Destroy>',dispose,add='+');update_privacy();app.run_background(read,loaded);backdrop(window);reveal_window(window)
