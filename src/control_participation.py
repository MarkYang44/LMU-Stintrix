"""Discoverable, selection-bound participation corrections across local views."""
import tkinter as tk
from pathlib import Path
from control_theme import T
from control_flow import install
from race_mode import mode
from race_mode_overrides import relative,save


def eligible(app,entry):
    if not entry:return False
    meta=entry.get('session');meta=meta if isinstance(meta,dict) else {}
    if entry.get('status',meta.get('status'))=='recording':return False
    try:relative(app.data_path,entry['folder']);return (Path(entry['folder'])/'session.json').is_file()
    except (OSError,ValueError,KeyError,TypeError):return False


def refresh_views(app,on_saved):
    loaders=list(getattr(app,'record_loaders',{}).values());running={id(loader) for loader in loaders if loader.running}
    windows=list(getattr(app,'library_windows',{}).values());loading={id(w.library) for w in windows if w.winfo_exists() and getattr(w,'library',None) and w.library.loading}
    on_saved()
    if app.closing:return
    for loader in loaders:
        if loader.page and loader.page.alive() and (not loader.running or id(loader) in running):loader.read(True)
    for window in windows:
        if window.winfo_exists():
            view=getattr(window,'library',None)
            if view and view.alive() and (not view.loading or id(view) in loading):view.refresh()


def edit(app,entries,on_saved):
    from control_race_mode import show
    return show(app,entries,on_saved)


def quick(app,entry,kind,on_saved,say):
    try:count=save(app.data_path,[entry['folder']],kind,only_unknown=True)
    except (OSError,ValueError) as error:say(str(error) or type(error).__name__);return False
    say('参赛方式已更新' if count else '没有需要更正的记录；已保留现有分类。');refresh_views(app,on_saved);return True


class UnknownNotice(tk.Frame):
    def __init__(self,page):
        self.page=page;super().__init__(page.table.master,bg=T.CARD)
        page.app.label(self,'参赛方式未知，可直接确认：',10,T.ACCENT).pack(anchor='w')
        row=page.app.row(self);install(row);self.actions=[]
        for kind,title in [('online','标为线上'),('single','标为线下')]:
            self.actions.append(page.app.button(row,title,lambda k=kind:self.confirm(k),False,140))
    def confirm(self,kind):
        p=self.page
        if p.alive() and not p.loader.running and eligible(p.app,p.selected) and mode(p.selected)=='unknown':return quick(p.app,dict(p.selected),kind,lambda:p.loader.read(True),p.say)
    def sync(self):
        p=self.page;show=eligible(p.app,p.selected) and mode(p.selected)=='unknown'
        visible=bool(self.winfo_manager())
        if show and not visible:self.pack(fill='x',before=p.table,pady=(5,0))
        elif not show and visible:self.pack_forget()
        for button in self.actions:button.configure(state='disabled' if p.loader.running else 'normal')
        if show!=visible and hasattr(p,'view_layout'):p.view_layout.schedule()
    def retranslate(self):
        for button in self.actions:button.paint()
