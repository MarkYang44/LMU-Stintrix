"""One native filter surface for review, PB, podium, history and official results."""
import tkinter as tk
from tkinter import simpledialog
from pathlib import Path
from collections import Counter
from control_fields import Select,Field
from control_theme import T
from control_widgets import px
from i18n import tr
from event_filters import DEFAULTS,CHOICES,SORTS,filtered,layout_key,limits
from event_catalog import normalize
from race_model import read_json
from storage import atomic_json
from track_names import display,layout

PERIODS=('全部时间','今天','最近 7 天','最近 30 天')
BUILTINS={'线上 LMGT3 正赛':dict(mode='online',vehicle_class='LMGT3',phase='Race'),'同组领奖台':dict(outcome='podium',phase='Race'),'采样缺口待检查':dict(quality='gaps'),'已收藏赛事':dict(favorite='yes')}
SHORT_SORTS=('最新优先','最早优先','阶段 ↑','阶段 ↓','赛道 ↑','赛道 ↓','车辆 ↑','车辆 ↓','线下优先','线上优先','最快圈优先','同组名次','同组提升','总名次','总提升','比赛最长','最稳定','记录最长')
SHORT_SORTS+=('圈速 ↓','同组名次 ↓')

class EventControls(tk.Frame):
    def __init__(self,parent,app,callback,key):
        super().__init__(parent,bg=T.CARD);self.app=app;self.callback=callback;self.key=key;self.items=[];self.variables={};self.choices={};self.lookup={};self.tiles=[]
        self.path=Path(app.data_path)/'EventCatalog/views.json';self.path.parent.mkdir(parents=True,exist_ok=True);saved=read_json(self.path,{})
        self.state={**DEFAULTS,**saved.get('states',{}).get(key,{}),**getattr(app,key,{})};setattr(app,key,self.state)
        self.basic=tk.Frame(self,bg=T.CARD);self.basic.pack(fill='x');self.advanced=tk.Frame(self,bg=T.CARD);self.titles={}
        fields=[('track','赛道'),('layout','具体布局'),('vehicle_class','车辆组别'),('car','车型')]
        advanced=[('phase','阶段'),('mode','参赛方式'),('period','时间范围（UTC）'),('team','车队'),('outcome','比赛成绩'),('trust','成绩依据'),('quality','数据质量'),('weather','已记录圈天气'),('front','前轮胎种'),('rear','后轮胎种'),('source','记录来源'),('favorite','收藏'),('traffic','交通人工标记'),('tag','标签'),('available','可用数据'),('start','开始日期（UTC）'),('end','结束日期（UTC）'),('min_laps','至少有效完整圈'),('fuel_min','圈起点油量 ≥ L'),('fuel_max','圈起点油量 ≤ L'),('temp_min','赛道温度 ≥ °C'),('temp_max','赛道温度 ≤ °C'),('tc_min','TC ≥'),('tc_max','TC ≤'),('abs_min','ABS ≥'),('abs_max','ABS ≤'),('duration_min','比赛时长 ≥ 分钟'),('duration_max','比赛时长 ≤ 分钟')]
        for parent,spec in ((self.basic,fields),(self.advanced,advanced)):
            group=[]
            for name,label in spec:
                self.titles[name]=label
                tile=tk.Frame(parent,bg=T.CARD);group.append(tile);self.tiles.append(tile)
                app.label(tile,label,9,T.MUTED).pack(anchor='w',pady=(3,4));var=tk.StringVar(self);self.variables[name]=var
                if name in ('start','end','min_laps') or name.endswith(('_min','_max')):
                    w=Field(tile,textvariable=var,width=16);w.entry.bind('<Return>',lambda _:self.apply());w.entry.bind('<FocusOut>',lambda _:self.apply())
                else:
                    w=Select(tile,textvariable=var,width=18);self.choices[name]=w;w.bind('<<ComboboxSelected>>',lambda _:self.apply())
                w.pack(fill='x')
            parent.bind('<Configure>',lambda e,p=parent,g=group:self.arrange(e,p,g))
        tools=app.row(self);self.toggle_button=app.button(tools,'更多筛选',self.toggle,False,90)
        app.button(tools,'重置筛选',self.reset,False,100)
        self.variables['sort']=tk.StringVar(self);self.titles['sort']='排序';self.choices['sort']=Select(tools,textvariable=self.variables['sort'],width=13);self.choices['sort'].pack(side='left',padx=5);self.choices['sort'].bind('<<ComboboxSelected>>',lambda _:self.apply())
        self.view=tk.StringVar(self);self.viewbox=Select(tools,textvariable=self.view,width=13);self.viewbox.pack(side='left',padx=5);self.viewbox.bind('<<ComboboxSelected>>',lambda _:self.restore())
        from control_action_menu import ActionMenu,MenuAction
        manage=app.button(tools,'视图 / 列',lambda:menu.toggle(),False,92)
        menu=ActionMenu(manage,[MenuAction('save','保存视图',self.save_view,hint='保存当前筛选、排序与搜索条件'),
            MenuAction('columns','列设置',lambda:self.column_editor(),enabled=lambda:hasattr(self,'column_editor'),hint='显示、隐藏与固定列；拖动表头边界调整列宽'),
            MenuAction('delete','删除视图',self.delete_view,enabled=lambda:self.view.get() not in BUILTINS and self.view.get() in self.views,hint='选择已保存的自定义视图后可删除',danger=True)],'管理视图')
        tools.bind('<Configure>',lambda e:self.arrange_toolbar(e,tools))
        # A sibling can be packed inside this panel or above its table. Keeping
        # one set of chips avoids hiding active conditions with the disclosure.
        self.chips=tk.Frame(self.master,bg=T.CARD);self.chip_widgets=[];self.compact_target=None;self.chips.bind('<Configure>',lambda _:self.arrange_chips())
        self.bind('<Destroy>',self.dispose_chips,add='+')
        self.summary=tk.StringVar(self);self.summary_label=app.label(self,self.summary,9,T.MUTED);self.summary_label.pack(fill='x',pady=4)
        self.selection_detail=tk.StringVar(self);self.detail=app.label(self,self.selection_detail,9,T.ACCENT);self.detail.bind('<Configure>',lambda e:self.detail.configure(wraplength=max(100,e.width)))
        self.hint=app.label(self,'天气与车辆条件仅代表已记录有效圈；最快圈页按候选圈条件筛选后再选纪录。比赛时长缺少起终点时不推算。',9,T.MUTED);self.hint.bind('<Configure>',lambda e:self.hint.configure(wraplength=max(100,e.width)))
        self.update_views();self.update_options([]);self.pack(fill='x',pady=8)
        if getattr(app,'filter_expansion',{}).get(key):self.toggle()
    def arrange_toolbar(self,event,parent):
        if not parent.winfo_exists():return
        self.flow(parent,[w for w in parent.winfo_children() if not isinstance(w,(tk.Menu,tk.Toplevel))],event.width)
    def flow(self,parent,children,width):
        gap=px(self,8);x=y=line=0
        for w in children:
            if not w.winfo_exists():continue
            w.pack_forget();w.grid_forget();w.place_forget()
            size=min(max(1,width),w.winfo_reqwidth());height=w.winfo_reqheight()
            if x and x+size>width:y+=line+gap;x=line=0
            w.place(x=x,y=y,width=size,height=height);x+=size+gap;line=max(line,height)
        parent.pack_propagate(False);parent.configure(height=max(1,y+line))
    def arrange(self,event,parent,tiles):
        cols=max(1,min(4,event.width//px(self,165)))
        for i in range(4):parent.columnconfigure(i,weight=1 if i<cols else 0,uniform='facets' if i<cols else '')
        for i,tile in enumerate(tiles):tile.grid(row=i//cols,column=i%cols,sticky='ew',padx=(0,px(self,10)) if i%cols<cols-1 else 0,pady=(0,px(self,6)))
    def toggle(self):
        if not hasattr(self.app,'filter_expansion'):self.app.filter_expansion={}
        self.app.filter_expansion[self.key]=not bool(self.advanced.winfo_manager())
        if self.advanced.winfo_manager():self.advanced.pack_forget();self.hint.pack_forget()
        else:self.advanced.pack(fill='x',after=self.basic);self.hint.pack(fill='x',pady=3)
    def update_views(self):
        value=read_json(self.path,{});self.views={**BUILTINS,**value.get('views',{})}
        self.viewbox.compact_labels={'线上 LMGT3 正赛':'线上 GT3','同组领奖台':'领奖台','采样缺口待检查':'检查缺口','已收藏赛事':'已收藏'}
        self.viewbox.configure(values=[tr('常用视图'),*self.views]);self.view.set(tr('常用视图'))
    def persist(self):
        value=read_json(self.path,{});value.setdefault('states',{})[self.key]=dict(self.state);atomic_json(self.path,value)
    def save_view(self):
        name=simpledialog.askstring(tr('保存视图'),tr('输入视图名称'),parent=self.app.root)
        if not name or not name.strip():return
        name=name.strip()[:60]
        if name in BUILTINS:self.app.status.set(tr('内置视图名称不可覆盖'));return
        value=read_json(self.path,{});view=dict(self.state)
        if hasattr(self,'query'):view['query']=self.query.get()
        value.setdefault('views',{})[name]=view;atomic_json(self.path,value);self.update_views();self.view.set(name)
    def delete_view(self):
        name=self.view.get();value=read_json(self.path,{})
        if name in value.get('views',{}):value['views'].pop(name);atomic_json(self.path,value);self.update_views()
    def restore(self):
        if self.view.get() not in self.views:return
        self.state.clear();self.state.update(DEFAULTS);self.state.update(self.views[self.view.get()]);self.update_options(self.items);self.persist();self.notify_query(self.state.get('query',''))
    def reset(self):
        self.state.clear();self.state.update(DEFAULTS);self.update_options(self.items);self.persist();self.notify_query('')
    def notify_query(self,value):
        if hasattr(self,'query') and self.query.get()!=value:
            self.query.set(value)
        # A visual StringVar trace (e.g. the search clear icon) does not repopulate a table.
        self.callback()
    def bind_query(self,variable):
        self.query=variable;variable.set(self.state.get('query',''))
    def apply(self):
        proposed=dict(self.state)
        for key,var in self.variables.items():proposed[key]=self.lookup[key].get(var.get(),self.state.get(key,'')) if key in self.lookup else var.get().strip()
        if proposed.get('track')!=self.state.get('track'):proposed['layout']=''
        try:limits(proposed);filtered([],proposed)
        except ValueError as error:self.app.status.set(tr(str(error)));return
        if proposed==self.state:return
        if hasattr(self,'query'):proposed['query']=self.query.get()
        self.state.update(proposed);self.update_options(self.items);self.persist();self.callback()
    def update_options(self,items):
        self.items=items;facets=[normalize(e) for e in items]
        for key in self.choices:
            if key=='period':mapping=dict(enumerate(PERIODS))
            elif key=='sort':mapping=dict(enumerate(SORTS))
            elif key in CHOICES:mapping=CHOICES[key][1]
            else:
                mapping={'':{'track':'全部赛道','layout':'全部布局','vehicle_class':'全部组别','car':'全部车型','team':'全部车队','front':'全部前胎','rear':'全部后胎','tag':'全部标签'}[key]};counts=Counter()
                for f in facets:
                    if key=='layout' and self.state.get('track') and f.get('track')!=self.state['track']:continue
                    values=f.get(key+'_tyres',[]) if key in ('front','rear') else f.get('tags',[]) if key=='tag' else [layout_key(f)] if key=='layout' else [f.get('vehicle' if key=='car' else key,'')]
                    for v in values:
                        if not v:continue
                        counts[v]+=1
                        mapping[v]=layout(f.get('track'),f.get('layout'),f.get('length_m')) if key=='layout' else display(v) if key=='track' else v
                mapping={k:mapping[k] for k in sorted(mapping,key=lambda v:(v!='',str(mapping[v]).casefold()))}
                mapping={k:str(v)+(f' ({counts[k]})' if k else '') for k,v in mapping.items()}
            current=self.state.get(key,DEFAULTS[key])
            if current not in mapping:mapping={**mapping,current:str(current)}
            labels={};seen=set()
            for value,label in mapping.items():
                label=tr(str(label))
                if label in seen:label+=' · '+str(value)
                seen.add(label);labels[label]=value
            self.lookup[key]=labels
            if key=='sort':self.choices[key].compact_labels={label:SHORT_SORTS[index] for label,index in labels.items() if 0<=index<len(SHORT_SORTS)}
            self.choices[key].configure(values=list(labels));self.variables[key].set(next(label for label,v in labels.items() if v==current))
        for key,var in self.variables.items():
            if key not in self.choices:var.set(self.state.get(key,''))
        self.update_chips()
    def update_chips(self):
        focused=self.chips.focus_get() in self.chip_widgets
        for w in self.chip_widgets:w.destroy()
        self.chip_widgets=[]
        for key,value in self.state.items():
            if key not in self.variables or value in ('',None) or value==DEFAULTS.get(key):continue
            text=self.variables[key].get()
            if key in ('start','end','min_laps') or key.endswith(('_min','_max')):text=tr(self.titles[key])+' '+str(value)
            text=tr(self.titles[key])+' · '+text if key in self.choices else text
            self.chip_widgets.append(self.app.button(self.chips,text+' ×',lambda k=key:self.remove(k),False,105))
        if any(v!=DEFAULTS.get(k) for k,v in self.state.items() if k in self.variables and k!='sort'):
            self.chip_widgets.append(self.app.button(self.chips,'清除条件',self.clear_conditions,False,100))
        for w in self.chip_widgets:w.configure(height=px(w,34))
        self.sync_chips();self.arrange_chips()
        if focused:
            if self.chip_widgets:self.chip_widgets[0].focus_set()
            elif self.compact_target is not None:self.compact_target.viewport.focus_set()
    def compact(self,before):
        self.compact_target=before;self.sync_chips()
    def sync_chips(self):
        if not self.chips.winfo_exists():return
        expanded=bool(self.winfo_manager()) or self.compact_target is None
        parent=self if expanded else self.master;before=self.summary_label if expanded else self.compact_target
        if not self.chip_widgets:self.chips.pack_forget();return
        current=self.chips.pack_info() if self.chips.winfo_manager() else {}
        if current.get('in') is not parent:
            self.chips.pack_forget();self.chips.pack(in_=parent,fill='x',pady=(4,0),before=before)
            self.arrange_chips()
    def dispose_chips(self,event):
        if event.widget is self and self.chips.winfo_exists():self.chips.destroy()
    def clear_conditions(self):
        for key in self.variables:
            if key!='sort':self.state[key]=DEFAULTS[key]
        if hasattr(self,'query'):self.state['query']=self.query.get()
        self.update_options(self.items);self.persist();self.callback()
    def arrange_chips(self):
        self.flow(self.chips,self.chip_widgets,max(190,self.chips.winfo_width()))
    def remove(self,key):
        self.state[key]=DEFAULTS[key]
        if key=='track':self.state['layout']=''
        if hasattr(self,'query'):self.state['query']=self.query.get()
        self.update_options(self.items);self.persist();self.callback()
    def pairs(self,values,query=''):
        if hasattr(self,'sort_table'):self.sort_table()
        if hasattr(self,'query'):self.state['query']=self.query.get()
        try:rows=filtered(values,self.state,query)
        except ValueError as error:self.app.status.set(tr(str(error)));return []
        self.summary.set(tr('显示 ')+str(len(rows))+tr(' / 共 ')+str(len(values))+tr(' 条；括号内为当前资料库选项数'))
        return rows
    def describe(self,entry=None):
        from event_filters import TRUST,QUALITY
        if not entry:self.selection_detail.set('');self.detail.pack_forget();return
        f=normalize(entry);scope=tr('最快圈条件') if f.get('condition_scope')=='fastest_lap' else tr('已记录有效圈条件')
        self.selection_detail.set(tr(TRUST.get(f.get('trust'),'未知'))+' · '+tr(QUALITY.get(f.get('quality'),'完整性未知'))+' · '+scope)
        if not self.detail.winfo_manager():self.detail.pack(fill='x',pady=3)

def replace_rows(table,rows,selected=()):
    """Keep selection and pixel scroll for a sort/filter refresh."""
    offset=table.offset;xoffset=table.xoffset
    table.replace(rows,selected);table.offset=min(offset,max(0,len(rows)*table.rowheight-table.viewport.winfo_height()));table.xoffset=xoffset

def edit_note(app,entry,done):
    from control_notes import show
    return show(app,entry,done)
