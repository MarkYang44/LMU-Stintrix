"""Desktop policy and OS services; analysis and file formats remain shared."""
import os
from pathlib import Path
import subprocess
import sys


def offline_only():
    return sys.platform == 'darwin' or os.environ.get('STINTRIX_OFFLINE') == '1'


def open_path(path):
    """Open an existing local file with the OS, without a shell or URL parsing."""
    if sys.platform == 'win32':
        return os.startfile(path)
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(str(path))
    command = ['/usr/bin/open', str(path)] if sys.platform == 'darwin' else ['xdg-open', str(path)]
    return subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def page_ids():
    # Stable business IDs preserve saved filters, page state and action routing;
    # the tuple is the rail order: live, analysis, library, tools, settings last.
    return (1, 6, 4, 5, 3, 2) if offline_only() else (0, 1, 6, 4, 5, 3, 2)


def wheel_steps(event):
    """Wheel units: Windows and Tk 9 report 120 per notch; Tk 8.6 Aqua reports lines."""
    import tkinter
    delta=getattr(event,'delta',event)
    return delta if sys.platform=='darwin' and tkinter.TkVersion<9 else delta/120


def install_touchpad(root):
    """Tk 9 reports Mac trackpads as TouchpadScroll; replay them through the wheel bindings."""
    import tkinter
    if sys.platform!='darwin' or tkinter.TkVersion<9:return
    def replay(event):
        widget=event.widget
        # Native Tk widgets (Text, Entry, ttk scrollables) already scroll themselves.
        if not isinstance(widget,tkinter.Misc) or root.bind_class(widget.winfo_class(),'<TouchpadScroll>'):return
        dx,dy=(int(value) for value in root.tk.splitlist(root.tk.call('::tk::PreciseScrollDeltas',event.delta)))
        # Pixel deltas become 20 px wheel lines (Tk 9 uses 120 per line), matching the main view.
        for sequence,pixels in (('<MouseWheel>',dy),('<Shift-MouseWheel>',dx)):
            if pixels:widget.event_generate(sequence,delta=pixels*6,x=event.x,y=event.y,when='now')
    root.bind_all('<TouchpadScroll>',replay,add='+')


def title(profile):
    return profile.title + (' · 离线分析' if offline_only() else ' · 控制中心')


def shortcut_hint(keys):
    return keys.replace('Ctrl','Cmd') if sys.platform=='darwin' else keys


def install_mac_keys(root,on_quit=None,preferences=None,pages=None):
    if sys.platform != 'darwin':
        return
    if on_quit is not None:
        # Native Cmd+Q must use the same pending-task and unsaved-edit guards
        # as the window close button, rather than Tcl's default immediate exit.
        root.createcommand('tk::mac::Quit',on_quit)
    if preferences is not None:root.bind('<Command-comma>',lambda event:(preferences(),'break')[1])
    # Existing canvas/table shortcuts use Control. Native text widgets already
    # implement Command editing; do not paste/copy twice in those widgets.
    for key in ('f', 'k', 's', 'a', 'c', 'v', 'x'):
        def dispatch(event, key=key):
            target = root.focus_get() or root
            if key in ('a', 'c', 'v', 'x') and target.winfo_class() in ('Entry', 'TEntry', 'Text', 'Spinbox'):
                return
            target.event_generate('<Control-' + key + '>')
            return 'break'
        root.bind('<Command-' + key + '>', dispatch)
    # In Tk event patterns '<Control-1>' means Control + mouse button 1, so a
    # forwarded Command+number never reached the page keys. Bind them directly.
    for key,action in (pages or {}).items():root.bind('<Command-Key-'+key+'>',action)
    root.bind('<Command-Shift-c>',lambda event:((root.focus_get() or root).event_generate('<Control-Shift-c>'),'break')[1])

