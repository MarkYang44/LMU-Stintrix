"""First-use guidance; UI-only readiness checks never replace extraction validation."""
from pathlib import Path
import tkinter as tk
from control_theme import T
from i18n import Label,tr
from video_signal import clock,number,arc_points

NAMES={'throttle':'油门圆弧','brake':'刹车圆弧','anchor':'固定文字','distance_box':'距离读数','timer_box':'圈内计时'}


class VideoGuide:
    def init_guidance(self):
        self.range_confirmed=tk.BooleanVar(self.window,value=False)
        self.guide_heading=tk.StringVar(self.window);self.guide_detail=tk.StringVar(self.window)
        self.range_summary=tk.StringVar(self.window);self.result_note=tk.StringVar(self.window)
        self.guide_job=None;self.guide_traces=[];self.guide_ready=False;self.help_window=None
        self.review_values=[tk.StringVar(self.window) for _ in range(4)]

    def install_guidance(self):
        self.guide_ready=True
        def changed(key):
            if key in ('start','end') and self.range_confirmed.get():self.range_confirmed.set(False)
            self.queue_guidance()
        for key,var in self.fields.items():
            token=var.trace_add('write',lambda *_,k=key:changed(k));self.guide_traces.append((var,token))
        for var in (self.mode,self.target,self.range_confirmed,self.thickness,*self.clockwise.values()):
            token=var.trace_add('write',lambda *_:self.queue_guidance());self.guide_traces.append((var,token))
        for widget in (self.sync,self.marks):
            def edited(_,area=widget):
                if area.edit_modified():area.edit_modified(False);self.queue_guidance()
            widget.bind('<<Modified>>',edited,add='+')
        self.tabs.bind('<<NotebookTabChanged>>',lambda _:self.queue_guidance(),add='+')
        self.update_guidance()

    def queue_guidance(self):
        if not self.guide_ready or self.guide_job:return
        try:self.guide_job=self.window.after_idle(self.update_guidance)
        except tk.TclError:pass

    def dispose_guidance(self):
        self.guide_ready=False
        if self.guide_job:
            try:self.window.after_cancel(self.guide_job)
            except tk.TclError:pass
            self.guide_job=None
        for var,token in self.guide_traces:
            try:var.trace_remove('write',token)
            except tk.TclError:pass
        self.guide_traces.clear()

    def setup_issue(self):
        if not self.fields['video'].get().strip():return 'video',0,'先选择本地视频；保持原速、无剪辑，画面中的油刹 HUD 要清楚可见。'
        if self.media is None or self.image is None:return 'preview',0,'等待预览完成；如果失败，请展开工具设置，选择同时包含 ffmpeg 和 ffprobe 的目录。'
        if not self.media.get('path') or Path(self.fields['video'].get()).resolve()!=Path(self.media['path']):return 'preview',0,'视频路径已变化，请重新读取预览。'
        if not self.fields['track'].get().strip() or not self.fields['layout'].get().strip():return 'identity',0,'请选择已有赛道布局；列表为空时，点“手动填写”输入游戏中的赛道、布局和长度。'
        try:number(self.fields['length'].get(),100,50000)
        except ValueError:return 'identity',0,'布局长度用米填写，例如 4535.8；请查游戏或赛事记录，不要根据视频圈时猜测。'

    def range_issue(self):
        try:
            start=clock(self.fields['start'].get());end=clock(self.fields['end'].get())
            if end-start<.5 or end-start>1800 or self.media is None or end>self.media.get('duration',0)+.02:raise ValueError()
        except ValueError:return 'range',1,'先拖动预览条：在起点过线时点“设为圈起点”，下一次经过同一标线时点“设为圈终点”。'
        if not self.range_confirmed.get():return 'confirm',1,'核对起点和终点是同一条标线、相隔完整一圈，再勾选“我已核对完整一圈”。整段视频不一定就是一圈。'
        try:sample=clock(self.fields['sample'].get())
        except ValueError:sample=-1
        if not start<=sample<end:return 'sample',1,'当前预览不在圈段内；点击下方主按钮，切换到圈内画面后再标定。'

    def calibration_issue(self):
        required=['throttle','brake','anchor']+(['distance_box','timer_box'] if self.mode_code()=='distance_hud' else [])
        if self.calibration_size and self.media and self.calibration_size!=[self.media['width'],self.media['height']]:return 'resolution',1,'标定分辨率不同，请重做本次标定；不要直接套用不同大小的 HUD。'
        for key in required:
            if key not in self.geometry:return key,1,tr('还需标定')+'：'+tr(NAMES[key])
            value=self.geometry[key]
            try:
                if key in self.clockwise:
                    points=arc_points(dict(value,clockwise=self.clockwise[key].get(),thickness=float(self.thickness.get())))
                    if self.media and any(not 0<=x<=self.media['width'] or not 0<=y<=self.media['height'] for samples in points for x,y in samples):raise ValueError('圆弧超出画面')
                elif len(value)!=4 or self.media and not (0<=value[0]<value[2]<=self.media['width'] and 0<=value[1]<value[3]<=self.media['height'] and value[2]-value[0]>=8 and value[3]-value[1]>=8):raise ValueError('框选区域太小或超出画面')
            except (ValueError,KeyError,TypeError,IndexError) as error:return key,1,tr('需要调整')+' '+tr(NAMES[key])+'：'+str(error)

    def mode_issue(self):
        if self.mode_code()!='telemetry':return
        if not self.fields['telemetry'].get().strip():return 'telemetry',2,'此模式需要视频中同一圈的 .lap.json；不同圈只能做结果对比，不能用于同步标定。'
        try:
            points=[line.split('=') for line in self.sync.get('1.0','end').splitlines() if line.strip()]
            if len(points)<2:raise ValueError()
            for pair in points:
                if len(pair)!=2:raise ValueError()
                clock(pair[0]);clock(pair[1])
        except ValueError:return 'sync',2,'同步点每行填写“视频时间 = 遥测圈内时间”，至少两行；建议三个独立事件，覆盖至少 80% 圈时。'

    def issues(self):return [self.setup_issue(),self.range_issue(),self.calibration_issue(),self.mode_issue()]

    def update_guidance(self):
        self.guide_job=None
        if not self.guide_ready or not self.alive():return
        page=self.tabs.current;issues=self.issues();first=next((item for item in issues if item),None)
        try:
            a=clock(self.fields['start'].get());b=clock(self.fields['end'].get())
            self.range_summary.set(f'{a:.3f} s → {b:.3f} s · {b-a:.3f} s')
        except ValueError:self.range_summary.set(tr('圈段尚未设置'))
        if page==0:
            title='先选视频，再选赛道布局';detail=issues[0][2] if issues[0] else '视频与布局已准备好。点击“下一步”，在画面中标记完整一圈，再标定油门与刹车。'
            action='下一步：圈段与标定'
        elif page==1:
            title='先确定完整一圈';detail=issues[1][2] if issues[1] else '';action='下一步：检查并提取'
            if not issues[1]:
                key=self.target.get();value=self.geometry.get(key);name=tr(NAMES[key])
                if key in self.clockwise:
                    count=len(self.clicks)
                    if value and not count:title=name+tr(' · 已标定');detail='切到该踏板正在踩下的画面，核对覆盖线和“检查标定”读数；恒为零时先检查是否选错圆弧。'
                    else:
                        title=name+' · '+str(min(count+1,3))+'/3'
                        detail=['先切到该踏板踩下的画面。绿色是油门、红色是刹车，两条弧可能都在左侧且半径不同；点击几何圆心，不是弧线。','点击真正的 0% 起点。即使当前有踩踏，也要找完整刻度的起点。','点击真正的 100% 终点。不要把视频里观察到的最大刹车当作 100%。'][min(count,2)]
                    if count==3 and issues[2] and issues[2][0]==key:detail=issues[2][2]+tr('；撤销上一个点，或展开“方向与弧宽”修正。')
                else:
                    title=tr('拖框')+' · '+name
                    detail={'anchor':'按住鼠标拖框，只圈始终不变的文字，例如 KPH。不要圈车速、挡位、圈时或会变化的背景。',
                        'distance_box':'只框本圈赛道距离的纯数值；不要使用车速或总行驶里程。单位在检查页设置。',
                        'timer_box':'只框当前这一圈的实际计时，例如 1:23.456；不要框预测圈时。'}[key]
                if issues[2]:action='继续完成标定'
                else:
                    title='必要标定已完成'
                    detail='检查覆盖线贴合油刹刻度、固定文字不含变化数字；确认后点击“下一步：检查并提取”。'
        else:
            title='检查完成后，再开始提取';detail=first[2] if first else '准备就绪。提取只在本机进行；完成后先打开报告检查缺口与油刹变化，结果仍是视频估算。'
            action='修正未完成项' if first else '重新提取' if self.result else '开始提取'
        self.guide_heading.set(tr(title));self.guide_detail.set(tr(detail))
        if not self.busy:self.start.configure(text=action,state='normal')
        self.back.configure(state='normal' if page and not self.busy else 'disabled')
        for var,title,issue in zip(self.review_values,['视频与赛道','完整一圈','油刹与固定文字','额外同步条件'],issues):
            var.set(('○ ' if issue else '✓ ')+tr(title)+' · '+(tr(issue[2]) if issue else tr('已准备好')))
        if self.result:
            q=self.result.get('quality');self.result_note.set(tr('报告已保存。先点“打开结果”查看曲线与缺口；需要比较时，再使用下面的对比入口。')+(' '+tr('缺失样本')+f" {q.get('missing_samples',0)}" if q else ''))
        else:self.result_note.set(tr('提取后会保存独立报告、CSV、JSON 和标定。先看报告中的缺口与质量说明，再决定是否用于对比。'))

    def go_issue(self,issue):
        key,page,detail=issue;self.tabs.select(page);self.status.set(tr(detail))
        if key=='video':self.choose('video','video')
        elif key=='preview':self.read_preview(select=False)
        elif key=='identity':
            if not self.manual_body.winfo_manager():self.toggle_manual()
            self.field_widgets['track'].focus_set()
        elif key=='sample':
            start=clock(self.fields['start'].get());end=clock(self.fields['end'].get());self.request_frame(min(end-.05,start+.05))
        elif key=='confirm':self.range_check.focus_set()
        elif key=='range':self.seek_scale.focus_set()
        elif key=='resolution':self.read_preview()
        elif key in NAMES:
            if self.target.get()!=key:self.target.set(key);self.target_changed()
            if key in self.geometry and not self.calibration_options.winfo_manager():self.toggle_calibration_options()
        elif key in ('telemetry','sync'):
            if not self.advanced_body.winfo_manager():self.toggle_advanced()
            (self.field_widgets['telemetry'] if key=='telemetry' else self.sync).focus_set()
        self.queue_guidance()

    def primary_action(self):
        if self.busy:return
        page=self.tabs.current
        if page==0:
            issue=self.setup_issue()
            if issue:self.go_issue(issue)
            else:self.next_preview()
        elif page==1:
            issue=self.setup_issue() or self.range_issue() or self.calibration_issue()
            if issue:self.go_issue(issue)
            else:self.tabs.select(2)
        else:
            issue=next((item for item in self.issues() if item),None)
            if issue:self.go_issue(issue)
            else:self.run()

    def previous_step(self):
        if not self.busy:self.tabs.select(max(0,self.tabs.current-1))

    def toggle_calibration_options(self):
        if self.calibration_options.winfo_manager():self.calibration_options.pack_forget()
        else:self.calibration_options.pack(fill='x')

    def toggle_advanced(self):
        if self.advanced_body.winfo_manager():self.advanced_body.pack_forget()
        else:self.advanced_body.pack(fill='x',before=self.result_card)

    def show_help(self):
        if self.help_window is not None and self.help_window.winfo_exists():self.help_window.lift();return
        from control_video_widgets import ScrollPage,Action
        top=tk.Toplevel(self.window);self.help_window=top;top.title(tr('视频提取 · 操作示意'));top.geometry('760x650');top.minsize(620,480);top.configure(bg=T.BG)
        Action(top,'看懂了，返回标定',top.destroy,190,True).pack(side='bottom',pady=12)
        page=ScrollPage(top);page.pack(fill='both',expand=True,padx=18,pady=12)
        top.bind('<MouseWheel>',lambda e:page.wheel(e.delta))
        top.bind('<Next>',lambda _:page.scroll_to('scroll',1,'pages'))
        top.bind('<Prior>',lambda _:page.scroll_to('scroll',-1,'pages'))
        def paragraph(title,body):
            Label(page.body,text=title,bg=T.BG,fg=T.FG,font=(T.FONT,12,'bold'),anchor='w').pack(fill='x',pady=(14,5))
            label=Label(page.body,text=body,bg=T.BG,fg=T.MUTED,font=(T.FONT,10),justify='left',anchor='w');label.pack(fill='x');label.bind('<Configure>',lambda e:label.configure(wraplength=max(200,e.width)))
        paragraph('1 · 先标一圈','拖到起点经过标线的画面，设为圈起点；再拖到下一次经过同一标线的画面，设为圈终点。两个位置的判断方法要一致，不要用不同圈的刹车点。')
        paragraph('2 · 油门与刹车，各点三下','先点几何圆心，再点 0% 起点、100% 终点。油门和刹车可能不同圆心、不同半径，必须分别标定；红色转速环不是刹车。')
        diagram=tk.Canvas(page.body,height=150,bg=T.CARD,highlightthickness=0);diagram.pack(fill='x',pady=10)
        diagram.create_arc(120,25,240,145,start=45,extent=90,style='arc',outline=T.GREEN,width=7)
        diagram.create_oval(177,82,183,88,fill=T.ACCENT,outline='');diagram.create_text(205,103,text=tr('① 几何圆心'),fill=T.FG,anchor='w')
        diagram.create_line(224,41,270,30,fill=T.MUTED);diagram.create_line(136,41,115,30,fill=T.MUTED)
        diagram.create_text(280,30,text=tr('② 0% 起点'),fill=T.FG,anchor='w');diagram.create_text(12,17,text=tr('③ 100% 终点'),fill=T.FG,anchor='w')
        paragraph('3 · 框住固定文字','在不变的 KPH 等文字外拖一个小框。车速数字、挡位、圈时会变化，不能作为固定文字。锚点用于判断 HUD 是否可见；缺失不能当作油刹为零。')
        paragraph('覆盖线不对怎么办？','先用撤销修改误点；整项不对可重做。覆盖线绕了长弧时，展开方向与弧宽切换顺/逆时针；线偏离真实弧中心时重选圆心与端点。弧宽按原视频像素设置。')
        paragraph('画面放大后怎么移动？','滚轮围绕鼠标位置缩放；右键或中键按住拖动画面，Shift + 滚轮横向移动。点过画面后，也可按住空格再左键拖动。平移不会增加标定点；“适合视窗”恢复全图。放大只便于选点，不增加原始视频精度。')
        paragraph('为什么油门和刹车都在左侧？','部分 LMU HUD 把绿色油门和红色刹车放在左侧相邻半径，右侧外环可能是转速。分别选择正在给油和正在制动的画面，再核对各自圆弧，不要根据左右位置猜测。')
        paragraph('完成后先看什么？','打开报告，看是否有缺口、油刹是否与画面大致一致。可读率不是正确率；没有同圈原生遥测时，不能宣称绝对识别精度。原视频与历史赛事不会被改写。')
