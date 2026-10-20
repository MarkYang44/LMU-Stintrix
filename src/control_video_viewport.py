"""Direct calibration navigation; original-video coordinates never change."""
import math


class VideoViewport:
    def install_viewport(self):
        self.pan_active=False;self.space_pan=False
        for button in (2,3):
            self.canvas.bind(f'<ButtonPress-{button}>',self.begin_pan)
            self.canvas.bind(f'<B{button}-Motion>',self.move_pan)
            self.canvas.bind(f'<ButtonRelease-{button}>',self.end_pan)
        self.canvas.bind('<MouseWheel>',self.preview_wheel)
        self.canvas.bind('<Shift-MouseWheel>',self.preview_wheel)
        self.canvas.bind('<KeyPress-space>',self.space_down)
        self.canvas.bind('<KeyRelease-space>',self.space_up)
        self.canvas.bind('<FocusOut>',self.cancel_pan)

    def space_down(self,_):
        self.space_pan=True;self.canvas.configure(cursor='fleur');return 'break'

    def space_up(self,_):
        self.space_pan=False
        if not self.pan_active:self.canvas.configure(cursor='crosshair')
        return 'break'

    def cancel_pan(self,_=None):
        self.pan_active=False;self.space_pan=False;self.canvas.configure(cursor='crosshair')

    def begin_pan(self,event):
        if self.image is None:return 'break'
        self.canvas.focus_set();self.pan_active=True;self.drag=None;self.canvas.delete('drag');self.canvas.configure(cursor='fleur')
        self.canvas.scan_mark(event.x,event.y);return 'break'

    def move_pan(self,event):
        if self.pan_active:
            self.canvas.scan_dragto(event.x,event.y,gain=1);self.draw_preview_bitmap()
        return 'break'

    def end_pan(self,_):
        self.pan_active=False;self.canvas.configure(cursor='fleur' if self.space_pan else 'crosshair');return 'break'

    def scroll_preview(self,axis,*args):
        getattr(self.canvas,axis+'view')(*args);self.draw_preview_bitmap()

    def preview_wheel(self,event):
        if self.image is None:return 'break'
        if event.state & 1:
            # Pixel travel scales with the viewport, not the size of a huge bitmap.
            width=max(1,self.image.width*self.zoom.get())
            self.canvas.xview_moveto((self.canvas.canvasx(0)-event.delta/120*80)/width)
            self.draw_preview_bitmap()
        else:self.set_preview_zoom(self.zoom.get()*1.16**(max(-4,min(4,event.delta/120))),event.x,event.y)
        return 'break'

    def set_preview_zoom(self,value,x=None,y=None):
        if self.image is None:return
        self.preview_fit=False
        if self.fit_job:self.window.after_cancel(self.fit_job);self.fit_job=None
        old=self.preview_key[1] if self.preview_key and self.preview_key[0]==id(self.image) else self.zoom.get()
        x=self.canvas.winfo_width()/2 if x is None else x;y=self.canvas.winfo_height()/2 if y is None else y
        source_x=self.canvas.canvasx(x)/old;source_y=self.canvas.canvasy(y)/old
        value=round(max(.1,min(12,float(value))),4);self.zoom.set(value)
        width=max(1,round(self.image.width*value));height=max(1,round(self.image.height*value))
        self.canvas.configure(scrollregion=(0,0,width,height))
        self.canvas.xview_moveto((source_x*value-x)/width);self.canvas.yview_moveto((source_y*value-y)/height)
        self.redraw()

    def draw_preview_bitmap(self):
        if self.image is None:return
        from PIL import ImageTk
        zoom=self.zoom.get();width=max(1,round(self.image.width*zoom));height=max(1,round(self.image.height*zoom))
        self.canvas.configure(scrollregion=(0,0,width,height))
        # Render only the visible crop plus an overscan margin. Even 12x does not
        # allocate a 13440px-wide Tk image or reduce the retained source preview.
        x0=max(0,math.floor((self.canvas.canvasx(0)-32)/zoom));y0=max(0,math.floor((self.canvas.canvasy(0)-32)/zoom))
        x1=min(self.image.width,math.ceil((self.canvas.canvasx(0)+self.canvas.winfo_width()+32)/zoom))
        y1=min(self.image.height,math.ceil((self.canvas.canvasy(0)+self.canvas.winfo_height()+32)/zoom))
        if x1<=x0 or y1<=y0:return
        key=(id(self.image),zoom,x0,y0,x1,y1)
        if key==self.preview_key:return
        x=round(x0*zoom);y=round(y0*zoom);right=round(x1*zoom);bottom=round(y1*zoom)
        patch=self.image.crop((x0,y0,x1,y1)).resize((max(1,right-x),max(1,bottom-y)))
        self.photo=ImageTk.PhotoImage(patch,master=self.window)
        self.canvas.delete('bitmap');self.canvas.create_image(x,y,image=self.photo,anchor='nw',tags='bitmap');self.canvas.tag_lower('bitmap')
        self.preview_key=key

    def nudge_preview(self,delta):
        if not self.media:return
        if self.busy and not self.preview_loading:return
        # Base repeated requests on the pending target, not a stale decoded frame.
        value=max(0,min(self.media['duration']-.001,self.seek.get()+delta))
        self.seek.set(value);self.seek_changed(value);self.request_frame(value)
