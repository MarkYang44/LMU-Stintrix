"""Local participation confirmation, single or batch, without rewriting evidence."""
import tkinter as tk
from pathlib import Path
from i18n import tr
from control_theme import T
from control_widgets import Switch
from control_video_widgets import ChoiceStrip
from control_flow import install
from race_mode import LABELS,mode
from race_mode_overrides import load,relative,save
from track_names import display


def show(app,entry,on_saved):
    old=getattr(app,'participation_editor',None)
    if old is not None and old.winfo_exists():old.deiconify();old.lift();return old
    entries=list({Path(e['folder']).resolve():dict(e) for e in (entry if isinstance(entry,(list,tuple)) else [entry])}.values())
    folders=list(dict.fromkeys(Path(e['folder']).resolve() for e in entries));keys=[relative(app.data_path,f) for f in folders];batch=len(folders)>1
    window=tk.Toplevel(app.root);app.participation_editor=window;window.title(tr('更正参赛方式'));window.configure(bg=T.BG);window.geometry('630x420');window.minsize(500,340);window.transient(app.root)
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=16,pady=14)
    def label(text,size=10,color=T.MUTED):
        widget=app.label(body,text,size,color,size==15);widget.pack(fill='x',padx=14,pady=4);widget.bind('<Configure>',lambda e:widget.configure(wraplength=max(100,e.width)));return widget
    first=entries[0];title=label('',15,T.FG);current=label('');preview=label('')
    choice=tk.StringVar(window,value='auto');unknown=tk.BooleanVar(window,value=batch);message=tk.StringVar(window);state=dict(notice='')
    strip=ChoiceStrip(body,choice,[('线上','online'),('线下','single'),('自动识别','auto')],lambda:None);strip.pack(fill='x',padx=14,pady=10)
    if batch:Switch(body,'仅更正未知记录',unknown,lambda:None,compact=True).pack(fill='x',padx=14,pady=4)
    label('批量恢复自动识别时，请关闭“仅更正未知记录”。' if batch else '选择自动识别可撤销这场赛事的人工更正。',9)
    if batch:label('默认跳过已识别或人工确认的记录；保存时再次核对。',9)
    footer=tk.Frame(window,bg=T.BG);footer.pack(side='bottom',before=body,fill='x',padx=16,pady=(0,12));status=app.label(footer,message,9,T.MUTED);status.pack(fill='x');status.bind('<Configure>',lambda e:status.configure(wraplength=max(100,e.width)))
    row=app.row(footer);install(row)
    def say(text):state['notice']=text;message.set(tr(text))
    def translate():
        window.title(tr('更正参赛方式'));title.configure(text=tr('已选择 {count} 场赛事').format(count=len(folders)) if batch else display(first.get('track','')))
        current.configure(text=tr('其中 {count} 场参赛方式未知').format(count=sum(mode(e)=='unknown' for e in entries)) if batch else tr('当前参赛方式')+' · '+tr(LABELS[mode(first)]))
        names=list(dict.fromkeys(display(e.get('track','')) for e in entries));meta=first.get('session');meta=meta if isinstance(meta,dict) else {}
        preview.configure(text=' / '.join(names[:3])+(' …' if len(names)>3 else '') if batch else first.get('vehicle',meta.get('vehicle','')))
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
    button=app.button(row,'保存更正',commit,True,140);app.button(row,'重新读取更正',reload,False,140);app.button(row,'取消更正',window.destroy,False,110)
    state['measure']=None
    def measure():
        state['measure']=None
        wanted=max(340,body.winfo_reqheight()+footer.winfo_reqheight()+40)
        if window.minsize()!=(500,wanted):window.minsize(500,wanted)
    def resized(event):
        # Child labels can wrap without resizing the top-level window. Recheck
        # their requested geometry too, so instructions never lose their space.
        if state['measure'] is not None:window.after_cancel(state['measure'])
        state['measure']=window.after_idle(measure)
    def dispose(event):
        if event.widget is window and state['measure'] is not None:window.after_cancel(state['measure']);state['measure']=None
    window.bind('<Configure>',resized,add='+');window.bind('<Destroy>',dispose,add='+')
    window.mode_controls=dict(choice=choice,only_unknown=unknown,save=commit,reload=reload,message=message,strip=strip,footer=row,folders=tuple(folders))
    reload();translate();window.update_idletasks();measure();window.grab_set();return window
