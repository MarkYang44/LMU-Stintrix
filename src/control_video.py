"""Independent video wizard; decoder and OCR imports stay off idle HUD paths."""
import json
import os
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog
from control_theme import T
from i18n import tr,Label
from management import panel
from video_signal import clock
from control_video_assist import VideoAssist

MODES={'普通 POV · 时间 / 地标':'time','距离 + 计时 HUD · OCR':'distance_hud','视频 + 同圈遥测 · 同步':'telemetry'}


def show(app,root):
    existing=getattr(app,'video_window',None)
    if existing is not None and existing.winfo_exists():existing.lift();return existing
    window=panel(app,'Stintrix · 视频提取油刹曲线',1180,900);window.minsize(940,720);app.video_window=window
    wizard=VideoWizard(app,window,Path(root));window.video_wizard=wizard
    return window


class VideoWizard(VideoAssist):
    def __init__(self,app,window,root):
        self.app=app;self.window=window;self.root=root;self.media=None;self.image=None;self.photo=None
        self.geometry={};self.calibration_size=None;self.clicks=[];self.drag=None;self.busy=False;self.cancel=threading.Event();self.progress=(0,'');self.result=None
        self.fields={};self.zoom=tk.DoubleVar(window,value=1);self.target=tk.StringVar(window,value='throttle')
        self.mode=tk.StringVar(window,value=next(iter(MODES)));self.status=tk.StringVar(window,value='先选择视频，再读取标定帧。所有处理都在本机完成。')
        self.clockwise={k:tk.BooleanVar(window,value=True) for k in ('throttle','brake')}
        self.thickness=tk.StringVar(window,value='6');self.hz=tk.StringVar(window,value='20');self.unit=tk.StringVar(window,value='m')
        self.init_assist()
        from control_video_layout import build
        from control_motion import Motion
        self.motion=Motion(window);self.poll_job=None;self.preview_key=None;self.scroll_pages=[]
        build(self,MODES);self.mode_changed();self.palette_roles=[]
        def remember(widget):
            if isinstance(widget,(tk.Label,tk.Entry,tk.Text)):
                color=widget.cget('fg');role=next((key for key in ('FG','MUTED','ACCENT') if getattr(T,key)==color),None)
                if role:self.palette_roles.append((widget,role))
            for child in widget.winfo_children():remember(child)
        remember(window)
        window.protocol('WM_DELETE_WINDOW',self.close)
        window.bind('<Destroy>',self.destroyed,add='+')
        self.motion.animate('enter',lambda t:window.attributes('-alpha',.92+.08*t),200)
        from library import inventory
        def loaded(events,error):
            if not self.alive():return
            if not error:
                from track_names import display,layout_label
                for event in events:
                    track=event.get('track');layout=event.get('track_layout');length=event.get('track_length_m')
                    if track and layout and isinstance(length,(int,float)) and length>100:
                        label=f'{display(track)} / {layout_label(track,layout)} · {length:.1f} m [{layout}]'
                        self.identities[label]=(track,layout,length)
                self.identitybox.configure(values=list(self.identities))
                self.infer_layout()
        app.run_background(lambda:inventory(root),loaded)

    def alive(self):return not self.app.closing and self.window.winfo_exists()

    def refresh_palette(self):
        from control_video_widgets import Action,TaskProgress
        from control_fields import Field,Select
        from control_widgets import Switch
        for widget,role in self.palette_roles:
            if widget.winfo_exists():widget.configure(fg=getattr(T,role))
        def repaint(widget):
            if isinstance(widget,(Action,TaskProgress,Field,Select,Switch)):widget.paint()
            for child in widget.winfo_children():repaint(child)
        repaint(self.window)
        for strip in (self.tabs,self.targets):
            if strip is self.tabs:strip.indicator.select(strip.buttons[strip.current],False)
            else:strip.refresh(False)

    def entry(self,parent,title,key,default='',browse=None):
        from control_video_layout import entry
        return entry(self,parent,title,key,default,browse)

    def choose(self,key,kind):
        if self.busy:return
        if kind=='directory':value=filedialog.askdirectory(parent=self.window)
        else:
            types=[('视频','*.mp4 *.mkv *.mov *.webm *.avi'),('所有文件','*')] if kind=='video' else [('完整圈遥测','*.lap.json')]
            value=filedialog.askopenfilename(parent=self.window,filetypes=types)
        if value:
            self.fields[key].set(value)
            if key=='video':
                self.selected_video()
            if key=='telemetry':
                def work():
                    from video_alignment import native_header
                    path=Path(value)
                    if path.stat().st_size>1024*1024*1024:raise ValueError('请选择单圈 JSON（小于 1 GiB）')
                    return native_header(path)
                def done(data):
                    for target,source in [('track','track'),('layout','track_layout')]:self.fields[target].set(data['session'].get(source,''))
                    self.fields['length'].set(str(data['lap']['track_length_m']))
                    self.status.set('已读取遥测身份；请确认与视频为同一圈，并填写同步点。')
                self.dispatch(work,done)

    def use_identity(self):
        selected=self.identities.get(self.identity.get())
        if selected:
            for key,value in zip(('track','layout','length'),selected):self.fields[key].set(str(value))

    def mode_changed(self):
        notes={'time':'普通 POV：仅时间轴；填写固定地标后可比较分段耗时。',
               'distance_hud':'距离 HUD：框选纯距离数值与 m:ss.xxx 圈内计时。两者须来自同一游戏时钟；不能是速度、总里程或预测圈时。OCR 未通过检查时降级为时间轴。',
               'telemetry':'同圈遥测：使用圈速对比导出的已验证完整圈 .lap.json；官方 DuckDB 需先导入。选择文件会填入原始赛道身份，再填写同步点。这里只做视频同步校准，不修改遥测。'}
        self.mode_hint.configure(text=notes[MODES[self.mode.get()]])
        mode=MODES[self.mode.get()]
        if mode=='telemetry':self.telemetry_card.pack(fill='x',before=self.landmark_card,pady=(0,12))
        else:self.telemetry_card.pack_forget()
        if mode=='distance_hud':self.distance_options.pack(side='left',padx=24)
        else:self.distance_options.pack_forget()
        for key in ('distance_box','timer_box'):self.targets.buttons[key].configure(state='normal' if mode=='distance_hud' else 'disabled')
        if mode!='distance_hud' and self.target.get() in ('distance_box','timer_box'):self.target.set('throttle')

    def pause_hidden_scroll(self):
        for page in self.scroll_pages:
            if str(page)!=self.tabs.select():page.scroller.cancel()

    def wheel(self,event):
        if isinstance(event.widget,tk.Text):return
        for page in self.scroll_pages:
            if str(page)==self.tabs.select():page.wheel(event.delta);return 'break'

    def empty_preview(self):
        if self.image is not None:return
        width=self.canvas.winfo_width();height=self.canvas.winfo_height();self.canvas.delete('empty')
        self.canvas.create_text(width/2,height/2-15,text=tr('等待标定帧'),fill=T.FG,font=(T.FONT,16,'bold'),tags='empty')
        self.canvas.create_text(width/2,height/2+20,text=tr('先在第 1 步选择视频并读取一帧画面'),fill=T.MUTED,font=(T.FONT,10),tags='empty')

    def responsive(self,event):
        if event.widget is not self.window:return
        from control_widgets import px
        compact=event.height<px(self.window,820)
        if compact==getattr(self,'compact',None):return
        self.compact=compact
        if compact:
            self.heading_meta.pack_forget();self.heading_hint.pack_forget()
            self.heading_title.configure(font=(T.FONT,17,'bold'));self.heading_frame.pack_configure(pady=(5,1))
        else:
            self.heading_meta.pack(fill='x',before=self.heading_title,pady=(3,7));self.heading_hint.pack(fill='x',pady=(3,7))
            self.heading_title.configure(font=(T.FONT,21,'bold'));self.heading_frame.pack_configure(pady=(15,6))

    def fit_preview(self):
        if self.image is None:return
        self.window.update_idletasks()
        amount=min((self.canvas.winfo_width()-8)/self.image.width,(self.canvas.winfo_height()-8)/self.image.height,3)
        self.zoom.set(max(.1,round(amount,2)));self.redraw();self.canvas.xview_moveto(0);self.canvas.yview_moveto(0)

    def target_changed(self):
        self.clicks=[]
        self.hint.set('依次点击：圆心 → 0% 起点 → 100% 终点。注意选择正确方向。' if self.target.get() in self.clockwise else '拖动框选固定区域。锚点应是始终可见的固定文字，例如 KPH；数值区只框选数字。')
        self.redraw()

    def clear_target(self):
        self.geometry.pop(self.target.get(),None);self.clicks=[];self.redraw()

    def check_calibration(self):
        if self.image is None:return
        from video_signal import arc_points,pedal
        sx=self.image.width/self.media['width'];sy=self.image.height/self.media['height']
        try:
            readings=[]
            for key in ('throttle','brake'):
                arc=dict(self.geometry[key],clockwise=self.clockwise[key].get(),thickness=float(self.thickness.get()))
                points=[[(round(x*sx),round(y*sy)) for x,y in samples] for samples in arc_points(arc)]
                value,_=pedal(self.image,points,key);readings.append('无法读取' if value is None else f'{value:.0%}')
            self.status.set('预览估算：油门 '+readings[0]+' / 刹车 '+readings[1]+'。请与画面核对；预览缩放可能带来量化差异。')
        except (ValueError,KeyError,TypeError) as error:self.status.set('标定未完成：'+str(error))

    def point(self,event):
        sx,sy=self.factors();return [self.canvas.canvasx(event.x)/sx,self.canvas.canvasy(event.y)/sy]

    def factors(self):
        return self.image.width*self.zoom.get()/self.media['width'],self.image.height*self.zoom.get()/self.media['height']

    def press(self,event):
        if self.busy or self.image is None:return
        point=self.point(event)
        if not 0<=point[0]<self.media['width'] or not 0<=point[1]<self.media['height']:return
        if self.target.get() in self.clockwise:
            self.save_undo()
            if len(self.clicks)>=3:self.clicks=[]
            if not self.clicks:self.geometry.pop(self.target.get(),None)
            self.clicks.append(point)
            if len(self.clicks)==3:self.geometry[self.target.get()]=dict(points=list(self.clicks))
            self.hint.set(['点击 0% 起点','点击 100% 终点','圆弧已标定；检查覆盖线，必要时切换顺 / 逆时针。'][len(self.clicks)-1]);self.redraw()
            if len(self.clicks)==3:self.advance_target()
        else:self.drag=point

    def dragging(self,event):
        if self.drag is None or self.busy:return
        sx,sy=self.factors();point=self.point(event);self.canvas.delete('drag')
        self.canvas.create_rectangle(self.drag[0]*sx,self.drag[1]*sy,point[0]*sx,point[1]*sy,outline='#ffff55',width=2,tags='drag')

    def release(self,event):
        if self.drag is None or self.busy:return
        point=self.point(event);x,y=self.drag;self.drag=None
        point=[max(0,min(point[0],self.media['width'])),max(0,min(point[1],self.media['height']))]
        box=[round(min(x,point[0])),round(min(y,point[1])),round(max(x,point[0])),round(max(y,point[1]))]
        if box[2]-box[0]<8 or box[3]-box[1]<8:self.hint.set('框选区域太小，请重新框选固定文字。');self.redraw();return
        self.save_undo();self.geometry[self.target.get()]=box;self.redraw();self.advance_target()

    def cancel_current(self):
        if not self.busy:return
        self.cancel.set();self.stop.configure(state='disabled');self.progress[:]=[self.progress[0],'正在取消，保留已有结果…']
        self.status.set(self.progress[1])

    def redraw(self):
        if self.image is None:self.empty_preview();return
        from PIL import ImageTk
        from video_signal import arc_points
        zoom=self.zoom.get();key=(id(self.image),zoom)
        # Geometry changes never resample/re-upload the video bitmap.
        if key!=self.preview_key:
            self.photo=ImageTk.PhotoImage(self.image.resize((round(self.image.width*zoom),round(self.image.height*zoom))),master=self.window)
            self.canvas.delete('bitmap');self.canvas.create_image(0,0,image=self.photo,anchor='nw',tags='bitmap');self.canvas.tag_lower('bitmap')
            self.canvas.configure(scrollregion=(0,0,self.photo.width(),self.photo.height()));self.preview_key=key
        self.canvas.delete('empty');self.canvas.delete('overlay');self.canvas.delete('drag')
        sx,sy=self.factors()
        for key,value in self.geometry.items():
            color={'throttle':'#00ff88','brake':'#ff4455'}.get(key,'#f2e34e')
            if key in self.clockwise:
                try:
                    coordinates=[p for samples in arc_points(dict(value,clockwise=self.clockwise[key].get())) for p in [samples[1]]]
                    self.canvas.create_line(*[n for x,y in coordinates for n in (x*sx,y*sy)],fill=color,width=2,tags='overlay')
                except ValueError:pass
                for x,y in value['points']:self.canvas.create_oval(x*sx-3,y*sy-3,x*sx+3,y*sy+3,outline=color,width=2,tags='overlay')
            else:self.canvas.create_rectangle(value[0]*sx,value[1]*sy,value[2]*sx,value[3]*sy,outline=color,width=2,tags='overlay')
        if self.target.get() in self.clockwise and len(self.clicks)<3:
            for x,y in self.clicks:self.canvas.create_oval(x*sx-4,y*sy-4,x*sx+4,y*sy+4,outline=T.ACCENT,width=2,tags='overlay')
        names={'throttle':'油门圆弧','brake':'刹车圆弧','anchor':'固定文字','distance_box':'距离读数','timer_box':'圈内计时'}
        self.geometry_label.configure(text='已标定：'+(' / '.join(names.get(k,k) for k in self.geometry) or '尚未设置'))

    def dispatch(self,work,done,label='后台处理中…',with_state=False):
        if self.busy:return
        self.busy=True;self.cancel=threading.Event();self.progress=[0,label];self.status.set(label)
        self.bar.complete=False;self.bar['value']=0;self.percent.configure(text=tr('处理中'))
        self.start.configure(state='disabled',text='处理中…');self.stop.configure(state='normal');self.compare_button.configure(state='disabled')
        self.history_button.configure(state='disabled')
        self.feedback.busy('video');self.poll()
        def finished(result,error):
            self.busy=False;self.preview_loading=False
            if not self.alive():return
            if self.poll_job:self.window.after_cancel(self.poll_job);self.poll_job=None
            self.start.configure(state='normal',text='开始提取');self.stop.configure(state='disabled');self.compare_button.configure(state='normal')
            self.history_button.configure(state='normal')
            self.feedback.busy('video',False)
            if error:
                self.status.set(tr('已取消') if self.cancel.is_set() else error);self.percent.configure(text=tr('已取消') if self.cancel.is_set() else tr('未完成'))
                if '未找到 ff' in str(error):self.tools_body.pack(fill='x')
            else:
                done(result);self.bar.complete=True;self.bar['value']=100;self.bar.paint();self.percent.configure(text=tr('已完成'));self.feedback.success()
        cancel,progress=self.cancel,self.progress
        self.app.run_background((lambda:work(cancel,progress)) if with_state else work,finished)

    def load_preview(self):
        self.read_preview()

    def load_calibration(self):
        if self.busy:return
        path=filedialog.askopenfilename(parent=self.window,filetypes=[('标定','calibration.json')])
        if not path:return
        try:
            value=json.loads(Path(path).read_text(encoding='utf-8'));self.apply_geometry(value);self.undo_stack=[];self.redraw()
            self.status.set('已加载几何标定。必须使用相同分辨率与 HUD 缩放；请读取新视频标定帧检查。')
        except (OSError,ValueError,KeyError,TypeError) as error:self.status.set(str(error))

    def config(self):
        if self.media is None or self.image is None:raise ValueError('请先读取当前视频的标定帧')
        if self.calibration_size and self.calibration_size!=[self.media['width'],self.media['height']]:raise ValueError('加载的标定分辨率不同，请重新读取视频并标定')
        if Path(self.fields['video'].get()).resolve()!=Path(self.media['path']):raise ValueError('视频已更换，请重新读取标定帧')
        config=dict(video=self.fields['video'].get(),ffmpeg_dir=self.fields['ffmpeg'].get(),mode=MODES[self.mode.get()],frame_size=[self.media['width'],self.media['height']],
            start_s=clock(self.fields['start'].get()),end_s=clock(self.fields['end'].get()),sample_s=clock(self.fields['sample'].get()),
            identity=dict(track=self.fields['track'].get().strip(),track_layout=self.fields['layout'].get().strip(),length_m=float(self.fields['length'].get())),
            hz=float(self.hz.get()),telemetry=self.fields['telemetry'].get(),distance_unit=self.unit.get(),landmarks=[],sync=[])
        for key in ('throttle','brake','anchor'):
            if key not in self.geometry:raise ValueError('缺少标定：'+key)
        config.update(self.geometry)
        for key in self.clockwise:config[key]=dict(config[key],clockwise=self.clockwise[key].get(),thickness=float(self.thickness.get()))
        for line in self.marks.get('1.0','end').splitlines():
            if line.strip():
                name,when=line.rsplit('=',1);config['landmarks'].append(dict(name=name.strip(),video_s=clock(when)))
        if config['mode']=='telemetry':
            for line in self.sync.get('1.0','end').splitlines():
                if line.strip():a,b=line.split('=',1);config['sync'].append([clock(a),clock(b)])
        if config['mode']=='distance_hud' and any(k not in config for k in ('distance_box','timer_box')):raise ValueError('距离 HUD 模式需要框选距离数值和圈内计时')
        return config

    def run(self):
        if self.busy:return
        if self.app.active():self.status.set('请先停止 HUD 记录，再进行视频分析，避免争用比赛资源。');return
        try:config=self.config()
        except (ValueError,KeyError,TypeError) as error:self.status.set('输入未完成：'+str(error));return
        root=self.root
        def work(cancel,progress):
            from video_analysis import analyze
            return analyze(config,root,cancel,lambda p,t:progress.__setitem__(slice(None),[p,t]))
        def done(result):
            self.result=result;self.open.configure(state='normal');self.bar['value']=100
            if result['quality']['pedal_readable_ratio']>=.9:
                from video_preferences import remember
                try:remember(self.root,config,self.image,self.media)
                except (ValueError,KeyError,OSError):pass
            self.status.set('已保存：'+result['folder']+'；点击“打开结果”查看报告。')
        self.dispatch(work,done,with_state=True)

    def open_result(self):
        if self.result:
            try:os.startfile(self.result['report'])
            except OSError as error:self.status.set(str(error))

    def compare_history(self):
        if self.busy:return
        from control_video_history import show
        path=Path(self.result['folder'])/'curve.json' if self.result else None
        show(self.app,self.root,path if path and path.is_file() else None)

    def compare(self):
        if self.busy:return
        files=[]
        for name in ('A','B'):
            value=filedialog.askopenfilename(parent=self.window,title=tr('选择提取结果 ')+name,filetypes=[('提取结果','curve.json')])
            if not value:return
            files.append(value)
        root=self.root
        def work():
            from video_alignment import compare
            from video_report import write_comparison
            import uuid
            values=[]
            for file in files:
                if Path(file).stat().st_size>32*1024*1024:raise ValueError('提取结果文件过大')
                values.append(json.loads(Path(file).read_text(encoding='utf-8')))
            result=compare(*values);folder=root/'VideoCurves'/('Compare-'+uuid.uuid4().hex[:12]);folder.mkdir(parents=True)
            (folder/'comparison.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');write_comparison(folder/'report.html',result,*values)
            return dict(folder=str(folder),report=str(folder/'report.html'))
        def done(result):self.result=result;self.open.configure(state='normal');self.status.set('两圈对比已保存：'+result['folder'])
        self.dispatch(work,done)

    def poll(self):
        self.poll_job=None
        if not self.alive() or not self.busy:return
        self.bar['value']=self.progress[0]
        self.status.set('正在取消，保留已有结果…' if self.cancel.is_set() else self.progress[1])
        self.percent.configure(text=f'{self.progress[0]}%' if self.progress[0] else tr('处理中'))
        self.poll_job=self.window.after(150,self.poll)

    def destroyed(self,event):
        if event.widget is self.window:
            self.cancel.set();self.photo=None;self.image=None;self.preview_key=None;self.palette_roles.clear()
            if self.poll_job:
                try:self.window.after_cancel(self.poll_job)
                except tk.TclError:pass
                self.poll_job=None
            if self.seek_job:
                try:self.window.after_cancel(self.seek_job)
                except tk.TclError:pass
                self.seek_job=None

    def close(self):self.cancel.set();self.window.destroy()
