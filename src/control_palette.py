"""Ctrl+K command palette: reach any page, action, setting or guide entry by typing.

Opening is instant because the palette is a frequent, keyboard-first surface;
results filter on every keystroke and nothing runs before Enter or a click.
Commands reuse the callbacks behind the visible buttons, so availability and
side effects never diverge, and anything unavailable right now stays hidden.
"""
import re
import time
import tkinter as tk
import i18n
from i18n import tr
from control_theme import T
from control_widgets import Pill,px,rounded,scale
from control_motion import keyboard_action

GROUPS=('最近使用','页面','操作','设置','赛道指南','车型图鉴','搜索')
RECENT=5
LIMIT=40


class Command:
    __slots__=('key','title','group','run','hint','shortcut','words')
    def __init__(self,key,title,group,run,hint='',shortcut='',words=()):
        self.key=key;self.title=title;self.group=group;self.run=run;self.hint=hint;self.shortcut=shortcut;self.words=tuple(words)
    def texts(self):
        """Both languages match, whichever one the interface shows."""
        english=i18n.catalog()
        return [(self.title,1.),(english.get(self.title,self.title),1.),(self.hint,.6),(english.get(self.hint,self.hint),.6),*((word,.8) for word in self.words)]


def parts(text):return [part for part in re.split(r'[\s·/,，、()（）:：\-–—|]+',text) if part]


def subsequence(word,text):
    position=0
    for character in word:
        position=text.find(character,position)
        if position<0:return False
        position+=1
    return True


def score(command,query):
    """Prefix beats word start beats substring beats a loose subsequence; titles weigh most."""
    words=query.casefold().split()
    if not words:return 0.
    texts=[(text.casefold(),weight) for text,weight in command.texts() if text]
    total=0.
    for word in words:
        best=0.
        for text,weight in texts:
            if text.startswith(word):value=3.
            elif any(part.startswith(word) for part in parts(text)):value=2.
            elif word in text:value=1.
            # Loose letters count only inside one word of a title ("bcn" in "barcelona").
            elif len(word)>1 and weight==1. and any(subsequence(word,part) for part in parts(text)):value=.4
            else:continue
            best=max(best,value*weight)
        if not best:return 0.
        total+=best
    return total


def rank(commands,query,recent=()):
    """Ordered results: recent and core entries first when empty, best matches otherwise."""
    if not query.strip():
        found={command.key:command for command in commands}
        picks=[Command(found[key].key,found[key].title,'最近使用',found[key].run,found[key].hint,found[key].shortcut,found[key].words) for key in recent if key in found]
        chosen={command.key for command in picks}
        return picks+[command for command in commands if command.group in ('页面','操作') and command.key not in chosen]
    order={group:i for i,group in enumerate(GROUPS)}
    scored=[(score(command,query),order.get(command.group,9),i,command) for i,command in enumerate(commands) if command.group!='搜索']
    matched=[entry for entry in scored if entry[0]>0]
    matched.sort(key=lambda entry:(-entry[0],entry[1],entry[2]))
    return [entry[3] for entry in matched[:LIMIT]]+[command for command in commands if command.group=='搜索']


def when_ready(app,page,callback,deadline=None):
    """Run once the requested page has committed, without blocking the event loop."""
    deadline=deadline or time.monotonic()+6
    pages=getattr(app,'pages',None)
    if getattr(app,'closing',False) or pages is None:return
    ready=app.page==page and pages.pending is None and pages.active is not None and pages.active.complete and not app.shell.covering
    if ready:callback();return
    if time.monotonic()<deadline:app.root.after(30,lambda:when_ready(app,page,callback,deadline))


def go(app,page,callback=None):
    if app.page!=page or app.shell.covering or app.pages.pending is not None:app.request_page(page)
    if callback:when_ready(app,page,callback)


def reveal(app,widget):
    if widget is None or not widget.winfo_exists():return
    app.root.update_idletasks();y=widget.winfo_rooty()-app.content.winfo_rooty()
    app.scroll.yview_moveto(max(0,y-45)/max(1,app.content.winfo_height()));widget.focus_set()


def guide_names(app):
    from simulator_profiles import profile
    if profile(getattr(app,'simulator','lmu')).catalogue=='official':return {}
    cached=getattr(app,'_palette_guide',None)
    if cached is None:
        try:
            from guidebook import catalog
            data=catalog()
        except (OSError,ValueError):data={'tracks':{},'cars':{}}
        cached={view:[(slug,item['name'],item.get('location',''),item.get('location_zh',''),item.get('car_class','')) for slug,item in data.get(view,{}).items()] for view in ('tracks','cars')}
        app._palette_guide=cached
    return cached


def open_guide(app,view,query):
    """Same hand-off as a guide card's own jump: a fresh, filtered first page."""
    state=app.guide_state.setdefault(view,{})
    state.update(query=query,group='',car='',favorite='',page=0,mode='browse');state.pop('browse_scroll',None)
    page=4 if view=='tracks' else 5
    # The open guide rebuilds with the new query; another page switches normally.
    if app.page==page:app.show_page(page,progressive=True)
    else:app.request_page(page)


def search_reviews(app,query):
    def apply():
        variable=getattr(app,'search',None)
        if variable is not None:variable.set(query)
        field=getattr(app,'search_target',None)
        if field is not None and field.winfo_exists():field.flush(True);field.entry.focus_set();field.entry.icursor('end')
    go(app,1,apply)


def search_settings(app,query):
    app.settings_query=query;app.settings_results_open=True
    def apply():
        search=getattr(app,'settings_search',None)
        if search is not None and search.field.winfo_exists():search.variable.set(query);search.focus()
    go(app,2,apply)


def open_setting(app,entry):
    if entry.get('action'):entry['action']();return
    go(app,2,lambda:reveal(app,entry['widget']))


def live_setting(app,key):
    return next((entry for entry in reversed(getattr(app,'settings_index',[])) if entry['key']==key and entry['widget'].winfo_exists()),None)


def open_setting_key(app,key,label):
    """Settings are reachable before their page was ever opened: build it, then reveal the field."""
    entry=live_setting(app,key)
    if entry is not None:open_setting(app,entry);return
    def ready():
        entry=live_setting(app,key)
        if entry is not None:open_setting(app,entry)
        else:search_settings(app,tr(label))
    go(app,2,ready)


def setting_catalogue(app):
    """(key, label, section, run) for every searchable preference of this simulator."""
    from control_settings_search import SECTIONS,ROUTES,FORMS,TYRES,EXTRA,route
    from simulator_profiles import profile
    found=[]
    if profile(getattr(app,'simulator','lmu')).catalogue!='official':
        for module,(fields,choices) in FORMS.items():
            for spec in (*fields,*choices):found.append((spec[0],spec[1],SECTIONS[module],None))
        found+=[(key,label,SECTIONS['vehicle'],None) for key,label in TYRES]
        found+=[(key,label,section,None) for key,label,section in EXTRA]
        found+=[(key,label,'运行与数据',lambda p=page,a=attribute,c=section:route(app,p,a,c)) for key,label,page,attribute,section in ROUTES]
    known={item[0] for item in found}
    for entry in reversed(getattr(app,'settings_index',[])):
        widget=entry.get('widget')
        if entry['key'] in known or entry['key']=='global_shortcuts' or widget is None or not widget.winfo_exists():continue
        known.add(entry['key']);found.append((entry['key'],entry['label'],entry['section'],lambda e=entry:open_setting(app,e)))
    return found


def commands(app):
    from control_hud_stop import saving
    from control_maintenance import busy
    from track_names import display
    found=[]
    add=lambda *args,**kwargs:found.append(Command(*args,**kwargs))
    for index,name in enumerate(app.page_titles):
        add(f'page:{index}',name,'页面',lambda i=index:app.request_page(i),app.page_subtitles[index],f'Ctrl+{index+1}')
    active=app.active();idle=not active and not saving(app) and not busy(app)
    if idle:
        add('start','启动记录','操作',app.start,'启动 HUD 并开始记录',words=('start','record','hud'))
        add('demo','演示模式','操作',lambda:app.start(True),'合成数据预览 HUD',words=('demo',))
    if active:
        add('stop','停止并保存','操作',app.stop_hud,'结束本次记录并生成报告',words=('stop','save'))
        add('clickthrough','鼠标穿透 / 解锁','操作',lambda:app.hud_action('toggle_clickthrough'),'HUD 运行中')
        add('diagnostics','性能诊断','操作',lambda:app.hud_action('show_diagnostics'),'HUD 运行中')
    recent=getattr(app,'recent',None)
    if recent is not None and recent.folder is not None:
        from control_recent_session import open_report,add_note
        state=recent.state();where=state.get('text','')
        if state.get('review'):add('recent:review','打开刚结束的复盘','操作',lambda:open_report(app,'review'),where,words=('review','last'))
        if state.get('laps'):add('recent:laps','刚结束的圈速单','操作',lambda:open_report(app,'laps'),where,words=('laps',))
        if state.get('note'):add('recent:note','为刚结束的赛事添加备注','操作',lambda:add_note(app),where,words=('note',))
    from control_layouts import show as layouts
    from control_shortcuts import show as shortcuts
    from control_interface import show as interface
    add('layouts','HUD 布局','操作',lambda:layouts(app),'布局方案、备份与恢复',words=('layout',))
    add('shortcuts','全局快捷键','操作',lambda:shortcuts(app),'游戏中控制 HUD 的按键',words=('hotkey','keys'))
    add('interface','检查数据接口','操作',lambda:interface(app),'查看游戏数据接口与插件状态')
    add('library','完整记录管理','操作',lambda:app.library(),'查看与整理全部本地赛事')
    sheet=getattr(app,'shortcut_sheet',None)
    if sheet is not None:add('keys','键盘快捷键一览','操作',sheet.open,'所有界面快捷键','F1',words=('keyboard','shortcuts','help'))
    add('theme','切换为浅色主题' if T.mode=='dark' else '切换为深色主题','操作',app.toggle_theme,'',words=('theme','dark','light'))
    add('language','Switch to English' if i18n.language=='zh' else '切换到中文','操作',app.toggle_language,'EN / 中文',words=('language','english','中文'))
    for key,label,section,run in setting_catalogue(app):
        add('setting:'+key,label,'设置',run or (lambda k=key,l=label:open_setting_key(app,k,l)),section,words=(key.replace('_',' '),))
    names=guide_names(app)
    for slug,name,location,location_zh,_ in names.get('tracks',[]):
        add('track:'+slug,display(name),'赛道指南',lambda q=name:open_guide(app,'tracks',q),location_zh if i18n.language=='zh' else location,words=(name,display(name,'zh'),location,location_zh))
    for slug,name,_,_,car_class in names.get('cars',[]):
        add('car:'+slug,name,'车型图鉴',lambda q=name:open_guide(app,'cars',q),car_class)
    return found


def search_commands(app,query):
    """Typed text can always continue as a search inside the page that owns it."""
    from simulator_profiles import profile
    found=[Command('search:reviews',tr('在赛事复盘中搜索')+f' “{query}”','搜索',lambda:search_reviews(app,query),'',''),
        Command('search:settings',tr('在设置中搜索')+f' “{query}”','搜索',lambda:search_settings(app,query),'','')]
    if profile(getattr(app,'simulator','lmu')).catalogue!='official':
        found+=[Command('search:tracks',tr('在赛道指南中搜索')+f' “{query}”','搜索',lambda:open_guide(app,'tracks',query),'',''),
            Command('search:cars',tr('在车型图鉴中搜索')+f' “{query}”','搜索',lambda:open_guide(app,'cars',query),'','')]
    return found


class Palette:
    """A floating panel inside the main window: no extra native window, no focus juggling."""
    def __init__(self,app):
        self.app=app;self.frame=None;self.rows=[];self.results=[];self.index=0;self.click=None;self.resize=None;self.previous=None;self.commands=[]
        if not hasattr(app,'_palette_recent'):app._palette_recent=[]

    @property
    def opened(self):return self.frame is not None and self.frame.winfo_exists()

    def toggle(self,_=None):
        if self.opened:self.close()
        else:self.open()
        return 'break'

    def open(self):
        app=self.app;root=app.root
        if self.opened:self.entry.focus_set();return
        sheet=getattr(app,'shortcut_sheet',None)
        if sheet is not None:sheet.close(False)
        try:self.commands=commands(app)
        except tk.TclError:return
        self.previous=root.focus_get()
        # A page-coloured halo and a hairline edge lift the panel off the cards below.
        self.frame=frame=tk.Frame(root,bg=T.BG);self.halo=px(root,6)
        edge=tk.Frame(frame,bg=T.EDGE);edge.pack(fill='both',expand=True,padx=self.halo,pady=self.halo)
        inner=tk.Frame(edge,bg=T.CARD);inner.pack(fill='both',expand=True,padx=1,pady=1)
        head=tk.Frame(inner,bg=T.CARD);head.pack(fill='x',padx=px(root,14),pady=(px(root,14),px(root,8)))
        self.query=tk.StringVar(root)
        from control_search import SearchField
        self.field=SearchField(head,self.query,None,placeholder='搜索页面、操作、设置或赛道…',font=(T.FONT,12));self.field.pack(fill='x')
        self.entry=self.field.entry
        self.list=tk.Canvas(inner,bg=T.CARD,highlightthickness=0,height=1,takefocus=False);self.list.pack(fill='x',padx=px(root,8));self.drawn=None
        self.list.bind('<Configure>',lambda e:self.draw() if e.width!=self.drawn else None)
        foot=tk.Frame(inner,bg=T.CARD);foot.pack(fill='x',padx=px(root,16),pady=(px(root,6),px(root,10)))
        self.count=tk.Label(foot,text='',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='w');self.count.pack(side='left')
        tk.Label(foot,text=tr('↑↓ 选择 · Enter 打开 · Esc 关闭'),bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='e').pack(side='right')
        self.trace=self.query.trace_add('write',lambda *_:self.refresh())
        for sequence,handler in (('<Down>',lambda _:self.move(1)),('<Up>',lambda _:self.move(-1)),('<Next>',lambda _:self.move(5)),('<Prior>',lambda _:self.move(-5)),
                ('<Tab>',lambda _:self.move(1)),('<Shift-Tab>',lambda _:self.move(-1)),('<Control-n>',lambda _:self.move(1)),('<Control-p>',lambda _:self.move(-1)),
                ('<Return>',lambda _:self.choose(keyboard=True)),('<Escape>',lambda _:self.close(True)),('<Control-k>',lambda _:self.close(True)),('<Control-K>',lambda _:self.close(True)),
                ('<Control-f>',lambda _:None)):
            self.entry.bind(sequence,lambda event,h=handler:(h(event),'break')[1])
        self.list.bind('<Motion>',self.hover);self.list.bind('<Button-1>',self.press)
        self.list.bind('<MouseWheel>',lambda e:(self.list.yview_scroll(-1 if e.delta>0 else 1,'units') if self.list.yview()!=(0.,1.) else None,'break')[1])
        frame.bind('<Destroy>',self.dispose,add='+')
        self.click=root.bind('<Button-1>',self.outside,add='+');self.resize=root.bind('<Configure>',self.place,add='+')
        self.place();frame.lift();self.refresh();self.entry.focus_set()

    def place(self,event=None):
        if not self.opened or (event is not None and event.widget is not self.app.root):return
        root=self.app.root;width=max(px(root,420),min(px(root,660),root.winfo_width()-px(root,120)));self.width=width
        self.frame.place(in_=root,relx=.5,y=px(root,78),anchor='n',width=width)

    def refresh(self):
        if not self.opened:return
        query=self.query.get();extra=search_commands(self.app,query.strip()) if query.strip() else []
        self.results=rank(self.commands+extra,query,self.app._palette_recent)
        self.index=0;self.draw()
        found=sum(command.group!='搜索' for command in self.results)
        self.count.configure(text=tr('没有匹配结果') if query.strip() and not found else (tr('{count} 项').format(count=found) if query.strip() else ''))

    def draw(self):
        canvas=self.list;canvas.delete('all');s=scale(canvas);width=max(1,canvas.winfo_width() if canvas.winfo_width()>1 else self.width-2*self.halo-2-px(canvas,16));self.drawn=canvas.winfo_width()
        self.rows=[];y=0;group=None;item_h=round(40*s);head_h=round(26*s)
        for position,command in enumerate(self.results):
            if command.group!=group:
                group=command.group;canvas.create_text(10*s,y+head_h-7*s,text=tr(group),anchor='sw',fill=T.MUTED,font=(T.FONT,8,'bold'));y+=head_h
            self.rows.append((y,y+item_h,command));selected=position==self.index
            if selected:
                rounded(canvas,2*s,y+2*s,width-4*s,item_h-4*s,6*s,fill=T.SELECT,outline=T.MARK)
                canvas.create_rectangle(2*s,y+12*s,5*s,y+item_h-12*s,fill=T.ACCENT,outline='')
            shortcut=command.shortcut
            right=width-12*s
            if shortcut:canvas.create_text(right,y+item_h/2,text=shortcut,anchor='e',fill=T.ACCENT if selected else T.MUTED,font=('Consolas',8));right-=tk_measure(canvas,('Consolas',8),shortcut)+14*s
            title=tr(command.title);title_font=(T.FONT,10,'bold' if selected else 'normal')
            title=clip(canvas,title_font,title,right-16*s)
            canvas.create_text(16*s,y+item_h/2,text=title,anchor='w',fill=T.FG,font=title_font)
            hint=tr(command.hint) if command.hint else ''
            if hint:
                left=16*s+tk_measure(canvas,title_font,title)+12*s;room=right-left
                if room>40*s:canvas.create_text(left,y+item_h/2,text=clip(canvas,(T.FONT,9),hint,room),anchor='w',fill=T.MUTED,font=(T.FONT,9))
            y+=item_h
        if not self.results:
            canvas.create_text(width/2,round(30*s),text=tr('输入以搜索页面、操作、设置或赛道'),fill=T.MUTED,font=(T.FONT,9));y=round(60*s)
        visible=min(y,round(380*s));canvas.configure(height=max(1,visible),scrollregion=(0,0,width,max(y,1)))
        self.keep_visible()

    def keep_visible(self):
        if not self.rows:return
        top,bottom,_=self.rows[min(self.index,len(self.rows)-1)];canvas=self.list
        total=max(1,float(canvas.cget('scrollregion').split()[3]) if canvas.cget('scrollregion') else 1);view=canvas.winfo_height() if canvas.winfo_height()>1 else int(canvas.cget('height'))
        first=canvas.canvasy(0)
        if self.index==0:canvas.yview_moveto(0)
        elif top<first+round(26*scale(canvas)):canvas.yview_moveto(max(0,top-round(26*scale(canvas)))/total)
        elif bottom>first+view:canvas.yview_moveto((bottom-view)/total)

    def move(self,delta):
        if not self.rows:return
        self.index=max(0,min(len(self.rows)-1,self.index+delta));self.draw()

    def hover(self,event):
        y=self.list.canvasy(event.y)
        for position,(top,bottom,_) in enumerate(self.rows):
            if top<=y<bottom:
                if position!=self.index:self.index=position;self.draw()
                return

    def press(self,event):
        self.hover(event)
        if self.rows:self.choose(keyboard=False)
        return 'break'

    def choose(self,keyboard=False):
        if not self.rows:return
        command=self.rows[min(self.index,len(self.rows)-1)][2]
        recent=self.app._palette_recent
        if not command.key.startswith('search:'):
            if command.key in recent:recent.remove(command.key)
            recent.insert(0,command.key);del recent[RECENT:]
        self.close(False)
        if keyboard:keyboard_action(self.app.root,command.run)
        else:command.run()

    def outside(self,event):
        widget=event.widget
        while widget is not None:
            if widget is self.frame:return
            widget=getattr(widget,'master',None)
        self.close(False)

    def close(self,restore=True):
        if not self.opened:return
        previous=self.previous;self.frame.destroy()
        if restore and previous is not None:
            try:
                if previous.winfo_exists():previous.focus_set()
            except (tk.TclError,KeyError):pass

    def dispose(self,event):
        if event.widget is not self.frame:return
        root=self.app.root
        for sequence,token in (('<Button-1>',self.click),('<Configure>',self.resize)):
            if token:
                try:root.unbind(sequence,token)
                except tk.TclError:pass
        self.click=self.resize=None
        try:self.query.trace_remove('write',self.trace)
        except (tk.TclError,AttributeError):pass
        from control_widgets import release
        release(self.query);self.frame=None;self.rows=[]


def tk_measure(widget,font,text):return int(widget.tk.call('font','measure',font,text))


def clip(widget,font,text,room):
    if tk_measure(widget,font,text)<=room:return text
    while text and tk_measure(widget,font,text+'…')>room:text=text[:-1]
    return text+'…'


class SearchPill(Pill):
    """Header entry to the palette: a drawn magnifier, its label and the shortcut."""
    def __init__(self,parent,command):
        super().__init__(parent,'搜索',command,150)
        keys=tk_measure(self,('Consolas',8),'Ctrl K');self.configure(width=max(int(self.cget('width')),round(self.font.measure(tr('搜索'))+keys+64*self.s)))
    def paint(self):
        super().paint()
        s=self.s;w=self.winfo_width();h=self.winfo_height();shift=self.press_amount*s;middle=h/2-s+shift
        if not hasattr(self,'glass'):
            self.glass=self.create_oval(0,0,1,1);self.handle=self.create_line(0,0,1,1,capstyle='round');self.keys=self.create_text(0,0,anchor='e',font=('Consolas',8))
        r=4.5*s;cx=20*s;cy=middle-1*s
        self.coords(self.glass,cx-r,cy-r,cx+r,cy+r);self.coords(self.handle,cx+r*.75,cy+r*.75,cx+r*1.7,cy+r*1.7)
        self.itemconfigure(self.glass,outline=T.FG,width=max(1,1.4*s));self.itemconfigure(self.handle,fill=T.FG,width=max(1,1.4*s))
        self.coords(self.caption,33*s,middle);self.itemconfigure(self.caption,anchor='w')
        self.coords(self.keys,w-16*s,middle);self.itemconfigure(self.keys,text='Ctrl K',fill=T.MUTED)
