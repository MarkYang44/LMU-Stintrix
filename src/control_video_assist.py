"""Fewer wizard actions: automatic preview, visual lap range, reusable HUD drafts."""
import copy
from collections import OrderedDict
from pathlib import Path
import tkinter as tk
from video_signal import clock


class VideoAssist:
    def init_assist(self):
        self.seek=tk.DoubleVar(self.window,value=0);self.seek_text=tk.StringVar(self.window,value='0.000 s')
        self.media_hint=tk.StringVar(self.window,value='选择文件后自动读取预览和时长。普通视频保持默认输入条件即可。')
        self.undo_stack=[];self.loaded_sample=None;self.seek_job=None;self.preview_pending=None;self.preview_loading=False
        self.preview_cache=OrderedDict();self.preview_media_stamp=None

    def preview_stamp(self,path,directory):
        try:
            file=Path(path).resolve();stamp=file.stat()
            return str(file),stamp.st_size,stamp.st_mtime_ns,str(directory)
        except OSError:return None

    def remember_preview(self,key,result):
        if key is None:return
        self.preview_cache[key]=result;self.preview_cache.move_to_end(key)
        # RGB previews only; never retain full-resolution video frames.
        while len(self.preview_cache)>3 or sum(image.width*image.height*3 for _,image in self.preview_cache.values())>12*1024*1024:
            self.preview_cache.popitem(last=False)

    def infer_layout(self):
        if self.fields['track'].get().strip():return
        from video_preferences import infer_identity
        label=infer_identity(self.fields['video'].get(),self.identities)
        if label:self.identity.set(label);self.use_identity()

    def toggle_manual(self):
        if self.manual_body.winfo_manager():self.manual_body.pack_forget()
        else:self.manual_body.pack(fill='x')

    def toggle_tools(self):
        if self.tools_body.winfo_manager():self.tools_body.pack_forget()
        else:self.tools_body.pack(fill='x')

    def selected_video(self):
        if self.seek_job:self.window.after_cancel(self.seek_job);self.seek_job=None
        self.preview_pending=None;self.clicks=[];self.drag=None
        self.preview_fit=True
        self.preview_cache.clear();self.preview_media_stamp=None;self.loaded_sample=None
        self.geometry={};self.calibration_size=None;self.image=None;self.media=None;self.photo=None;self.preview_key=None
        self.undo_stack=[];self.result=None;self.open.configure(state='disabled')
        for key,value in (('start','0'),('end',''),('sample','0')):self.fields[key].set(value)
        self.identity.set('')
        for key in ('track','layout','length'):self.fields[key].set('')
        self.canvas.delete('all');self.empty_preview();self.infer_layout();self.read_preview(select=False)

    def read_preview(self,select=True):
        if self.busy:return
        try:
            path=self.fields['video'].get();seconds=clock(self.fields['sample'].get());directory=self.fields['ffmpeg'].get()
        except ValueError as error:self.status.set(str(error));return
        stamp=self.preview_stamp(path,directory);key=(stamp,seconds) if stamp is not None else None
        cached=self.preview_cache.get(key) if key is not None else None
        known_media=self.media if stamp is not None and stamp==self.preview_media_stamp else None
        def work(cancel,_):
            from video_media import probe,preview
            media=known_media or probe(path,directory,cancel)
            if seconds>=media['duration']:raise ValueError('预览时间超出视频时长')
            return media,preview(path,seconds,directory,cancel)
        def done(result):
            self.remember_preview(key,result)
            if self.preview_pending is not None:
                pending=self.preview_pending;self.preview_pending=None
                if pending!=seconds:
                    self.seek_job=self.window.after_idle(lambda:self.request_frame(pending))
                    return False
            same_view=self.image is not None and self.image.size==result[1].size and self.media is not None and self.media['path']==result[0]['path']
            self.media,self.image=result;self.loaded_sample=seconds
            self.preview_media_stamp=stamp
            if not self.fields['end'].get().strip():self.fields['end'].set(f"{self.media['duration']:.6f}")
            if self.calibration_size and self.calibration_size!=[self.media['width'],self.media['height']]:self.geometry={};self.calibration_size=None
            reused=False
            if not self.geometry:
                from video_preferences import load,match
                profile=match(load(self.root),self.image,self.media)
                if profile:
                    self.apply_geometry(profile);reused=True
            self.seek_scale.configure(to=max(.001,self.media['duration']-.001));self.seek.set(seconds);self.seek_changed(seconds)
            self.infer_layout()
            if select:self.tabs.select(self.calibration)
            clicks=self.clicks[:]
            if self.preview_fit or not same_view:self.fit_preview()
            self.target_changed();self.clicks=clicks;self.redraw()
            self.media_hint.set(f"{self.media['width']} × {self.media['height']} · {self.media['duration']:.3f} 秒；圈段可在预览条上设置。")
            self.status.set('已自动复用上次 HUD 标定，请检查覆盖线后提取。' if reused else '预览已就绪。选择赛道布局后，在第 2 步拖动时间条设置圈段并标定 HUD。')
        if cached is not None:
            self.preview_cache.move_to_end(key);done(cached);return
        self.preview_loading=True;self.dispatch(work,done,'正在读取视频预览…',with_state=True,preview=True)

    def apply_geometry(self,value):
        self.geometry={k:copy.deepcopy(value[k]) for k in ('throttle','brake','anchor','distance_box','timer_box') if k in value}
        self.calibration_size=value.get('frame_size')
        for key in self.clockwise:
            if key in value:self.clockwise[key].set(value[key].get('clockwise',True))
        self.thickness.set(str(value.get('throttle',{}).get('thickness',6)))

    def next_preview(self):
        if self.busy:return
        try:seconds=clock(self.fields['sample'].get())
        except ValueError as error:self.status.set(str(error));return
        if self.media and Path(self.fields['video'].get()).resolve()==Path(self.media['path']) and self.loaded_sample==seconds:
            self.tabs.select(self.calibration);self.fit_preview()
        else:self.load_preview()

    def seek_changed(self,value):self.seek_text.set(f'{float(value):.3f} s')

    def request_frame(self,seconds=None):
        self.seek_job=None
        if not self.media:return
        seconds=self.seek.get() if seconds is None else seconds
        if self.busy:
            if self.preview_loading:self.preview_pending=seconds
            return
        self.fields['sample'].set(f'{seconds:.6f}');self.read_preview()

    def mark_range(self,edge):
        if self.busy or self.loaded_sample is None:return
        self.fields[edge].set(f'{self.loaded_sample:.6f}')
        self.status.set('已设置圈'+('起点' if edge=='start' else '终点')+'；请确认这是同一完整圈的过线位置。')
        if edge=='end':
            try:start=clock(self.fields['start'].get())
            except ValueError:return
            if self.loaded_sample>start:
                # The endpoint is exclusive during extraction. Keep the calibration
                # frame inside the selected lap without another manual operation.
                self.request_frame(max(start,self.loaded_sample-.05))

    def save_undo(self):
        self.undo_stack.append((copy.deepcopy(self.geometry),self.target.get(),copy.deepcopy(self.clicks)))
        self.undo_stack=self.undo_stack[-12:]

    def undo_calibration(self):
        if self.busy or not self.undo_stack:return
        self.geometry,target,self.clicks=self.undo_stack.pop();self.target.set(target);self.redraw()
        self.hint.set('已撤销上一步，继续点击或重新框选。')

    def advance_target(self):
        keys=['throttle','brake','anchor']+(['distance_box','timer_box'] if self.mode.get().startswith('距离') else [])
        key=next((k for k in keys if k not in self.geometry),None)
        if key:self.target.set(key);self.target_changed()
        else:self.clicks=[];self.status.set('必要标定已完成。核对覆盖线、圈段及布局后，点击“开始提取”。')
