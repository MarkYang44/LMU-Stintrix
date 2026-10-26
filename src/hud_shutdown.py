"""Hide HUD presentation immediately; retain its Tk owner until writes drain."""
def ancestor(parent,widget):
    while widget is not None:
        if widget is parent:return True
        widget=getattr(widget,'master',None)
    return False


def begin(app,keep_center=False):
    app.presentation_hidden=True
    # Cancel only callbacks registered on this HUD owner, leaving the retained
    # control center's timers alive. The shutdown poll is scheduled afterwards.
    registered=getattr(app.root,'_tclCommands',None);commands=set(registered) if isinstance(registered,(list,tuple,set)) else set()
    if commands:
        for job in app.root.tk.splitlist(app.root.tk.call('after','info')):
            info=app.root.tk.call('after','info',job);script=str(info[0]).split()
            if script and script[0] in commands:app.root.after_cancel(job)
    from hud_presentation import windows
    for window in windows(app).values():
        if window.winfo_exists():window.withdraw()
    if not keep_center:return
    center=getattr(app,'control_center',None) or getattr(getattr(app,'on_menu',None),'__self__',None)
    if center is None or center.closing or not center.root.winfo_exists():return
    app.stop_center=center
    if getattr(app,'owns_shortcuts',False):
        app.owns_shortcuts=False;center.owns_shortcuts=True
        center.shortcuts=app.shortcuts;center.shortcuts.hud=lambda:center.hud if center.active() else None;center.shortcuts.show=center.show
    center.attached=False;center.root.protocol('WM_DELETE_WINDOW',center.request_close)
    if ancestor(app.root,center.root):center.hud_host_root=app.root


def finish(app):
    app.stopped=True
    center=getattr(app,'stop_center',None)
    if center is not None and center.root.winfo_exists() and ancestor(app.root,center.root):app.root.withdraw()
    else:app.root.destroy()
