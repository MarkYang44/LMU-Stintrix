"""Private table presentation preferences; rows and selection are never rewritten."""
import json,math
import tkinter as tk
from pathlib import Path
from storage import atomic_json
from control_theme import T
from control_widgets import Switch
from i18n import tr


def load(root):
    path=Path(root)/'table_views.json'
    if not path.exists():return dict(version=1,tables={})
    if path.stat().st_size>262144:raise ValueError('表格设置文件过大')
    try:value=json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError,OSError) as error:raise ValueError('表格设置无法读取，原文件已保留') from error
    if not isinstance(value,dict) or value.get('version')!=1 or not isinstance(value.get('tables'),dict):raise ValueError('表格设置格式无效')
    return value


def checked(value,table):
    if not isinstance(value,dict):raise ValueError('表格设置格式无效')
    visible=value.get('visible',table.columns);frozen=value.get('frozen',[k for k in ('date','track') if k in visible]);widths=value.get('widths',{})
    if not isinstance(visible,list) or not visible or any(k not in table.columns for k in visible) or len(set(visible))!=len(visible):raise ValueError('至少保留一列')
    if not isinstance(frozen,list) or any(k not in visible for k in frozen) or not isinstance(widths,dict):raise ValueError('表格设置格式无效')
    for key,width in widths.items():
        if key not in table.columns or isinstance(width,bool) or not isinstance(width,(float,int)) or not math.isfinite(width) or not 40<=width<=1600:raise ValueError('列宽无效')
    return dict(visible=list(visible),frozen=[k for k in visible if k in frozen],widths=widths)


def install(app,table,key,filters=None,frozen=None):
    table.copy_feedback=app.status.set
    defaults=dict(visible=list(table.columns),frozen=[k for k in (frozen if frozen is not None else ('date','track')) if k in table.columns],widths={k:round(v/table.s,2) for k,v in table.widths.items()})
    def apply(value):table.configure_columns(value['visible'],value['frozen'],{k:v*table.s for k,v in value['widths'].items()})
    from control_table_layouts import compact,install as install_layouts
    initial=compact(table,defaults) if key in ('review','history') else defaults
    try:apply(checked(load(app.data_path)['tables'].get(key,initial),table))
    except (OSError,ValueError) as error:app.status.set(tr(str(error)))
    def persist(value,previous=None):
        value=checked(value,table);all_values=load(app.data_path);old=all_values['tables'].get(key,{})
        if not isinstance(old,dict):raise ValueError('表格设置格式无效')
        saved={**old,**value}
        if previous is not None:saved['previous_layout']=checked(previous,table)
        all_values['tables'][key]=saved;atomic_json(Path(app.data_path)/'table_views.json',all_values);apply(value)
    def snapshot():return dict(visible=list(table.displaycolumns),frozen=list(table.frozen_columns),widths={k:v/table.s for k,v in table.widths.items()})
    install_layouts(app,table,key,defaults,persist,snapshot)
    def remember():
        try:persist(dict(visible=table.displaycolumns,frozen=table.frozen_columns,widths={k:round(v/table.s,2) for k,v in table.widths.items()}))
        except (OSError,ValueError) as error:app.status.set(tr(str(error)))
    table.columns_changed=remember
    if filters is not None:
        filters.column_editor=lambda:show()
        from control_table_sort import install as install_sort
        install_sort(table,filters)
    else:app.button(app.row(table.master),'列设置',lambda:show(),False,95)
    def show():
        import control_confirm
        old=getattr(table,'preferences_window',None)
        if old is not None and old.winfo_exists():old.lift();return old
        from control_window import window as sheet,fit,note
        from control_widgets import px
        window=sheet(app.root,'列设置','选择显示的列；固定列在横向滚动时保持可见，至少保留一列。拖动表头边界可调整列宽。',escape=False,transient=False);table.preferences_window=window
        from control_video_widgets import ScrollPage
        feedback=note(window.body,'',9,T.ACCENT);feedback.pack(fill='x',pady=(0,px(window,6)))
        scroll=ScrollPage(window.body);scroll.pack(fill='both',expand=True);window.bind('<MouseWheel>',lambda e:scroll.wheel(e.delta))
        surface=tk.Frame(scroll.body,bg=T.CARD);surface.pack(fill='x',padx=(0,px(window,10)))
        body=tk.Frame(surface,bg=T.CARD);body.pack(fill='x',padx=px(window,16),pady=px(window,10))
        heading=app.row(body);heading.columnconfigure(0,weight=1);heading.columnconfigure(1,minsize=px(window,84));heading.columnconfigure(2,minsize=px(window,84))
        for col,title in enumerate(('列名称','显示','固定')):app.label(heading,title,9,T.MUTED).grid(row=0,column=col,sticky='w',padx=6)
        visible={};frozen={};pins={};traces=[];state=dict(reset=False,baseline=None,loading=True)
        drafts=getattr(app,'column_drafts',None)
        if drafts is None:drafts=app.column_drafts={}
        status=tk.StringVar(window);dirty=window.status;feedback.configure(textvariable=status)
        def snapshot():
            return dict(visible={k:v.get() for k,v in visible.items()},frozen={k:v.get() for k,v in frozen.items()},reset=state['reset'])
        def is_dirty():return snapshot()!=state['baseline']
        def changed(*_):
            for col in pins:pins[col].configure(state='normal' if visible[col].get() else 'disabled')
            if not state['loading']:dirty.set(tr('有未保存修改' if is_dirty() else '列设置与已保存值一致'))
        for col in table.columns:
            row=app.row(body);row.pack_configure(pady=1);row.columnconfigure(0,weight=1);row.columnconfigure(1,minsize=px(window,84));row.columnconfigure(2,minsize=px(window,84))
            v=tk.BooleanVar(window,value=col in table.displaycolumns);f=tk.BooleanVar(window,value=col in table.frozen_columns);visible[col]=v;frozen[col]=f
            app.label(row,table.labels[col],10).grid(row=0,column=0,sticky='w',padx=6)
            Switch(row,'',v,lambda:None,compact=True).grid(row=0,column=1,sticky='w',padx=6)
            pin=Switch(row,'',f,lambda:None,compact=True);pin.grid(row=0,column=2,sticky='w',padx=6);pins[col]=pin
        state['baseline']=snapshot()
        remembered=drafts.get(key)
        if remembered:
            for col in table.columns:
                visible[col].set(remembered['visible'].get(col,True));frozen[col].set(remembered['frozen'].get(col,False))
            state['reset']=remembered['reset']
        state['loading']=False
        def save():
            try:
                widths=defaults['widths'] if state['reset'] else {k:round(v/table.s,2) for k,v in table.widths.items()}
                order=defaults['visible'] if state['reset'] else list(table.displaycolumns)+[k for k in table.columns if k not in table.displaycolumns]
                persist(dict(visible=[k for k in order if visible[k].get()],frozen=[k for k,v in frozen.items() if v.get() and visible[k].get()],widths=widths))
                state['reset']=False;state['baseline']=snapshot();drafts.pop(key,None);changed();status.set(tr('列设置已保存'));return True
            except (OSError,ValueError) as error:status.set(tr(str(error)));return False
        window.add_action('应用并记住',save,True,120)
        def reset():
            if is_dirty():
                answer=control_confirm.draft_choice(window,save_label='应用并记住')
                if answer=='cancel':return
                if answer=='save' and not save():return
            for col in table.columns:visible[col].set(True);frozen[col].set(col in defaults['frozen'])
            state['reset']=True;changed();status.set(tr('默认列已填入，应用后生效'))
        window.add_action('恢复默认列',reset,False,110);window.add_action('关闭',lambda:close(),False,90)
        def keep():
            if is_dirty():drafts[key]=snapshot()
        def close(after=None,exiting=False):
            if is_dirty():
                answer=control_confirm.draft_choice(window,closing=True,exiting=exiting,save_label='应用并记住')
                if answer=='cancel':return
                if answer=='save' and not save():return
                if answer=='keep':keep()
                if answer=='discard':drafts.pop(key,None)
            window.destroy()
            if after:after()
        def dispose(event):
            if event.widget is window:
                if table.winfo_exists():table.unbind('<Destroy>',destroy_binding)
                for variable,token in traces:variable.trace_remove('write',token)
                for variable in [*visible.values(),*frozen.values(),status]:variable.__del__();variable._tk=None
        window.bind('<Destroy>',dispose,add='+')
        def close_with_table(event):
            if event.widget is table and window.winfo_exists():keep();window.destroy()
        destroy_binding=table.bind('<Destroy>',close_with_table,add='+')
        for variable in [*visible.values(),*frozen.values()]:traces.append((variable,variable.trace_add('write',changed)))
        changed();window.on_close=close;window.bind('<Escape>',lambda _:(close(),'break')[1]);control_confirm.register(app,window,close)
        window.column_visible=visible;window.column_frozen=frozen;window.column_save=save;window.column_status=status;window.column_close=close;window.column_dirty=is_dirty;window.column_pins=pins;window.column_reset=reset
        fit(window,540,660,minimum=(460,420));return window
    table.show_columns=show;table.remember_columns=remember
