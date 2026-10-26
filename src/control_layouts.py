"""Named layout drafts, visual editing and explicit apply/restore boundaries."""
import tkinter as tk
from tkinter import simpledialog,messagebox
from copy import deepcopy
import math
from control_fields import Field,Select
from control_widgets import Switch
from control_theme import T
from hud_layouts import LayoutStore,KINDS,normalize,numeric_bounds
from control_layout_preview import LayoutPreview
from i18n import tr
import layout_actions
import control_confirm
from control_validation import Feedback
from preference_error import PreferenceError

TITLES={'main':'油刹 / 转向','tyres':'轮胎','strategy':'燃油与能量','pit':'进站分析','stint':'Stint 节奏','weather':'天气与赛道'}
MODES={'normal':'标准面板','curves':'纯净 · 仅曲线','controls':'纯净 · 曲线 + 踏板 / 方向盘'}


def show(app):
    old=getattr(app,'layout_window',None)
    if old is not None and old.winfo_exists():old.deiconify();old.lift();return old
    try:initial=layout_actions.current(app.data_path,app.hud if app.active() else None)
    except (ValueError,OSError) as error:
        messagebox.showerror(tr('布局无法打开'),tr(str(error)),parent=app.root);return
    window=tk.Toplevel(app.root);app.layout_window=window;window.title(tr('HUD 布局与备份'));window.configure(bg=T.BG);window.geometry('900x820');window.minsize(720,580)
    from control_video_widgets import ScrollPage
    scroll=ScrollPage(window);scroll.pack(fill='both',expand=True)
    window.bind('<MouseWheel>',lambda e:scroll.wheel(e.delta) if not isinstance(e.widget,Select) else None)
    body=tk.Frame(scroll.body,bg=T.CARD);body.pack(fill='both',expand=True,padx=16,pady=12)
    store=LayoutStore(app.data_path);variables=[];traces=[];remembered=getattr(app,'layout_draft',None);errors=Feedback()
    def var(value='',boolean=False):
        result=tk.BooleanVar(window,value=value) if boolean else tk.StringVar(window,value=value);variables.append(result);return result
    def hud():return app.hud if app.active() else None
    state={'draft':deepcopy(initial),'panel':'main','history':{},'loading':True,'baseline':None,'pending':None}
    status=var();dirty=var();selected=var();name=var();kind=var('main');visible=var(True,True);top=var(True,True);lock=var(False,True);mode=var('normal');wave=var('10');backup=var();snap=var(False,True)
    def section(title):app.label(body,title,11,T.FG).pack(anchor='w',pady=(10,6))
    section('选择布局')
    row=app.row(body);chooser=Select(row,textvariable=selected,values=(),width=25);chooser.pack(side='left',fill='x',expand=True)
    app.button(row,'应用所选布局',lambda:guard(apply_selected),False,140)
    tile=tk.Frame(body,bg=T.CARD);tile.pack(fill='x');row=app.row(tile);app.label(row,'布局名称',10).pack(side='left',padx=(0,12));name_field=Field(row,textvariable=name);name_field.pack(side='left',fill='x',expand=True);errors.add('name',name_field,'布局名称',app.label(tile,'',9,T.RED))
    section('编辑面板')
    row=app.row(body);panel=Select(row,textvariable=kind,values=KINDS,labels=TITLES,width=23);panel.pack(side='left')
    Switch(row,'显示该面板',visible,lambda:None,compact=True).pack(side='left',padx=12)
    row=app.row(body);Switch(row,'10 px 网格吸附',snap,lambda:None,compact=True).pack(side='left')
    hint=app.label(body,'拖拽移动 · 右下角缩放 · 方向键 1 px / Shift 10 px',9,T.MUTED);hint.pack(fill='x');hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(100,e.width)))
    def preview_data():
        try:return collect()
        except ValueError:return None
    def preview_select(key):
        if not guard(collect):return False
        state['panel']=key;kind.set(key);load_panel();return True
    def preview_change(key,values):
        state['draft']['panels'][key].update(values);load_panel();changed()
    preview=LayoutPreview(body,preview_data,lambda:state['panel'],preview_select,preview_change,snap.get,TITLES);preview.pack(fill='x',pady=6)
    row=app.row(body);app.button(row,'−',lambda:preview.zoom_at(1/1.25),False,44);app.button(row,'+',lambda:preview.zoom_at(1.25),False,44)
    app.button(row,'适合全部显示器',preview.fit_all,False,150);app.button(row,'聚焦所选面板',preview.fit_selected,False,145)
    app.label(body,'滚轮缩放；中键或拖动空白处平移。',9,T.MUTED).pack(anchor='w')
    app.label(body,'预览仅修改草稿；保存并应用后才改变 HUD。虚线表示隐藏面板。',9,T.MUTED).pack(anchor='w',pady=(0,4))
    fields={};grid=tk.Frame(body,bg=T.CARD);grid.pack(fill='x',pady=2)
    for index,(key,label) in enumerate([('x','水平位置 / px'),('y','垂直位置 / px'),('width','宽度 / px'),('height','高度 / px'),('opacity','不透明度 / %')]):
        tile=tk.Frame(grid,bg=T.CARD);tile.grid(row=index//3,column=index%3,sticky='ew',padx=(0,12),pady=3);grid.columnconfigure(index%3,weight=1)
        app.label(tile,label,9,T.MUTED).pack(anchor='w');fields[key]=var();field=Field(tile,textvariable=fields[key],width=18);field.pack(fill='x',pady=2)
        errors.add(key,field,label,app.label(tile,'',9,T.RED));field.entry.bind('<FocusOut>',lambda _,k=key:validate_field(k),add='+')
        traces.append((fields[key],fields[key].trace_add('write',lambda *_,k=key:errors.clear(k))))
    row=app.row(body);Select(row,textvariable=mode,values=tuple(MODES),labels=MODES,width=27).pack(side='left')
    app.label(row,'波形窗口 / 秒',9,T.MUTED).pack(side='left',padx=10);Select(row,textvariable=wave,values=('5','10','20'),width=8).pack(side='left')
    row=app.row(body);Switch(row,'窗口置顶',top,lambda:None,compact=True).pack(side='left',padx=(0,20));Switch(row,'鼠标穿透 / 锁定位置',lock,lambda:None,compact=True).pack(side='left')
    app.button(body,'备份与恢复 ▾',lambda:toggle_backup(),False,150)
    recovery=tk.Frame(body,bg=T.CARD)
    app.label(recovery,'切换、覆盖与恢复前自动备份，保留最近 12 次。恢复会还原当时的布局列表和画面。',9,T.MUTED).pack(fill='x',pady=6)
    row=app.row(recovery);history=Select(row,textvariable=backup,values=(),width=39);history.pack(side='left',fill='x',expand=True)
    app.button(row,'恢复所选备份',lambda:guard(restore),False,140)
    row=app.row(recovery);app.button(row,'备份当前 HUD',lambda:guard(backup_now),False,145)
    app.button(row,'删除所选布局',lambda:guard(delete),False,145)
    footer=tk.Frame(window,bg=T.BG);footer.pack(side='bottom',fill='x',padx=16,pady=8)
    app.label(footer,dirty,9,T.MUTED).pack(anchor='w',pady=3)
    row=app.row(footer);app.button(row,'保存并应用',lambda:guard(save),True,135);app.button(row,'另存为',lambda:guard(copy),False,105)
    app.button(row,'读取当前 HUD',lambda:guard(read_live),False,140)
    feedback=app.label(footer,status,9,T.ACCENT);feedback.pack(fill='x',pady=3);feedback.bind('<Configure>',lambda e:feedback.configure(wraplength=max(100,e.width)))
    def toggle_backup():
        if recovery.winfo_manager():recovery.pack_forget()
        else:recovery.pack(fill='x',pady=5)
    def guard(action):
        try:action();return True
        except (ValueError,OSError,tk.TclError) as error:status.set(tr(str(error)));errors.show(error);return False
    def refresh():
        value=store.load();chooser.configure(values=list(value['profiles']));selected.set(value.get('active',''));name.set(selected.get())
        state['history']={h['time'][:19].replace('T',' ')+' UTC · '+tr({'save':'保存','switch':'切换','restore':'恢复','backup':'手动备份','delete':'删除'}.get(h['reason'],h['reason']))+' · '+h['id'][:5]:h['id'] for h in reversed(value['history'])}
        history.configure(values=list(state['history']));backup.set(next(iter(state['history']),''))
    def load_panel():
        was=state['loading'];state['loading']=True
        p=state['draft']['panels'][state['panel']]
        for key,v in fields.items():v.set(f"{p[key]*100:g}" if key=='opacity' else str(p[key]))
        visible.set(p['visible']);state['loading']=was
    def load_draft():
        state['loading']=True;mode.set(state['draft']['mode']);wave.set(state['draft']['window']);top.set(state['draft']['topmost']);lock.set(state['draft']['clickthrough']);load_panel();state['loading']=False
        preview.paint()
    def collect():
        draft=deepcopy(state['draft']);p=draft['panels'][state['panel']]
        for key,v in fields.items():
            try:number=float(v.get())/(100 if key=='opacity' else 1)
            except ValueError:raise PreferenceError('请输入有效数值',key) from None
            low,high=numeric_bounds(key)
            if not math.isfinite(number) or not low<=number<=high:raise PreferenceError(tr('允许范围')+f'：{low*100:g}–{high*100:g}' if key=='opacity' else tr('允许范围')+f'：{low:g}–{high:g}',key)
            p[key]=number
        p['visible']=visible.get();draft.update(mode=mode.get(),window=wave.get(),topmost=top.get(),clickthrough=lock.get())
        state['draft']=normalize(draft);return state['draft']
    def validate_field(key):
        if state['loading'] or not window.winfo_exists():return
        try:collect();errors.clear(key)
        except ValueError as error:
            if key in getattr(error,'fields',()):errors.show(error,False)
    def fingerprint():
        try:return (name.get(),collect())
        except ValueError:return (name.get(),{k:v.get() for k,v in fields.items()},visible.get(),mode.get(),wave.get(),top.get(),lock.get())
    def is_dirty():return fingerprint()!=state['baseline']
    def clean():state['baseline']=deepcopy(fingerprint());app.layout_draft=None;changed()
    def changed(*_):
        if state['loading']:return
        dirty.set(tr('有未保存修改' if is_dirty() else '草稿与已载入布局一致'))
        if state['pending'] is None:state['pending']=window.after_idle(redraw)
    def redraw():
        state['pending']=None
        if window.winfo_exists():preview.paint()
    def confirm_replace():
        if not is_dirty():return True
        answer=control_confirm.draft_choice(window)
        if answer=='cancel':return False
        return guard(save) if answer=='save' else True
    def change_panel(_=None):
        if not guard(collect):kind.set(state['panel']);return
        state['panel']=kind.get();load_panel();preview.paint()
    def select_draft(_=None):
        target=selected.get()
        if not confirm_replace():selected.set(state.get('selected',''));return
        value=store.load()
        if target in value['profiles']:
            state['draft']=deepcopy(value['profiles'][target]);selected.set(target);state['selected']=target;name.set(target);load_draft();clean();status.set(tr('已载入编辑区，点击应用后才改变 HUD'))
    def notify():
        callback=getattr(app,'refresh_run_configuration',None)
        if callback:callback()
    def apply_selected():
        target=selected.get()
        if not confirm_replace():return
        state['draft']=layout_actions.select(app.data_path,hud(),target);refresh();state['selected']=target;load_draft();clean();notify();status.set(tr('布局已应用，原画面已备份'))
    def save():
        if not name.get().strip():raise PreferenceError('请输入布局名称','name')
        layout_actions.save(app.data_path,hud(),name.get(),collect());refresh();state['selected']=selected.get();load_draft();clean();notify();status.set(tr('布局已保存并应用，下次启动自动恢复'))
        errors.clear()
    def copy():
        new=simpledialog.askstring(tr('另存为'),tr('输入新布局名称'),initialvalue=name.get(),parent=window)
        if new:
            if new in store.load()['profiles']:raise ValueError('该名称已存在，请使用不同名称')
            name.set(new);save()
    def read_live():
        if hud() is None:raise ValueError('请先启动 HUD，或直接编辑布局数值')
        if not confirm_replace():return
        state['draft']=layout_actions.current(app.data_path,hud());load_draft();changed();status.set(tr('已读取当前画面，保存后生效'))
    def restore():
        identifier=state['history'].get(backup.get())
        if not identifier:raise ValueError('请先选择备份')
        if not confirm_replace():return
        state['draft']=layout_actions.restore(app.data_path,hud(),identifier);refresh();state['selected']=selected.get();load_draft();clean();notify();status.set(tr('备份已恢复，恢复前状态也已备份'))
    def backup_now():
        oldname=name.get();oldselected=selected.get();store.backup(layout_actions.current(app.data_path,hud()));refresh();name.set(oldname);selected.set(oldselected);status.set(tr('当前 HUD 已备份'))
    def delete():
        target=selected.get()
        if not target:raise ValueError('请先选择布局')
        if not confirm_replace():return
        from control_danger import confirm
        if not confirm(window,'删除所选布局','删除所选布局',[target],action='删除所选布局',warning='删除后仍可从自动备份恢复。继续？'):return
        def edit(value):
            value['profiles'].pop(target)
            if value['active']==target:value['active']=''
        store.change('delete',layout_actions.current(app.data_path,hud()),edit);refresh();state['selected']=selected.get();changed();notify();status.set(tr('布局已删除，可从备份恢复'))
    def keep_draft():
        if is_dirty():app.layout_draft=dict(draft=deepcopy(state['draft']),baseline=deepcopy(state['baseline']),panel=state['panel'],name=name.get(),selected=selected.get(),fields={k:v.get() for k,v in fields.items()},visible=visible.get(),mode=mode.get(),wave=wave.get(),top=top.get(),lock=lock.get())
    def close(after=None,exiting=False):
        if is_dirty():
            answer=control_confirm.draft_choice(window,closing=True,exiting=exiting)
            if answer=='cancel':return
            if answer=='save' and not guard(save):return
            if answer=='keep':keep_draft()
            elif answer=='discard':app.layout_draft=None
        window.destroy()
        if after:after()
    def dispose(event):
        if event.widget is window:
            if state['pending'] is not None:window.after_cancel(state['pending'])
            for variable,token in traces:variable.trace_remove('write',token)
            for variable in variables:variable.__del__();variable._tk=None
    panel.bind('<<ComboboxSelected>>',change_panel);chooser.bind('<<ComboboxSelected>>',lambda e:guard(select_draft));window.protocol('WM_DELETE_WINDOW',close)
    control_confirm.register(app,window,close)
    refresh();state['selected']=selected.get();load_draft();clean()
    # A draft is session-local and never modifies the saved active layout on reopen.
    if remembered:
        state.update(draft=deepcopy(remembered['draft']),panel=remembered['panel'],baseline=remembered['baseline'],selected=remembered['selected']);name.set(remembered['name']);selected.set(remembered['selected']);kind.set(state['panel']);load_draft()
        for key,value in remembered['fields'].items():fields[key].set(value)
        visible.set(remembered['visible']);mode.set(remembered['mode']);wave.set(remembered['wave']);top.set(remembered['top']);lock.set(remembered['lock']);changed()
    for variable in [name,visible,mode,wave,top,lock,*fields.values()]:traces.append((variable,variable.trace_add('write',changed)))
    window.bind('<Destroy>',dispose,add='+')
    for label in body.winfo_children():
        if isinstance(label,tk.Label):label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(100,e.width)))
    window.layout_state=state;window.layout_fields=fields;window.layout_name=name;window.layout_panel=kind;window.layout_save=lambda:guard(save);window.layout_restore=lambda:guard(restore);window.layout_status=status
    window.layout_preview=preview;window.layout_select=chooser;window.layout_close=close;window.layout_dirty=is_dirty;window.layout_read=lambda:guard(read_live);window.layout_errors=errors
    return window
