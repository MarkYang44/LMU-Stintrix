"""Responsive desktop frame and animated navigation, separate from session logic."""
from i18n import tr,Label
import tkinter as tk
from control_theme import T
from tkinter import ttk,font as tkfont
from control_motion import Motion,SmoothScroll,keyboard_action
from control_widgets import rounded,polygon_points,scale,px,Pill
import branding
from control_feedback import StatusFeedback

# The rail reads as the product's map. Each stable page ID belongs to a group
# that opens with a short caption; '' pins the entry to the rail's foot, where
# people look for settings in every desktop app.
GROUPS={0:'实时',1:'分析',6:'分析',4:'资料',5:'资料',3:'工具',2:''}
# Offline preferences replace the settings page, so they keep its glyph.
GLYPHS={'运行与 HUD':0,'赛事复盘':1,'设置':3,'采样与遥测':3,'离线偏好设置':3,'图像与数据':4,'赛道指南':5,'车型图鉴':6,'个人赛道纪录':7}


def symbol(canvas,kind,x,y,s,color):
    def line(*v):canvas.create_line(*[n*s+(x if i%2==0 else y) for i,n in enumerate(v)],fill=color,width=max(1,1.5*s),capstyle='round',joinstyle='round')
    if kind==0:line(0,13,5,13,8,3,12,20,16,8,23,8)
    elif kind==1:
        for row,width in enumerate((23,16,20)):line(0,row*8,width,row*8)
    elif kind==2:line(0,19,5,13,9,16,14,3,19,8,24,0);line(0,6,6,3,12,9,18,17,24,12)
    elif kind==3:
        for i,p in enumerate((5,15,9)):line(i*8,0,i*8,22);line(i*8-3,p,i*8+3,p)
    elif kind==5:line(3,16,0,9,4,0,14,2,23,13,18,22,6,20,3,16)
    elif kind==6:
        line(0,15,3,5,8,5,11,1,18,1,21,5,24,5,27,15,0,15);line(5,15,5,20,10,20,10,15);line(18,15,18,20,23,20,23,15)
    elif kind==7:
        line(5,0,19,0,18,13,12,17,6,13,5,0);line(5,3,0,3,1,10,6,12);line(19,3,24,3,23,10,18,12);line(12,17,12,22);line(6,22,18,22)
    else:
        line(0,5,8,5,11,0,21,0,24,5,24,21,0,21,0,5);line(9,12,15,12);line(12,9,12,15)


class Navigation(tk.Canvas):
    """Grouped page rail: captions name each area, settings rest at the foot.

    Rows keep one comfortable height; a short window first drops the group
    captions (small gaps still separate the groups), then tightens the rows.
    """
    ROW=42;CAPTION=25;MINIMUM=34
    def __init__(self,parent,names,command,ids=None):
        self.s=scale(parent);self.names=names;self.command=command;self.selected=0;self.position=0;self.marker_amount=1.;self.hovered=-1;self.paint_key=None
        self.ids=tuple(ids) if ids is not None else tuple(range(len(names)))
        self.step=self.ROW*self.s;self.boxes=[];self.captioned=True
        super().__init__(parent,bg=T.RAIL,height=round(self.natural()),highlightthickness=0,takefocus=True,cursor='hand2')
        self.motion=Motion(self);self.bind('<Configure>',lambda _:self.paint());self.bind('<Motion>',self.hover);self.bind('<Leave>',self.leave)
        self.bind('<Button-1>',self.click);self.bind('<Up>',lambda _:keyboard_action(self,lambda:self.command(max(0,self.selected-1))))
        self.bind('<Down>',lambda _:keyboard_action(self,lambda:self.command(min(len(names)-1,self.selected+1))))
        from control_tooltip import Tooltip
        self.tip=Tooltip(self)
    def groups(self):return [GROUPS.get(page,'工具') for page in self.ids]
    def natural(self):
        groups=self.groups();captions=len({g for g in groups if g})
        return len(self.names)*self.ROW*self.s+captions*self.CAPTION*self.s+(18*self.s if '' in groups else 0)
    def arrange(self,height):
        """(boxes, captions, rule) for this height; boxes are (top, height) per entry."""
        s=self.s;groups=self.groups();count=len(self.names)
        main=[i for i,g in enumerate(groups) if g];pinned=[i for i,g in enumerate(groups) if not g]
        names=[];[names.append(groups[i]) for i in main if groups[i] not in names]
        gap=18*s if pinned else 0
        if height<=1 or height>=self.natural():step=self.ROW*s;captioned=True
        else:
            captioned=False;room=height-max(0,len(names)-1)*8*s-gap
            step=max(self.MINIMUM*s,min(self.ROW*s,room/max(1,count)))
        boxes=[(0,step)]*count;captions=[];y=0;previous=None
        for i in main:
            if groups[i]!=previous:
                if captioned:captions.append((y,groups[i]));y+=self.CAPTION*s
                elif previous is not None:y+=8*s
                previous=groups[i]
            boxes[i]=(y,step);y+=step
        rule=None
        if pinned:
            bottom=max(y+gap,height-len(pinned)*step);rule=bottom-gap/2
            for i in pinned:boxes[i]=(bottom,step);bottom+=step
        return boxes,captions,rule,step,captioned
    def index_at(self,y):
        return next((i for i,(top,h) in enumerate(self.boxes) if top<=y<top+h),-1)
    def click(self,event):
        index=self.index_at(event.y);self.tip.hide()
        if 0<=index<len(self.names):self.focus_set();self.command(index)
    def hover(self,event):
        index=self.index_at(event.y)
        if self.hovered!=index:self.hovered=index;self.paint()
        # A delayed hint teaches each entry's Ctrl+number shortcut; once one
        # is open, neighbouring entries answer at once while scanning.
        if 0<=index<len(self.names):
            from platform_runtime import shortcut_hint
            text=tr(self.names[index])+'  ·  '+shortcut_hint('Ctrl+'+str(index+1))+('  ·  '+tr('记录中') if index==0 and getattr(self,'live',False) else '')
            top,h=self.boxes[index]
            self.tip.request(index,text,self.winfo_rootx()+self.winfo_width(),round(self.winfo_rooty()+top+h/2))
        else:self.tip.hide()
    def leave(self,_):self.hovered=-1;self.paint();self.tip.hide()
    def select(self,index):
        # Commit the selected row immediately; animate only its accent, never
        # slide a stale highlight across the previously selected menu entries.
        if self.selected==index:return
        self.position=index;self.selected=index;start=self.marker_amount if self.motion.jobs else .25;self.marker_amount=start;self.paint()
        def frame(t):self.marker_amount=start+(1-start)*t;self.paint()
        self.motion.animate('selection',frame,125)
    def paint(self):
        import i18n
        s=self.s;w=self.winfo_width();h=self.winfo_height()
        self.boxes,captions,rule,self.step,self.captioned=self.arrange(h)
        top,row=self.boxes[self.position];inset=4*s
        key=(w,h,self.selected,self.hovered,T.mode,i18n.language,getattr(self,'live',False),getattr(self,'compact_indices',False))
        if self.paint_key==key:
            self.coords(self.highlight,*polygon_points(0,top+inset,w-1,row-2*inset,8*s))
            self.coords(self.marker,*polygon_points(0,top+(row-22*s)/2,3*s,22*s*self.marker_amount,1*s))
            return
        self.paint_key=key;self.delete('all')
        caption_width=max(int(self.tk.call('font','measure',(T.FONT,11,'bold'),tr(name))) for name in self.names)
        numbers=not getattr(self,'compact_indices',False) and w>=57*s+caption_width+40*s
        for y,text in captions:self.create_text(19*s,y+self.CAPTION*s-7*s,text=tr(text),anchor='sw',fill=T.MUTED,font=(T.FONT,9))
        if rule is not None:self.create_line(12*s,rule,w-12*s,rule,fill=T.EDGE)
        self.highlight=rounded(self,0,top+inset,w-1,row-2*inset,8*s,fill=T.SELECT,outline=T.MARK)
        self.marker=rounded(self,0,top+(row-22*s)/2,3*s,22*s*self.marker_amount,1*s,fill=T.ACCENT,outline='')
        for i,name in enumerate(self.names):
            box_top,box=self.boxes[i];y=box_top+box/2;color=T.FG if i==self.selected else T.MUTED
            if i==self.hovered and i!=self.selected:
                rounded(self,4*s,box_top+inset+1*s,w-9*s,box-2*inset-2*s,8*s,fill=T.HOVER,outline='');color=T.FG
            kind=GLYPHS.get(name,i)
            symbol(self,kind,19*s,y-10*s,s,T.ACCENT if i==self.selected else color)
            self.create_text(57*s,y,text=tr(name),anchor='w',fill=color,font=(T.FONT,11,'bold' if i==self.selected else 'normal'))
            if numbers:self.create_text(w-12*s,y,text=f'{i + 1:02}',anchor='e',fill=T.ACCENT if i==self.selected else T.MUTED,font=(T.MONO,8))
            if i==0 and getattr(self,'live',False):
                # A small recording dot on the run entry, readable from any page.
                self.create_oval(38*s,y-15*s,45*s,y-8*s,fill=T.RED,outline=T.RAIL,width=max(1,1.5*s),tags='live')


class Shell:
    def __init__(self,root,names,command,status,on_theme=None,on_language=None,on_palette=None,page_ids=None):
        self.page_ids=tuple(page_ids) if page_ids is not None else tuple(range(len(names)))
        self.root=root;self.s=s=scale(root);self.compact=False
        self.brand_font=tkfont.Font(root,family=T.LATIN,size=23,weight='bold')
        self.rail_width=max(round(252*s),max(self.brand_font.measure('Stintrix'),*(tkfont.Font(root,family=T.FONT,size=11,weight='bold').measure(tr(name)) for name in names))+round(100*s))
        available_w=max(800,root.winfo_screenwidth()-round(70*s));available_h=max(600,root.winfo_screenheight()-round(100*s))
        if not getattr(root,'_stintrix_shell_sized',False):
            root.geometry(f'{min(round(1240*s),available_w)}x{min(round(850*s),available_h)}');root._stintrix_shell_sized=True
        root.minsize(min(round(1060*s),available_w),min(round(700*s),available_h))
        self.side=side=tk.Frame(root,bg=T.RAIL,width=self.rail_width);side.pack(side='left',fill='y');side.pack_propagate(False)
        self.brand=tk.Canvas(side,bg=T.RAIL,highlightthickness=0,height=round(130*s));self.brand.pack(fill='x',padx=round(25*s),pady=(round(22*s),round(4*s)))
        self.brand.bind('<Configure>',self.paint_brand)
        self.logo=None;self.logo_source=None;self.logo_width=None;self.context=None
        self.brand.bind('<Destroy>',self.release_brand,add='+')
        try:
            from PIL import Image,ImageOps,ImageTk
            with Image.open(branding.directory()/('menu-icon-light.png' if T.mode=='light' else 'menu-icon.png')) as artwork:
                self.logo_source=artwork.convert('RGBA');image=ImageOps.contain(self.logo_source,(self.rail_width-round(50*s),round(64*s)),Image.Resampling.LANCZOS)
                self.logo=ImageTk.PhotoImage(image,master=root)
        except (OSError,tk.TclError):pass
        import i18n
        from control_widgets import Segmented,release_with
        # Global controls live on the rail: the page header belongs to the page.
        self.palette_button=None
        if on_palette is not None:
            # One visible door to the command palette; Ctrl+K opens it anywhere.
            from control_palette import SearchPill
            self.palette_button=SearchPill(side,on_palette);self.palette_button.configure(height=round(40*s))
            self.palette_button.pack(fill='x',padx=round(16*s),pady=(round(6*s),round(10*s)))
        foot=tk.Frame(side,bg=T.RAIL);foot.pack(side='bottom',fill='x',padx=round(16*s),pady=(round(10*s),round(20*s)))
        # Theme and language show their current state, not the target of a
        # click: the other half switches, like every segmented choice. One
        # short row at every rail width, so the page groups keep their captions.
        toggles=tk.Frame(foot,bg=T.RAIL);toggles.pack(fill='x',pady=(0,round(10*s)));self.toggles=toggles
        def segmented(variable,values,command,captions,titles,icons=None):
            control=Segmented(toggles,variable,values,command,captions,titles,icons)
            control.configure(height=round(34*s),width=1)
            release_with(control,variable);return control
        # Settings mirrors these two; the shell alone retires them (see control_disposal).
        self.theme_var=tk.StringVar(root,value=T.mode);self.theme_var.shared=True
        self.theme_button=segmented(self.theme_var,['dark','light'],on_theme or (lambda:None),{'dark':'深色','light':'浅色'},{'dark':'深色主题','light':'浅色主题'},{'dark':'moon','light':'sun'})
        self.theme_button.configure(width=round(72*s))
        self.language_var=tk.StringVar(root,value=i18n.language);self.language_var.shared=True
        self.language_button=segmented(self.language_var,['zh','en'],on_language or (lambda:None),{'zh':'中文','en':'EN'},{'zh':'中文界面','en':'English interface'})
        toggles.columnconfigure(1,weight=1)
        self.theme_button.grid(row=0,column=0,sticky='w',padx=(0,round(6*s)))
        self.language_button.grid(row=0,column=1,sticky='ew')
        # The recording policy lives beside the start controls; the rail keeps
        # only the privacy promise under the global toggles.
        Label(foot,text='●  LOCAL & PRIVATE',bg=T.RAIL,fg=T.ACCENT,font=(T.LATIN,9,'bold'),anchor='w').pack(fill='x',padx=round(9*s))
        self.footer=foot
        self.navigation=Navigation(side,names,lambda index:command(self.page_ids[index]),self.page_ids)
        self.navigation.pack(fill='both',expand=True,padx=round(16*s))
        side.bind('<Configure>',self.layout_sidebar)
        self.main=main=tk.Frame(root,bg=T.BG);main.pack(side='left',fill='both',expand=True,padx=round(28*s),pady=(round(22*s),round(14*s)))
        self.motion=Motion(main)
        head=tk.Frame(main,bg=T.BG);head.pack(fill='x',pady=(0,round(14*s)))
        top=tk.Frame(head,bg=T.BG);top.pack(fill='x')
        # Retained for compatibility only: the page title now heads this row.
        self.breadcrumb=Label(top,text='STINTRIX  /  CONTROL CENTER',font=(T.LATIN,9,'bold'),bg=T.BG,fg=T.ACCENT,anchor='w')
        # The title names the page; a muted line says what the page is for.
        self.title=Label(top,font=(T.FONT,20,'bold'),bg=T.BG,fg=T.FG,anchor='w');self.title.pack(side='left',fill='x',expand=True)
        self.subtitle=Label(head,font=(T.FONT,9),bg=T.BG,fg=T.MUTED,anchor='w');self.subtitle.pack(fill='x',pady=(round(3*s),0))
        self.subtitle.bind('<Configure>',lambda e:self.subtitle.configure(wraplength=e.width))
        footer=tk.Frame(main,bg=T.BG);footer.pack(side='bottom',fill='x',pady=(round(12*s),0))
        self.status_feedback=StatusFeedback(footer,status);self.status_feedback.pack(side='left',fill='x',expand=True)
        from paths import app_version
        version=app_version()
        Label(footer,text='STINTRIX  v'+version,font=(T.MONO,8),bg=T.BG,fg=T.MUTED).pack(side='right')
        self.stage=tk.Frame(main,bg=T.BG);self.stage.pack(fill='both',expand=True)
        # View tabs (records views, data tasks) sit above the page actions and
        # stay put while views change or the page scrolls.
        self.tab_host=tk.Frame(self.stage,bg=T.BG)
        self.action_host=tk.Frame(self.stage,bg=T.BG)
        self.action_host.pack(fill='x',pady=(0,8))
        # A page's selection tray (the guide's comparison) rests under the
        # document, visible wherever the reader has scrolled.
        self.tray_host=tk.Frame(self.stage,bg=T.BG)
        self.width_binding=root.bind('<Configure>',self.layout_width,add='+')
        viewport=tk.Frame(self.stage,bg=T.BG);viewport.pack(fill='both',expand=True)
        self.scroll=tk.Canvas(viewport,bg=T.BG,highlightthickness=0)
        self.scroller=SmoothScroll(self.scroll,lambda:self.scroll.canvasy(0),
            lambda:max(0,self.content.winfo_height()-self.scroll.winfo_height()),
            lambda value:self.scroll.yview_moveto(value/max(1,self.content.winfo_height())))
        bar=ttk.Scrollbar(viewport,orient='vertical',command=self.scrollbar,style='Lab.Vertical.TScrollbar');self.bar=bar
        bar.pack(side='right',fill='y',padx=(round(8*s),0));self.scroll.pack(side='left',fill='both',expand=True)
        # Pages may follow the reading position (settings section tabs).
        self.scroll_listeners=[]
        def scrolled(*args):
            bar.set(*args)
            # A page that fits shows no thumb: a full-height bar only reads as a stray rule.
            try:idle=float(args[0])<=0 and float(args[1])>=1
            except (IndexError,ValueError):idle=False
            style='Lab.Idle.Vertical.TScrollbar' if idle else 'Lab.Vertical.TScrollbar'
            if str(bar.cget('style'))!=style:bar.configure(style=style)
            for listener in list(self.scroll_listeners):listener()
        self.scroll.configure(yscrollcommand=scrolled)
        self.content=tk.Frame(self.scroll,bg=T.BG);self.item=self.scroll.create_window(0,0,anchor='nw',window=self.content)
        self.scroll.bind('<Configure>',lambda e:self.scroll.itemconfigure(self.item,width=e.width))
        self.content.bind('<Configure>',lambda e:self.scroll.configure(scrollregion=(0,0,e.width,e.height)))
        from control_surface import Surface
        self.surface=Surface(self.stage)
    def release_brand(self,event):
        if event.widget is self.brand:
            self.logo=None;self.brand_font.__del__();self.brand_font.delete_font=False
    def refresh_brand(self):
        from PIL import Image
        try:
            with Image.open(branding.directory()/('menu-icon-light.png' if T.mode=='light' else 'menu-icon.png')) as artwork:self.logo_source=artwork.convert('RGBA')
        except OSError:self.logo_source=None;self.logo=None
        self.logo_width=None;self.paint_brand()
    def attach_context(self,widget):
        """Show one context control (the game switcher) under the logo."""
        self.context=widget;self.paint_brand()
    def paint_brand(self,_=None):
        c=self.brand;s=self.s;c.delete('all')
        width=c.winfo_width();logo_height=round((52 if self.compact else 64)*s)
        if self.logo_source is not None and width>1 and (width,logo_height)!=self.logo_width:
            from PIL import ImageOps,ImageTk
            self.logo=ImageTk.PhotoImage(ImageOps.contain(self.logo_source,(max(1,width),logo_height)),master=self.root);self.logo_width=(width,logo_height)
        if self.logo:c.create_image(0,0,image=self.logo,anchor='nw')
        if not self.logo:c.create_text(0,logo_height*.8,text='Stintrix',font=self.brand_font,fill=T.FG,anchor='w')
        context=self.context if self.context is not None and self.context.winfo_exists() else None
        if context is not None:
            # The switcher replaces the static game caption: one control, one name.
            top=logo_height+round(10*s);c.create_window(0,top,anchor='nw',window=context,width=max(1,width))
            line=top+context.winfo_reqheight()+round(12*s)
        else:
            from app_config import SIMULATOR
            from simulators import GAMES
            c.create_text(1*s,logo_height+18*s,text=GAMES[SIMULATOR].upper(),font=(T.LATIN,9,'bold'),fill=T.MUTED,anchor='w')
            line=logo_height+34*s
        right=c.winfo_width()
        c.create_line(0,line,right,line,fill=T.EDGE);c.create_line(0,line,44*s,line,fill=T.ACCENT,width=2*s)
        height=round(line+2*s)
        if int(c.cget('height'))!=height:c.configure(height=height)
    def scrollbar(self,*args):
        self.scroller.cancel();self.scroll.yview(*args)
    def detach(self):
        if getattr(self,'width_binding',None):self.root.unbind('<Configure>',self.width_binding);self.width_binding=None

    def layout_width(self,event):
        if event.widget is not self.root or not self.side.winfo_exists():return
        import i18n
        compact_width=260 if i18n.language=='en' else 200
        dense=event.width<1160*self.s
        if getattr(self.navigation,'compact_indices',False)!=dense:
            self.navigation.compact_indices=dense;self.navigation.paint_key=None;self.navigation.paint()
        target=min(self.rail_width,round(compact_width*self.s)) if event.width<1160*self.s else self.rail_width
        if int(self.side.cget('width'))!=target:
            self.side.configure(width=target)
            for label in self.footer.winfo_children():
                if isinstance(label,tk.Label):label.configure(wraplength=max(100,target-round(50*self.s)))

    def layout_sidebar(self,event):
        # Short windows shrink the logo; the rail rows adapt on their own.
        compact=event.height<780*self.s
        if compact!=self.compact:self.compact=compact;self.logo_width=None;self.paint_brand()
    def show_tabs(self):
        """Reveal the view-tab row once a page has put its tabs in it."""
        if self.tab_host.winfo_children() and not self.tab_host.winfo_manager():
            anchor=self.action_host if self.action_host.winfo_manager() else self.scroll.master
            self.tab_host.pack(fill='x',pady=(0,8),before=anchor)
    def clear_tabs(self):
        """Retire the page's fixed chrome: its view tabs and its tray."""
        for child in self.tab_host.winfo_children():child.destroy()
        self.tab_host.pack_forget()
        self.clear_tray()
    def show_tray(self,visible=True):
        """Show or hide the page's tray below the document (it keeps its widgets)."""
        if visible and self.tray_host.winfo_children():
            if not self.tray_host.winfo_manager():self.tray_host.pack(side='bottom',fill='x',pady=(round(10*self.s),0),before=self.scroll.master)
        elif self.tray_host.winfo_manager():self.tray_host.pack_forget()
    def clear_tray(self):
        for child in self.tray_host.winfo_children():child.destroy()
        self.tray_host.pack_forget()
    @property
    def covering(self):return self.surface.covering
    def cover_page(self):
        self.scroller.cancel();self.motion.cancel('page');self.scroll.coords(self.item,0,0)
        return self.surface.begin()
    def reveal_page(self,token=None):
        self.scroll.itemconfigure(self.item,state='normal')
        self.scroll.coords(self.item,0,0)
        return self.surface.reveal(token)
    def select(self,index):
        index=self.page_ids.index(index)
        self.navigation.select(index);self.breadcrumb.configure(text=f'STINTRIX  / 0{index + 1}')
        self.scroll.coords(self.item,0,0)
        self.title.configure(fg=T.FG)
