"""Complete native guide pages: spacious cards, private favorites and comparison."""
import tkinter as tk
from tkinter import ttk
from control_theme import T
from control_fields import Field,Select
from control_widgets import px,GlassCard
from control_flow import install
from guidebook import catalog
from guide_library import Library
from guide_cards import Cards


class GuidePage:
    PAGE_SIZE=3
    def __init__(self,center,view):
        self.center=center;self.view=view;self.job=None;self.card_job=None;self.render_generation=0;self.closed=False
        self.library=Library(catalog(),center.data_path/'guide_settings.json')
        import i18n
        self.library.language=i18n.language
        self.state=center.guide_state.setdefault(view,{})
        for key,value in dict(query='',group='',car='',favorite='',page=0,comparison=[],mode='browse',layout='cards').items():self.state.setdefault(key,value)
        self.state.setdefault('expanded',[]);self.pagers=[];self.page_boxes=[];self.restoring=False
        self.cards=Cards(self);self.rows=[];self.card_count=0;self.variables={};self.compare_buttons={};self.favorite_buttons={}
        self.initial_ready=center.pages.hold();self.fixed_actions={}
        self.build();self.container.bind('<Destroy>',self.dispose,add='+');self.render()

    def tr(self,zh,en):return self.library.tr(zh,en)
    def focus_search(self):
        # The search field is fixed above the cards: focusing never moves the reading position.
        if self.state['mode']=='compare':self.state['mode']='browse';self.render(top=True)
        entry=self.search_entry
        if entry is None or not entry.winfo_exists():return 'break'
        entry.focus_set();entry.selection_range(0,'end');return 'break'
    def dispose(self,event):
        if event.widget is not self.container:return
        self.closed=True;self.cards.page=None
        try:self.variables['query'].trace_remove('write',self.query_trace)
        except tk.TclError:pass
        for job in (self.job,self.card_job):
            if job:
                try:self.center.root.after_cancel(job)
                except tk.TclError:pass
        self.job=None;self.card_job=None

    def build(self):
        center=self.center;tr=self.tr
        self.container=tk.Frame(center.content,bg=T.BG);self.container.pack(fill='x')
        self.filter_card=GlassCard(self.container,compact=True);self.filter_card.pack(fill='x',pady=(0,12));body=self.filter_card.body
        query=tk.StringVar(center.root,value=self.state['query']);self.variables['query']=query
        # Search and the filter toggle live in the fixed toolbar (install_actions);
        # this card keeps the filter fields, chips, reset and the result count.
        self.search_field=self.search_entry=self.filter_button=None
        self.query_trace=query.trace_add('write',lambda *_:self.remember_query())
        class_values={tr('全部组别','All classes'):'','LMGT3':'LMGT3','Hypercar':'Hypercar'}
        car_values={tr('全部车型','All cars'):'',**{item['name']:item['slug'] for item in self.library.data['cars'].values()}}
        favorite_values={tr('全部内容','All content'):'',tr('收藏的车型','Favorite cars'):'cars'}
        if self.view=='tracks':favorite_values[tr('收藏的赛道','Favorite circuits')]='tracks'
        self.choices={};filters=tk.Frame(body,bg=T.CARD);self.filter_fields=filters;tiles=[]
        for key,title,values in [('group',tr('组别','Class'),class_values),('car',tr('车型','Car'),car_values),('favorite',tr('收藏','Favorites'),favorite_values)]:
            variable=tk.StringVar(center.root,value=next((name for name,value in values.items() if value==self.state[key]),next(iter(values))))
            self.variables[key]=variable;self.choices[key]=values
            tile=tk.Frame(filters,bg=T.CARD);tiles.append(tile);center.label(tile,title,9,T.MUTED).pack(anchor='w',pady=(2,4))
            box=Select(tile,textvariable=variable,values=list(values),width=12);box.pack(fill='x');box.bind('<<ComboboxSelected>>',lambda _:self.filter_changed())
        def arrange(event):
            columns=3 if event.width>=px(filters,630) else 2 if event.width>=px(filters,430) else 1
            for i in range(3):filters.columnconfigure(i,weight=1 if i<columns else 0,uniform='guide-filters' if i<columns else '',minsize=0)
            for i,tile in enumerate(tiles):tile.grid(row=i//columns,column=i%columns,sticky='ew',padx=(0,px(filters,8)) if i%columns<columns-1 else 0,pady=(0,4))
        filters.bind('<Configure>',arrange)
        row=center.row(body);self.filter_tools=row;install(row)
        self.reset_button=center.button(row,tr('重置筛选','Reset filters'),self.reset,width=112)
        self.metadata_button=center.button(row,tr('资料说明 ▸','About this data ▸'),self.toggle_metadata,width=120)
        self.page_number=tk.StringVar(center.root);self.variables['page_number']=self.page_number
        self.result=center.label(row,'',9,T.ACCENT);self.result.pack(side='left',padx=5)
        from control_guide_chips import Chips
        self.filter_chips=Chips(body,self.remove_filter,self.focus_search)
        self.metadata=tk.Frame(body,bg=T.CARD)
        self.cards.text(self.metadata,f"GTD {self.library.data['content_version']} · {self.library.data['updated']} · "+tr('资料参考：','Reference: ')+self.library.data['game_reference'],9,T.MUTED)
        self.cards.text(self.metadata,tr('实测验证：','Build-validated: ')+f"{self.library.data['validated_recommendations']}/{self.library.data['total_recommendations']} · "+tr('文字来自 GTD；图片来源 Le Mans Ultimate / Studio 397。保留原资料日期和未验证标记。','Content adapted from GTD; artwork credited to Le Mans Ultimate / Studio 397. Original dates and unverified markers retained.'),9,T.MUTED)
        if self.state.get('metadata'):
            self.metadata.pack(fill='x',pady=6);self.metadata_button.configure(text=tr('资料说明 ▾','About this data ▾'))
        card=GlassCard(self.container,compact=True);self.selection=card.body
        self.selected_label=self.cards.text(self.selection,'',10,T.FG)
        self.selection_chips=Chips(self.selection,self.select,self.focus_search)
        row=center.row(self.selection);install(row)
        self.compare_button=center.button(row,tr('查看对比','View comparison'),self.compare,True,width=130)
        center.button(row,tr('清空选择','Clear selection'),self.clear,width=115)
        self.browse_button=center.button(row,tr('返回资料列表','Back to library'),self.browse,width=145)
        self.results=tk.Frame(self.container,bg=T.BG);self.results.pack(fill='x')
        self.footer=center.row(self.container);install(self.footer);self.pager(self.footer)
        self.page_label=center.label(self.footer,'',9,T.MUTED);self.page_label.pack(side='left',padx=8)

    def pager(self,row,compact=False):
        previous=self.center.button(row,'\u2039' if compact else self.tr('上一页','Previous'),lambda:self.turn(-1),width=44 if compact else 86)
        box=Select(row,textvariable=self.page_number,values=[],width=9);box.pack(side='left',padx=4,pady=4);box.bind('<<ComboboxSelected>>',lambda _:self.go_page())
        following=self.center.button(row,'\u203a' if compact else self.tr('下一页','Next'),lambda:self.turn(1),width=44 if compact else 86)
        if compact:
            # Arrow-only pager buttons still name themselves on hover.
            from control_tooltip import Tooltip
            for button,text in ((previous,self.tr('上一页','Previous')),(following,self.tr('下一页','Next'))):
                tip=Tooltip(button);button.bind('<Enter>',lambda _,b=button,t=text,h=tip:h.request(t,t,b.winfo_rootx(),b.winfo_rooty()+b.winfo_height()),add='+');button.bind('<Leave>',lambda _,h=tip:h.hide(),add='+')
        self.pagers.append((previous,following));self.page_boxes.append(box)

    def install_actions(self,host):
        self.pagers=[pair for pair in self.pagers if all(button.winfo_exists() for button in pair)]
        self.page_boxes=[box for box in self.page_boxes if box.winfo_exists()]
        host.pack(fill='x',before=self.center.shell.scroll.master,pady=(0,8));install(host)
        from control_search import SearchField
        # One fixed row: the real search field (no separate "search" button that
        # only scrolls to it), the filter toggle, a compact pager and comparison.
        # Describe only what this view's text search actually matches; the car
        # filter narrows circuit recommendations separately.
        hint=self.tr('搜索赛道或地区','Search circuit or location') if self.view=='tracks' else self.tr('搜索车型、品牌或组别','Search car, brand or class')
        field=SearchField(host,textvariable=self.variables['query'],command=self.filter_changed,placeholder=hint,font=(T.FONT,11));field.flow_stretch=True
        field.configure(width=px(host,260));field.last=self.variables['query'].get()
        self.search_field=field;self.search_entry=field.entry
        self.filter_button=self.center.button(host,self.tr('筛选条件','Filters'),self.toggle_filters,width=110)
        # Cards read one entry deeply; the list shows every entry at once.
        from control_widgets import Segmented
        self.layout_var=tk.StringVar(host,value=self.state.get('layout','cards'))
        self.layout_switch=Segmented(host,self.layout_var,['cards','list'],self.set_layout,{'cards':self.tr('卡片','Cards'),'list':self.tr('列表','List')})
        self.layout_switch.configure(width=px(host,150));self.list_rows=getattr(self,'list_rows',[])
        from control_widgets import release_with
        release_with(self.layout_switch,self.layout_var)
        self.pager(host,compact=True)
        self.fixed_actions={'search':field,'filters':self.filter_button,
            'compare':self.center.button(host,self.tr('查看对比','View comparison'),lambda:self.browse() if self.state['mode']=='compare' else self.compare(),True,width=145)}
        self.sync_filters();self.update_selection();self.update_pagers()

    def set_layout(self):
        self.state['layout']=self.layout_var.get();self.state['page']=0;self.render(top=True)

    def listing(self,parent):
        """Overview first: every entry as one row; a row opens its full card in place."""
        from track_names import display
        box=tk.Frame(parent,bg=T.BG);box.pack(fill='x');expanded=self.state.setdefault('list_open',[]);gap=px(box,4)
        if len(self.rows)==1 and self.rows[0][0]['slug'] not in expanded:expanded.append(self.rows[0][0]['slug'])
        kind='tracks' if self.view=='tracks' else 'cars';rows=[]
        for item,recs in self.rows:
            slug=item['slug']
            if self.view=='tracks':
                title=display(item['name'],self.library.language)
                meta=self.library.text(item,'location')+' · '+item['length_km']+' km'+(' · DLC' if item.get('is_dlc') else '')
                count=self.tr('车型建议 ','Car picks ')+str(len(recs))
            else:
                title=item['name'];meta=item.get('car_class','');count=self.tr('推荐赛道 ','Recommended at ')+str(len(item.get('recommendations',[])))
            favorite=slug in self.library.favorites.get(kind,set())
            row=tk.Frame(box,bg=T.CARD,cursor='hand2',takefocus=True);row.pack(fill='x',pady=(0,gap))
            arrow=tk.Label(row,text='▸',bg=T.CARD,fg=T.MUTED,font=(T.FONT,10));arrow.pack(side='left',padx=(px(row,14),px(row,8)),pady=px(row,11))
            name=tk.Label(row,text=title,bg=T.CARD,fg=T.FG,font=(T.FONT,11,'bold'),anchor='w');name.pack(side='left')
            info=tk.Label(row,text=meta,bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='w');info.pack(side='left',padx=(px(row,12),0))
            tail=tk.Label(row,text=('★  ' if favorite else '')+count,bg=T.CARD,fg=T.ACCENT if favorite else T.MUTED,font=(T.FONT,9),anchor='e');tail.pack(side='right',padx=px(row,16))
            holder=tk.Frame(box,bg=T.BG);parts=(row,arrow,name,info,tail)
            def paint(on,parts=parts):
                for widget in parts:widget.configure(bg=T.HOVER if on else T.CARD)
            def toggle(_=None,slug=slug,item=item,recs=recs,holder=holder,arrow=arrow,row=row):
                if holder.winfo_manager():
                    for child in holder.winfo_children():child.destroy()
                    holder.pack_forget();arrow.configure(text='▸',fg=T.MUTED)
                    if slug in expanded:expanded.remove(slug)
                    return 'break'
                holder.pack(fill='x',after=row,pady=(0,px(box,10)))
                self.cards.track(holder,item,recs) if self.view=='tracks' else self.cards.car(holder,item)
                arrow.configure(text='▾',fg=T.ACCENT)
                if slug not in expanded:expanded.append(slug)
                return 'break'
            for widget in parts:
                widget.bind('<Button-1>',toggle);widget.bind('<Enter>',lambda _,p=paint:p(True));widget.bind('<Leave>',lambda _,p=paint:p(False))
            for key in ('<Return>','<space>'):row.bind(key,toggle)
            row.bind('<FocusIn>',lambda _,p=paint:p(True));row.bind('<FocusOut>',lambda _,p=paint:p(False))
            rows.append(row);row.guide_slug=slug;row.toggle=toggle
            if slug in expanded:toggle()
        for index,row in enumerate(rows):
            row.bind('<Down>',lambda _,i=index:(rows[min(len(rows)-1,i+1)].focus_set(),'break')[1])
            row.bind('<Up>',lambda _,i=index:(rows[max(0,i-1)].focus_set(),'break')[1])
        self.list_rows=rows

    def toggle_metadata(self):
        opened=not bool(self.metadata.winfo_manager());self.state['metadata']=opened
        if opened:
            from control_motion import expand
            expand(self.metadata,lambda:self.metadata.pack(fill='x',pady=6))
        else:self.metadata.pack_forget()
        self.metadata_button.configure(text=self.tr('资料说明 ▾','About this data ▾') if opened else self.tr('资料说明 ▸','About this data ▸'))

    def update_pagers(self):
        pages=max(1,(len(self.rows)+self.PAGE_SIZE-1)//self.PAGE_SIZE);page=max(0,min(pages-1,self.state['page']));self.state['page']=page;browsing=self.state['mode']=='browse' and self.state.get('layout')!='list'
        values=[f'{i+1} / {pages}' for i in range(pages)];self.page_number.set(values[page] if self.state.get('layout')!='list' else self.tr('全部 ','All ')+str(len(self.rows)))
        for previous,following in self.pagers:
            previous.configure(state='normal' if browsing and page>0 else 'disabled');following.configure(state='normal' if browsing and page<pages-1 else 'disabled')
        for box in self.page_boxes:box.configure(values=values,state='readonly' if browsing and pages>1 else 'disabled')

    def go_page(self):
        try:index=int(self.page_number.get().split('/')[0])-1
        except ValueError:return
        self.turn(index-self.state['page'])

    def filter_changed(self):
        self.remember_query()
        for key,values in self.choices.items():self.state[key]=values.get(self.variables[key].get(),'')
        self.render(top=True)

    def remember_query(self):
        self.state['query']=self.variables['query'].get()
        self.state['page']=0;self.state['mode']='browse';self.state.pop('browse_scroll',None)

    def toggle_filters(self):
        self.state['filters_open']=not self.state.get('filters_open',False);self.sync_filters(True)

    def sync_filters(self,animate=False):
        opened=bool(self.state.get('filters_open',False));active=[key for key in self.choices if self.state[key]]
        if opened and not self.filter_fields.winfo_manager():
            from control_motion import expand
            show=lambda:self.filter_fields.pack(fill='x',before=self.filter_tools)
            if animate:expand(self.filter_fields,show)
            else:show()
        elif not opened:self.filter_fields.pack_forget()
        title=self.tr('筛选条件','Filters')+(f' · {len(active)}' if active else '')
        button=self.filter_button
        if button is not None and button.winfo_exists():button.configure(text=title,selected=opened,width=max(px(button,110),button.font.measure(title)+px(button,36)))
        titles=dict(group=self.tr('组别','Class'),car=self.tr('车型','Car'),favorite=self.tr('收藏','Favorites'))
        self.filter_chips.set([] if opened else [(key,titles[key]+' · '+self.variables[key].get()) for key in active])
        self.reset_button.configure(state='normal' if active or self.state['query'] else 'disabled')

    def remove_filter(self,key):
        self.variables[key].set(next(iter(self.choices[key])));self.filter_changed()

    def render(self,top=False,restore=None):
        if self.job:
            self.center.root.after_cancel(self.job)
        self.job=None
        if self.closed:return
        field=self.search_field
        if field is not None and field.winfo_exists():
            if field.pending:field.after_cancel(field.pending);field.pending=None
            field.last=self.variables['query'].get()
        self.sync_filters();self.empty_action=None
        token=self.center.shell.cover_page() if self.initial_ready is None else None
        self.render_generation+=1;generation=self.render_generation
        if self.card_job:self.center.root.after_cancel(self.card_job);self.card_job=None
        self.center.shell.scroller.cancel()
        fraction=restore if restore is not None else 0 if top else self.center.scroll.yview()[0]
        if top:self.center.scroll.yview_moveto(0)
        for child in self.results.winfo_children():child.destroy()
        self.card_count=0;self.compare_buttons={};self.favorite_buttons={};self.rows=self.library.rows(self.view,self.state)
        if self.view=='tracks':text=self.tr('条赛道','circuits')+f" · {sum(len(recs) for _,recs in self.rows)} "+self.tr('条推荐','recommendations')
        else:text=self.tr('台车型','cars')
        self.result.configure(text=f'{len(self.rows)} '+text)
        self.update_selection()
        builders=[]
        if self.state['mode']=='compare':
            self.filter_card.pack_forget();self.footer.pack_forget()
            from control_guide_compare import Comparison
            def comparison():self.comparison=Comparison(self.results,self)
            builders.append(comparison)
            self.page_label.configure(text=self.tr('对比中 · 保留原赛道上下文','Comparing · original circuit context retained'))
        else:
            self.filter_card.pack(fill='x',pady=(0,12),before=self.selection.master if self.state['comparison'] else self.results);self.footer.pack(fill='x',pady=5)
            pages=max(1,(len(self.rows)+self.PAGE_SIZE-1)//self.PAGE_SIZE)
            self.state['page']=max(0,min(pages-1,self.state['page']));start=self.state['page']*self.PAGE_SIZE
            listing=self.state.get('layout')=='list'
            if listing and self.rows:
                self.footer.pack_forget();builders.append(lambda:self.listing(self.results))
            else:
                for item,recs in self.rows[start:start+self.PAGE_SIZE]:
                    builders.append(lambda item=item,recs=recs:self.cards.track(self.results,item,recs) if self.view=='tracks' else self.cards.car(self.results,item))
            if not self.rows:
                self.cards.text(self.results,self.tr('没有匹配的资料，试试重置筛选。','No matches. Try resetting filters.'),12,T.MUTED)
                label=self.tr('清空搜索，保留筛选','Clear search, keep filters') if self.state['query'] else self.tr('重置筛选','Reset filters')
                self.empty_action=self.center.button(self.results,label,self.clear_query if self.state['query'] else self.reset,width=200)
            self.page_label.configure(text='' if listing else f"{self.state['page']+1} / {pages} · "+self.tr('每页 3 张完整卡片','3 complete cards per page'))
        self.update_pagers()
        def finish():
            self.card_job=None
            if self.closed or generation!=self.render_generation:return
            # Settle the new document height before applying the requested view.
            self.center.root.update_idletasks()
            if self.closed or generation!=self.render_generation:return
            self.center.shell.scroller.cancel()
            self.center.scroll.yview_moveto(fraction)
            if self.state['mode']=='compare':self.card_count=len(self.state['comparison'])
            self.center.status.set(self.tr('完整原生图文 · 收藏仅保存在本机','Complete native library · favorites remain local'))
            if self.initial_ready is not None:
                ready=self.initial_ready;self.initial_ready=None;ready()
            else:self.center.shell.reveal_page(token)
        if getattr(self.center,'progressive',False):
            def next_card():
                self.card_job=None
                if self.closed or self.center.closing or generation!=self.render_generation:return
                try:
                    if builders:builders.pop(0)();self.card_count+=1;self.card_job=self.center.root.after(16,next_card)
                    else:finish()
                except Exception as error:self.center.pages.fail(error)
            self.card_job=self.center.root.after(16,next_card)
        else:
            for build in builders:build();self.card_count+=1
            self.center.root.update_idletasks();finish()

    def update_selection(self):
        self.selected_label.configure(text=self.tr('已选对比项目','Selected for comparison')+f" · {len(self.state['comparison'])} / 3")
        self.selection_chips.set([(key,self.library.name(key)) for key in self.state['comparison']])
        self.compare_button.configure(state='normal' if len(self.state['comparison'])>=2 and self.state['mode']!='compare' else 'disabled')
        self.browse_button.configure(state='normal' if self.state['mode']=='compare' else 'disabled')
        button=self.fixed_actions.get('compare')
        if button is not None and button.winfo_exists():
            comparing=self.state['mode']=='compare'
            button.configure(text=self.tr('返回资料列表','Back to library') if comparing else self.tr('查看对比','View comparison'),state='normal' if comparing or len(self.state['comparison'])>=2 else 'disabled')
        panel=self.selection.master
        if self.state['comparison']:panel.pack(fill='x',pady=(0,px(panel,18)),before=self.results)
        else:panel.pack_forget()

    def favorite(self,kind,slug):
        try:self.library.favorite(kind,slug)
        except OSError as error:self.center.status.set(self.tr('收藏保存失败：','Could not save favorite: ')+str(error));return
        if self.state['favorite']:self.render()
        else:
            for button in self.favorite_buttons.get((kind,slug),[]):
                button.label=('★ ' if slug in self.library.favorites[kind] else '☆ ')+self.tr('收藏','Favorite');button.paint()
    def select(self,key):
        if not self.library.toggle_comparison(self.state['comparison'],key):self.center.status.set(self.tr('最多选择 3 项，请先移除一项。','Select up to 3 items; remove one first.'));return
        if self.state['mode']=='compare':
            if len(self.state['comparison'])<2:self.browse()
            else:self.render()
        else:
            self.update_selection()
            for button in self.compare_buttons.get(key,[]):
                button.label=self.tr('移出对比','Remove') if key in self.state['comparison'] else self.tr('加入对比','Compare');button.primary=key in self.state['comparison'];button.paint()
            self.center.status.set(self.tr('已选 ','Selected ')+str(len(self.state['comparison']))+'/3')
    def compare(self):
        if len(self.state['comparison'])<2:self.center.status.set(self.tr('请先选择至少 2 项。','Choose at least 2 items first.'));return
        if self.state['mode']=='compare':return
        self.state['browse_scroll']=self.center.scroll.yview()[0]
        self.state['mode']='compare';self.render(top=True)
    def clear(self):
        comparing=self.state['mode']=='compare';self.state['comparison'].clear();self.state['mode']='browse';self.render(restore=self.state.get('browse_scroll',0) if comparing else None)
    def browse(self):
        if self.state['mode']!='compare':return
        self.state['mode']='browse';self.render(restore=self.state.get('browse_scroll',0))
    def clear_query(self):
        field=self.search_field
        if field is not None and field.winfo_exists():field.clear()
        else:self.variables['query'].set('');self.filter_changed()
    def reset(self):
        self.state.update(query='',group='',car='',favorite='',page=0,mode='browse')
        self.variables['query'].set('')
        for key,values in self.choices.items():self.variables[key].set(next(iter(values)))
        self.filter_changed()
    def language(self):self.center.toggle_language()
    def turn(self,delta):
        if self.state['mode']!='browse':return
        pages=max(1,(len(self.rows)+self.PAGE_SIZE-1)//self.PAGE_SIZE);target=max(0,min(pages-1,self.state['page']+delta))
        if target==self.state['page']:self.update_pagers();return
        self.state['page']=target;self.render(top=True)
    def jump(self,view,slug):
        target=self.center.guide_state.setdefault(view,{})
        target.update(query=self.library.data[view][slug]['name'],group='',car='',favorite='',page=0,mode='browse')
        self.center.show_page(4 if view=='tracks' else 5,progressive=True)


def show(center,view):
    center.guide_page=GuidePage(center,view)
