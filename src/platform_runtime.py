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
    # Stable business IDs preserve saved filters, page state and action routing.
    return (1, 3, 6, 4, 5, 2) if offline_only() else tuple(range(7))


def wheel_steps(event):
    return event.delta if sys.platform=='darwin' else event.delta/120


def title(profile):
    return profile.title + (' · 离线分析' if offline_only() else ' · 控制中心')


def install_mac_keys(root,on_quit=None,preferences=None):
    if sys.platform != 'darwin':
        return
    if on_quit is not None:
        # Native Cmd+Q must use the same pending-task and unsaved-edit guards
        # as the window close button, rather than Tcl's default immediate exit.
        root.createcommand('tk::mac::Quit',on_quit)
    if preferences is not None:root.bind('<Command-comma>',lambda event:(preferences(),'break')[1])
    # Existing canvas/table shortcuts use Control. Native text widgets already
    # implement Command editing; do not paste/copy twice in those widgets.
    for key in ('f', 'k', 's', 'a', 'c', 'v', 'x', '1', '2', '3', '4', '5', '6', '7'):
        def dispatch(event, key=key):
            target = root.focus_get() or root
            if key in ('a', 'c', 'v', 'x') and target.winfo_class() in ('Entry', 'TEntry', 'Text', 'Spinbox'):
                return
            target.event_generate('<Control-' + key + '>')
            return 'break'
        root.bind('<Command-' + key + '>', dispatch)
    root.bind('<Command-Shift-c>',lambda event:((root.focus_get() or root).event_generate('<Control-Shift-c>'),'break')[1])

