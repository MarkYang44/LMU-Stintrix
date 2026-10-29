"""Small, context-preserving EVO catalogue and official layout browser."""
import tkinter as tk
import webbrowser
from control_theme import T
from control_fields import Select
from control_flow import install
from control_search import SearchField
from control_motion import keyboard_action
from guide_cards import Picture
from evo_art import catalog,item,local_asset
from i18n import tr

GROUPS={'road':'公路车','gt2':'GT2','gt3':'GT3','gt4':'GT4','cup':'杯赛车 / 单一品牌','formula':'方程式','racing':'其他赛车'}


def matches(entries,query='',brand='',group=''):
    query=query.strip().casefold()
    return [e for e in entries if (not brand or e.get('brand')==brand) and (not group or e.get('group')==group) and
        query in ' '.join((e['name'],*e.get('aliases',[]),e.get('brand',''),*[c['name'] for c in e.get('configurations',[])])).casefold()]


class Gallery(tk.Frame):
    PAGE_SIZE=12
    def __init__(self,app,kind):
        super().__init__(app.content,bg=T.BG);self.pack(fill='x');self.app=app;self.kind=kind;self.cards=[];self.restoring=False;self.restore_job=None;self.traces=[];self.render_key=None
        states=getattr(app,'evo_gallery_state',{});app.evo_gallery_state=states
        self.state=states.setdefault(kind,dict(query='',brand='',group='',page=0,detail=None,scroll=0))
        self.entries=[e for e in catalog()[kind] if kind!='tracks' or not e.get('layouts')]
        self.car_buttons={}
        if kind=='cars':
            names={e['name'] for e in self.entries}
            self.state['comparison']=list(dict.fromkeys(n for n in self.state.get('comparison',[]) if n in names))[:2]
        self.browse=tk.Frame(self,bg=T.BG);self.browse.pack(fill='x');self.detail=tk.Frame(self,bg=T.BG)
        outer=app.content;app.content=self.browse
        try:body=app.card('AC EVO · 车型图库' if kind=='cars' else 'AC EVO · 赛道与布局','按品牌、车型组别筛选；仅在可见时加载图片。' if kind=='cars' else '点击赛道卡查看布局；线路图来自游戏官方网站。',compact=True)
        finally:app.content=outer
        self.variables={k:tk.StringVar(self,value=self.state.get(k,'')) for k in ('query','brand','group')}
        self.status=tk.StringVar(self);self.variables['status']=self.status
        row=app.row(body);app.label(row,'搜索',10,T.MUTED).pack(side='left',padx=(0,8))
        self.search=SearchField(row,textvariable=self.variables['query'],command=self.filter_changed,placeholder='搜索车型、品牌或赛道布局')
        self.search.pack(side='left',fill='x',expand=True);app.search_target=self.search
        self.selectors={}
        if kind=='cars':
            facets=tk.Frame(body,bg=T.CARD);facets.pack(fill='x',pady=8)
            specs=[('brand','品牌',['',*sorted({e['brand'] for e in self.entries})],{'':'全部品牌'}),
                ('group','车型组别',['',*GROUPS],{'':'全部车型组别',**GROUPS})]
            for i,(key,label,values,labels) in enumerate(specs):
                panel=tk.Frame(facets,bg=T.CARD);panel.grid(row=0,column=i,sticky='ew',padx=(0,10) if not i else 0)
                app.label(panel,label,9,T.MUTED).pack(anchor='w',pady=(0,5))
                select=Select(panel,textvariable=self.variables[key],values=values,labels={k:tr(v) for k,v in labels.items()});select.pack(fill='x');self.selectors[key]=select
                facets.columnconfigure(i,weight=1,uniform='evo-facets')
                self.traces.append((self.variables[key],self.variables[key].trace_add('write',self.filter_changed)))
            app.button(app.row(body),'重置筛选',self.reset,False,120)
        nav=app.row(body);install(nav)
        self.previous=app.button(nav,'← 上一页',lambda:self.step(-1),False,120)
        app.label(nav,self.status,10,T.MUTED).pack(side='left',padx=10)
        self.following=app.button(nav,'下一页 →',lambda:self.step(1),False,120)
        app.button(nav,'官方图片来源',lambda:webbrowser.open(catalog()['source']),False,145)
        if kind=='cars':
            from control_guide_chips import Chips
            selection=app.row(body);install(selection)
            self.selection_status=tk.StringVar(self)
            app.label(selection,self.selection_status,10,T.ACCENT).pack(side='left',padx=(0,10))
            self.compare_button=app.button(selection,'查看车型对比',self.open_compare,True,145)
            self.clear_button=app.button(selection,'清空选择',self.clear_selection,False,115)
            self.selection_chips=Chips(body,self.select_car,lambda:self.search.focus_set())
        self.host=tk.Frame(body,bg=T.CARD);self.host.pack(fill='x');self.host.bind('<Configure>',self.layout)
        self.bind('<Destroy>',self.dispose,add='+');app.evo_gallery_refresh=(self,self.refresh)
        self.render()
        selected=next((e for e in self.entries if e['name']==self.state.get('detail')),None)
        if selected:self.open_track(selected,remember=False)
        if kind=='cars' and self.state.get('mode')=='compare':self.open_compare(remember=False)

    def snapshot(self):
        self.state.update({k:v.get() for k,v in self.variables.items() if k in ('query','brand','group')})

    def filter_changed(self,*_):
        if self.restoring:return
        self.snapshot();self.state['page']=0;self.render()

    def reset(self):
        self.restoring=True
        try:
            for key in ('query','brand','group'):self.variables[key].set('')
        finally:self.restoring=False
        self.filter_changed()

    def step(self,delta):
        self.state['page']+=delta;self.render();self.app.scroll.yview_moveto(0)

    def layout(self,event=None):
        columns=2 if self.host.winfo_width()>=650 else 1
        for i,card in enumerate(self.cards):card.grid(row=i//columns,column=i%columns,sticky='nsew',padx=5,pady=5)
        for i in (0,1):self.host.columnconfigure(i,weight=1 if not i or columns==2 else 0,uniform='evo-gallery' if columns==2 else '')

    def render(self,force=False):
        self.snapshot()
        key=tuple(self.state.get(k) for k in ('query','brand','group','page'))+(T.mode,)
        if not force and key==self.render_key:return
        for child in self.host.winfo_children():child.destroy()
        self.cards.clear();self.car_buttons={}
        values=matches(self.entries,self.state['query'],self.state['brand'] if self.kind=='cars' else '',self.state['group'] if self.kind=='cars' else '')
        pages=max(1,(len(values)+self.PAGE_SIZE-1)//self.PAGE_SIZE);self.state['page']=max(0,min(self.state['page'],pages-1));page=self.state['page']
        self.status.set(tr('第 {page} / {pages} 页 · {count} 项').format(page=page+1,pages=pages,count=len(values)))
        self.previous.configure(state='normal' if page else 'disabled');self.following.configure(state='normal' if page+1<pages else 'disabled')
        self.visible_entries=values[page*self.PAGE_SIZE:(page+1)*self.PAGE_SIZE]
        for entry in self.visible_entries:
            card=tk.Frame(self.host,bg=T.FIELD,takefocus=self.kind=='tracks',highlightthickness=1,highlightbackground=T.FIELD,highlightcolor=T.ACCENT);self.cards.append(card)
            label=self.app.label(card,entry['name'],11,T.FG,True);label.configure(wraplength=320);label.pack(fill='x',padx=10,pady=10)
            label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(100,e.width)))
            caption=tr(GROUPS[entry['group']]) if self.kind=='cars' else tr('{count} 种布局 · {maps} 张官方线路图').format(count=len(entry.get('configurations',[])),maps=sum(bool(c.get('url')) for c in entry.get('configurations',[])))
            self.app.label(card,caption,9,T.MUTED).pack(anchor='w',padx=10,pady=(0,8))
            art=item(self.kind,entry['name'],root=self.app.data_path)
            if art:Picture(card,self.app,art)
            else:self.app.label(card,'图片尚未下载或该型号暂无匹配官方图。',10,T.MUTED).pack(fill='x',pady=28)
            if self.kind=='tracks':
                def activate(event=None,e=entry,owner=card):
                    if event is not None and event.type==tk.EventType.KeyPress:return keyboard_action(owner,lambda:self.open_track(e))
                    self.open_track(e);return 'break'
                self.bind_card(card,activate)
            else:
                row=self.app.row(card)
                self.car_buttons[entry['name']]=self.app.button(row,'加入对比',lambda n=entry['name']:self.select_car(n),False,120)
        if not values:self.app.label(self.host,'没有符合当前筛选的车型。' if self.kind=='cars' else '没有符合当前筛选的赛道或布局。',11,T.MUTED).pack(fill='x',pady=24)
        self.render_key=tuple(self.state.get(k) for k in ('query','brand','group','page'))+(T.mode,)
        self.layout()
        if self.kind=='cars':self.update_selection()

    def update_selection(self):
        names=self.state['comparison'];full=len(names)==2
        self.selection_status.set(tr('已选 {count} / 2 台车型').format(count=len(names)))
        self.compare_button.configure(state='normal' if full else 'disabled')
        self.clear_button.configure(state='normal' if names else 'disabled')
        self.selection_chips.set([(n,chr(65+i)+' · '+n) for i,n in enumerate(names)])
        for name,button in self.car_buttons.items():
            selected=name in names
            button.configure(text='移出对比' if selected else '加入对比',selected=selected,state='normal' if selected or not full else 'disabled')

    def select_car(self,name):
        names=self.state['comparison']
        if name in names:names.remove(name)
        elif len(names)<2 and any(e['name']==name for e in self.entries):names.append(name)
        self.update_selection()

    def clear_selection(self):
        self.state['comparison'].clear();self.update_selection()

    def open_compare(self,remember=True):
        if self.kind!='cars' or len(self.state['comparison'])!=2:return
        if remember and self.state.get('mode')!='compare':self.state['scroll']=self.app.scroll.yview()[0]
        self.state['mode']='compare';self.browse.pack_forget();self.detail.pack(fill='x')
        for child in self.detail.winfo_children():child.destroy()
        outer=self.app.content;self.app.content=self.detail
        try:body=self.app.card('AC EVO · 车型对比','选择保留在当前进程；返回后继续原筛选与位置。',compact=True)
        finally:self.app.content=outer
        self.app.button(self.app.row(body),'← 返回车型列表',self.back,False,185)
        from evo_gallery_compare import Comparison
        entries=[next(e for e in self.entries if e['name']==n) for n in self.state['comparison']]
        self.comparison=Comparison(body,self.app,entries)
        self.app.scroll.yview_moveto(0)

    def focus_search(self):
        if self.kind=='cars' and self.state.get('mode')=='compare':self.back()
        elif self.state.get('detail'):self.back()
        self.app.root.update_idletasks();self.app.scroll.yview_moveto(0)
        self.search.focus_set();self.search.entry.selection_range(0,'end');return 'break'

    def bind_card(self,widget,command):
        widget.configure(cursor='hand2');widget.bind('<Button-1>',command,add='+')
        widget.bind('<Return>',command);widget.bind('<space>',command)
        for child in widget.winfo_children():self.bind_card(child,command)

    def open_track(self,entry,remember=True):
        if self.kind!='tracks':return
        if remember and not self.state.get('detail'):self.state['scroll']=self.app.scroll.yview()[0]
        self.state['detail']=entry['name'];self.selected_track=entry;self.browse.pack_forget();self.detail.pack(fill='x')
        for child in self.detail.winfo_children():child.destroy()
        outer=self.app.content;self.app.content=self.detail
        configs=entry.get('configurations',[])
        subtitle=tr('{count} 种布局 · {maps} 张官方线路图').format(count=len(configs),maps=sum(bool(c.get('url')) for c in configs))
        try:body=self.app.card(entry['name'],subtitle,compact=True)
        finally:self.app.content=outer
        navigation=self.app.row(body);install(navigation)
        self.app.button(navigation,'← 返回赛道列表',self.back,False,185)
        self.track_variable=tk.StringVar(self.detail,value=entry['name'])
        self.track_select=Select(navigation,textvariable=self.track_variable,values=[e['name'] for e in self.entries],width=32)
        self.track_select.pack(side='left',padx=6)
        self.track_select.bind('<<ComboboxSelected>>',self.choose_track)
        self.map_buttons={};row=self.app.row(body);install(row)
        for config in configs:
            button=self.app.button(row,config['name'],lambda c=config:self.show_layout(c),False,150);self.map_buttons[config['name']]=button
            button.bind('<Left>',lambda e:self.step_layout(-1,e.widget));button.bind('<Right>',lambda e:self.step_layout(1,e.widget))
        self.layout_title=self.app.label(body,'',14,T.FG,True);self.layout_title.pack(fill='x',pady=12)
        self.map_host=tk.Frame(body,bg=T.FIELD);self.map_host.pack(fill='x');self.map_picture=None
        self.map_note=self.app.label(body,'',9,T.MUTED);self.map_note.pack(fill='x',pady=8)
        self.source_button=self.app.button(self.app.row(body),'官方图片来源',lambda:webbrowser.open(self.selected_layout.get('source',catalog()['source'])),False,185)
        wanted=self.state.get('layout_selection',{}).get(entry['name'])
        if configs:self.show_layout(next((c for c in configs if c['name']==wanted),configs[0]))
        self.app.scroll.yview_moveto(0)

    def show_layout(self,config):
        if getattr(self,'selected_layout',None)==config and getattr(self,'map_picture',None) is not None and self.map_picture.winfo_exists():return
        self.selected_layout=config;self.state.setdefault('layout_selection',{})[self.selected_track['name']]=config['name']
        self.layout_title.configure(text=config['name'])
        for key,button in self.map_buttons.items():button.configure(selected=key==config['name'])
        for child in self.map_host.winfo_children():child.destroy()
        art=local_asset(config,self.app.data_path)
        if art:self.map_picture=Picture(self.map_host,self.app,art)
        else:
            self.map_picture=None
            self.app.label(self.map_host,'该布局的官方线路图尚未下载，请使用上方更新按钮。' if config.get('url') else '尚未收录该布局的官方线路图。',11,T.MUTED).pack(fill='x',pady=32)
        self.map_note.configure(text=tr('官方线路示意图；未用其他布局的线路替代。') if config.get('url') else tr('布局已列出；找到可靠的对应线路图后再补充。'))
        self.source_button.configure(text='官方图片来源' if config.get('url') else '布局资料来源')

    def choose_track(self,*_):
        value=self.track_variable.get();entry=next((e for e in self.entries if e['name']==value),None)
        if entry and entry['name']!=self.selected_track['name']:self.open_track(entry)

    def step_layout(self,delta,owner):
        configs=self.selected_track.get('configurations',[])
        if configs:
            index=configs.index(self.selected_layout);target=configs[(index+delta)%len(configs)]
            keyboard_action(owner,lambda:self.show_layout(target));self.map_buttons[target['name']].focus_set()
        return 'break'

    def back(self):
        self.state['detail']=None;self.state['mode']='browse';self.detail.pack_forget();self.browse.pack(fill='x');self.app.search_target=self.search
        if self.restore_job:self.after_cancel(self.restore_job)
        def restore():
            self.restore_job=None
            if self.winfo_exists():
                self.app.root.update_idletasks()
                if self.winfo_exists():self.app.scroll.yview_moveto(self.state.get('scroll',0))
        self.restore_job=self.after_idle(restore)

    def refresh(self):
        if self.kind=='cars' and self.state.get('mode')=='compare':
            fraction=self.app.scroll.yview()[0];self.open_compare(remember=False);self.app.root.update_idletasks();self.app.scroll.yview_moveto(fraction)
        elif self.state.get('detail'):
            config=self.selected_layout;self.selected_layout=None;self.show_layout(config)
        else:self.render(force=True)

    def dispose(self,event):
        if event.widget is not self:return
        for var,trace in self.traces:
            try:var.trace_remove('write',trace)
            except tk.TclError:pass
        if self.restore_job:self.after_cancel(self.restore_job);self.restore_job=None
