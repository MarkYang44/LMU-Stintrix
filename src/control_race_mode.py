"""Local participation confirmation, single or batch, without rewriting evidence."""
import tkinter as tk
from pathlib import Path
from i18n import tr
from control_theme import T
from control_widgets import Switch
from control_video_widgets import ChoiceStrip
from race_mode import LABELS,mode
from race_mode_overrides import load,relative,save
from track_names import display


def show(app,entry,on_saved):
    old=getattr(app,'participation_editor',None)
    if old is not None and old.winfo_exists():old.deiconify();old.lift();return old
    entries=list({Path(e['folder']).resolve():dict(e) for e in (entry if isinstance(entry,(list,tuple)) else [entry])}.values())
    folders=list(dict.fromkeys(Path(e['folder']).resolve() for e in entries));keys=[relative(app.data_path,f) for f in folders];batch=len(folders)>1
    from control_window import window as sheet,note
    from control_widgets import px
    window=sheet(app.root,'更正参赛方式','—');app.participation_editor=window;body=window.body
    first=entries[0];current=note(body,'',10,T.FG);current.pack(fill='x')
    choice=tk.StringVar(window,value='auto');unknown=tk.BooleanVar(window,value=batch);message=window.status;state=dict(notice='')
    app.label(body,'更正为',9,T.MUTED).pack(anchor='w',pady=(px(window,14),px(window,4)))
    strip=ChoiceStrip(body,choice,[('线上','online'),('线下','single'),('自动识别','auto')],lambda:None);strip.pack(fill='x')
    if batch:Switch(body,'仅更正未知记录',unknown,lambda:None,compact=True).pack(fill='x',pady=(px(window,8),0))
    note(body,'批量恢复自动识别时，请关闭“仅更正未知记录”。' if batch else '选择自动识别可撤销这场赛事的人工更正。').pack(fill='x',pady=(px(window,10),0))
    if batch:note(body,'默认跳过已识别或人工确认的记录；保存时再次核对。').pack(fill='x',pady=(px(window,4),0))
    def say(text):state['notice']=text;message.set(tr(text))
    shell_translate=window.retranslate
    def translate():
        shell_translate()
        names=list(dict.fromkeys(display(e.get('track','')) for e in entries));meta=first.get('session');meta=meta if isinstance(meta,dict) else {}
        window.header.set(title=tr('已选择 {count} 场赛事').format(count=len(folders)) if batch else display(first.get('track','')),
            subtitle=' / '.join(names[:3])+(' …' if len(names)>3 else '') if batch else first.get('vehicle',meta.get('vehicle','')))
        current.configure(text=tr('其中 {count} 场参赛方式未知').format(count=sum(mode(e)=='unknown' for e in entries)) if batch else tr('当前参赛方式')+' · '+tr(LABELS[mode(first)]))
        message.set(tr(state['notice']));strip.refresh(False)
        for b in strip.buttons.values():b.paint()
    window.retranslate=translate
    def reload():
        try:
            saved=load(app.data_path)['entries'];values={next((v['race_mode'] for k,v in saved.items() if k.replace('\\','/').casefold()==key.casefold()),'auto') for key in keys}
            choice.set('online' if batch else values.pop());say('人工确认优先于自动识别；原始赛事文件保留。');button.configure(state='normal');return True
        except (OSError,ValueError) as error:say(str(error) or type(error).__name__);button.configure(state='disabled');return False
    def commit():
        try:count=save(app.data_path,folders,None if choice.get()=='auto' else choice.get(),only_unknown=unknown.get())
        except (OSError,ValueError) as error:say(str(error) or type(error).__name__);return False
        window.destroy()
        if not app.closing:
            from control_participation import refresh_views
            app.status.set(tr('已更正 {count} 场赛事').format(count=count) if count else tr('没有需要更正的记录；已保留现有分类。'));refresh_views(app,on_saved)
        return True
    button=window.add_action('保存更正',commit,True,120);window.add_action('重新读取更正',reload,False,110);window.add_action('取消',window.destroy,False,90)
    state['measure']=None
    def measure():
        state['measure']=None
        wanted=max(px(window,300),window.winfo_reqheight());narrow=px(window,400)
        if window.minsize()!=(narrow,wanted):window.minsize(narrow,wanted)
    def resized(event):
        # Child labels can wrap without resizing the top-level window. Recheck
        # their requested geometry too, so instructions never lose their space.
        if state['measure'] is not None:window.after_cancel(state['measure'])
        state['measure']=window.after_idle(measure)
    def dispose(event):
        if event.widget is window and state['measure'] is not None:window.after_cancel(state['measure']);state['measure']=None
    window.bind('<Configure>',resized,add='+');window.bind('<Destroy>',dispose,add='+')
    window.mode_controls=dict(choice=choice,only_unknown=unknown,save=commit,reload=reload,message=message,strip=strip,footer=window.footer.actions,folders=tuple(folders))
    from control_window import fit
    reload();translate();fit(window,520);measure();window.grab_set();return window
