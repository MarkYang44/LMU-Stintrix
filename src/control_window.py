"""One anatomy for every secondary window: header, padded body, action footer.

Tool windows, editors and confirmations read like the main pages: a short
accent tick and title, one muted line on what the window is for, the content,
then a footer whose left side reports state and whose right side holds the
actions. The primary action sits where each platform expects it (first on
Windows, last on macOS). Windows size to their content at the real display
scale and stay on the owner's monitor, so nothing is clipped at 125–200 %.
"""
import sys
import tkinter as tk
import tkinter.font as tkfont
from control_theme import T
from control_widgets import px, release_with
from control_motion import fade_in
from i18n import tr, Label

MAC = sys.platform == 'darwin'
PAD = 22


def wrapping(label, minimum=80):
    """Wrap to the label's own width so long text never widens or clips a window."""
    label.wraps = minimum
    label.bind('<Configure>', lambda e: label.configure(wraplength=max(minimum, e.width - 2)), add='+')
    return label


def note(parent, text, size=9, color=None, bold=False):
    """A muted, self-wrapping paragraph on the parent's background (text or a StringVar)."""
    source = dict(textvariable=text) if isinstance(text, tk.Variable) else dict(text=text)
    label = Label(parent, **source, bg=parent.cget('bg'), fg=color or T.MUTED, font=(T.FONT, size, 'bold' if bold else 'normal'),
                  anchor='w', justify='left')
    return wrapping(label)


class Header(tk.Frame):
    """Accent tick, title and an optional purpose line; `side` holds right-aligned meta."""

    def __init__(self, parent, title, subtitle='', size=15, tone=None):
        bg = parent.cget('bg')
        super().__init__(parent, bg=bg)
        self.tick = tk.Canvas(self, width=px(self, 28), height=px(self, 2), bg=bg, highlightthickness=0, takefocus=False)
        self.tick.create_rectangle(0, 0, px(self, 28), px(self, 2), fill=tone or T.ACCENT, outline='')
        self.tick.pack(anchor='w', pady=(0, px(self, 10)))
        line = tk.Frame(self, bg=bg)
        line.pack(fill='x')
        self.side = tk.Frame(line, bg=bg)
        self.side.pack(side='right', anchor='e')
        self.title = Label(line, text=title, bg=bg, fg=T.FG, font=(T.FONT, size, 'bold'), anchor='w', justify='left')
        self.title.pack(side='left', fill='x', expand=True)
        self.subtitle = note(self, subtitle)
        if subtitle:
            self.subtitle.pack(fill='x', pady=(px(self, 5), 0))

    def set(self, title=None, subtitle=None):
        if title is not None:
            self.title.configure(text=title)
        if subtitle is not None:
            self.subtitle.configure(text=subtitle)
            if subtitle and not self.subtitle.winfo_ismapped():
                self.subtitle.pack(fill='x', pady=(px(self, 5), 0))
            elif not subtitle:
                self.subtitle.pack_forget()


class Footer(tk.Frame):
    """A hairline, then state on the left and the window's actions on the right.

    Actions keep their natural translated widths. When state and actions do
    not share one line comfortably, the state moves onto its own full-width
    line and the actions wrap, still right-aligned, instead of being clipped.
    """

    def __init__(self, parent, variable=None, feedback=False):
        super().__init__(parent, bg=T.BG)
        self.stacked = False
        self.rule = tk.Frame(self, bg=T.EDGE, height=1)
        self.rule.pack(fill='x')
        self.bar = tk.Frame(self, bg=T.BG)
        self.bar.pack(fill='x', padx=px(self, PAD), pady=(px(self, 10), px(self, 12)))
        self.actions = tk.Frame(self.bar, bg=T.BG, width=1, height=1)
        self.actions.pack_propagate(False)
        self.actions.pack(side='right', anchor='e')
        self.status = variable or tk.StringVar(self)
        if variable is None:
            release_with(self, self.status)
        self.feedback = None
        self.message = None
        if feedback:
            from control_feedback import StatusFeedback
            self.feedback = StatusFeedback(self.bar, self.status)
            self.feedback.pack(side='left', fill='x', expand=True, padx=(0, px(self, 16)))
        else:
            self.message = note(self.bar, self.status)
            self.message.pack(side='left', fill='x', expand=True, padx=(0, px(self, 16)))
        self.buttons = []
        self.font = tkfont.Font(self, family=T.FONT, size=9)
        self.trace = self.status.trace_add('write', lambda *_: self.after_idle(self.arrange))
        self.bar.bind('<Configure>', lambda _: self.arrange(), add='+')
        self.bind('<Destroy>', self.dispose, add='+')

    def dispose(self, event):
        if event.widget is self:
            try:
                self.status.trace_remove('write', self.trace)
            except (tk.TclError, ValueError, AttributeError):
                pass
            # Delete the font here, on the GUI thread, rather than whenever it is collected.
            self.font.__del__()
            self.font.delete_font = False

    def ordered(self):
        """Platform order: primary first on Windows, primary nearest the edge on macOS."""
        return [b for b in (reversed(self.buttons) if MAC else self.buttons) if b.winfo_exists()]

    def natural(self):
        gap = px(self, 8)
        buttons = self.ordered()
        return sum(b.winfo_reqwidth() for b in buttons) + gap * max(0, len(buttons) - 1)

    def arrange(self, width=None):
        """Inline when state and actions share one line; otherwise state above, actions wrapped right."""
        if not self.winfo_exists():
            return
        width = width or self.bar.winfo_width()
        if width <= 1:
            return
        gap = px(self, 8)
        buttons = self.ordered()
        natural = self.natural()
        room = width - natural - px(self, 16)
        text = self.status.get()
        stacked = bool(buttons) and (natural > width or (bool(text) and (room < px(self, 150) or self.font.measure(text) > room * 1.9)))
        rows, line = [], 0
        for button in buttons:
            size = button.winfo_reqwidth()
            if not rows or (line and line + gap + size > width):
                rows.append([])
                line = 0
            rows[-1].append(button)
            line += (gap if line else 0) + size
        span = min(natural, width) if buttons else 1
        height = sum(max(b.winfo_reqheight() for b in row) for row in rows) + gap * max(0, len(rows) - 1) if rows else 1
        self.actions.configure(width=max(1, span), height=max(1, height))
        y = 0
        for row in rows:
            used = sum(b.winfo_reqwidth() for b in row) + gap * (len(row) - 1)
            x = span - used
            tallest = max(b.winfo_reqheight() for b in row)
            for button in row:
                button.place(x=x, y=y + (tallest - button.winfo_reqheight()) // 2)
                x += button.winfo_reqwidth() + gap
            y += tallest + gap
        if stacked == self.stacked:
            return
        self.stacked = stacked
        state = self.feedback or self.message
        state.pack_forget()
        if stacked:
            state.pack(side='top', fill='x', pady=(0, px(self, 8)), before=self.actions)
        else:
            state.pack(side='left', fill='x', expand=True, padx=(0, px(self, 16)))

    def add(self, text, command, primary=False, width=104, danger=False):
        """Add an action; callers list the primary first and the platform decides its side."""
        if danger:
            from control_danger import Danger as Action
        else:
            from control_video_widgets import Action
        button = Action(self.actions, text, command, width, primary)
        self.buttons.append(button)
        self.after_idle(self.arrange)
        return button


def repaint(widget):
    """Repaint canvas controls (buttons, fields) after a language change."""
    if hasattr(widget, 'paint') and widget.__class__.__name__ in ('Action', 'Pill', 'Danger', 'Field', 'SearchField', 'Select', 'Switch', 'Segmented'):
        widget.paint()
    for child in widget.winfo_children():
        repaint(child)


def settle(win, width=None):
    """Apply text wrapping and the footer layout for `width` before measuring.

    Tk lays out a new window's children only after the window manager has
    sized it, so before the first <Configure> paragraphs would still count as
    one line and wrapped actions as none. Until then the body's content width
    stands in for each paragraph's own width.
    """
    win.update_idletasks()
    content = width - 2 * px(win, PAD) if width else 0

    def visit(widget):
        minimum = getattr(widget, 'wraps', None)
        if minimum is not None:
            own = widget.winfo_width()
            span = own if own > 1 else content
            if span > 1:
                widget.configure(wraplength=max(minimum, span - 2))
        if hasattr(widget, 'settle'):
            widget.settle()
        for child in widget.winfo_children():
            visit(child)
    visit(win)
    footer = getattr(win, 'footer', None)
    if isinstance(footer, Footer):
        footer.arrange(None if footer.bar.winfo_width() > 1 else content)
    win.update_idletasks()


def window(owner, title, subtitle='', *, heading=None, topmost=False, transient=True, feedback=False, header=True, escape=True, tone=None):
    """A themed Toplevel with `header`, `body`, `footer`, `status` and `add_action`.

    `title` is the window-manager title; `heading` (default: the part after a
    "Stintrix · " prefix) is the in-window heading. Escape and the close box
    both call `window.on_close` when set, else close the window, so editors
    with drafts keep one close path.
    """
    root = owner.winfo_toplevel()
    win = tk.Toplevel(root)
    fade_in(win)
    win.title(tr(title))
    win.configure(bg=T.BG)
    if transient:
        win.transient(root)
    if topmost:
        win.attributes('-topmost', True)
    win.footer = Footer(win, feedback=feedback)
    win.footer.pack(side='bottom', fill='x')
    win.body = tk.Frame(win, bg=T.BG)
    win.body.pack(fill='both', expand=True, padx=px(win, PAD), pady=(px(win, 20), px(win, 14)))
    heading = heading if heading is not None else title.split(' · ', 1)[-1] if title.startswith('Stintrix · ') else title
    win.header = Header(win.body, heading, subtitle, tone=tone) if header else None
    if win.header is not None:
        win.header.pack(fill='x', pady=(0, px(win, 16)))
    win.status = win.footer.status
    win.add_action = win.footer.add
    win.on_close = None

    def close(_=None):
        (win.on_close or win.destroy)()
        return 'break'
    win.request_close = close
    win.protocol('WM_DELETE_WINDOW', close)
    if escape:
        win.bind('<Escape>', close)

    def retranslate():
        win.title(tr(title))
        repaint(win)
    win.retranslate = retranslate
    return win


def card(parent, padding=16):
    """A flat card surface inside a window body; returns (outer, inner)."""
    outer = tk.Frame(parent, bg=T.CARD)
    inner = tk.Frame(outer, bg=T.CARD)
    inner.pack(fill='both', expand=True, padx=px(parent, padding), pady=px(parent, padding - 4))
    return outer, inner


class Facts(tk.Frame):
    """Label / value rows that update in place; tones colour a value by meaning."""

    TONES = {'good': 'GREEN', 'bad': 'RED', 'warn': 'ACCENT', None: 'FG', 'muted': 'MUTED'}

    def __init__(self, parent, rows, mono=False):
        bg = parent.cget('bg')
        super().__init__(parent, bg=bg)
        self.values = {}
        for index, (key, label) in enumerate(rows):
            caption = Label(self, text=label, bg=bg, fg=T.MUTED, font=(T.FONT, 9), anchor='w', justify='left')
            value = tk.Label(self, text='—', bg=bg, fg=T.FG, font=(T.MONO if mono else T.FONT, 10), anchor='w', justify='left')
            caption.grid(row=index, column=0, sticky='nw', padx=(0, px(self, 18)), pady=px(self, 5))
            value.grid(row=index, column=1, sticky='nw', pady=px(self, 5))
            value.source = ''
            self.values[key] = value
        self.columnconfigure(1, weight=1)
        self.bind('<Configure>', lambda _: self.settle(), add='+')

    def settle(self):
        width = self.winfo_width()
        if width > 1:
            for value in self.values.values():
                value.configure(wraplength=max(120, width - value.winfo_x() - 4))

    def set(self, key, text, tone=None, translate=True):
        value = self.values[key]
        value.source = (text, translate)
        value.configure(text=tr(text) if translate else text, fg=getattr(T, self.TONES.get(tone, 'FG')))

    def retranslate(self):
        for value in self.values.values():
            if value.source:
                text, translate = value.source
                value.configure(text=tr(text) if translate else text)


def modal(win, owner, focus=None):
    """Hold input in `win` until it closes, then hand any previous grab back."""
    previous = owner.grab_current()
    try:
        win.grab_set()
        if focus is not None:
            focus.focus_set()
        owner.wait_window(win)
    finally:
        if previous is not None and previous.winfo_exists():
            previous.grab_set()
        if owner.winfo_exists():
            owner.focus_set()


def natural_width(win, minimum, maximum):
    """Design width that fits the footer's actions on one line, within limits."""
    from control_widgets import scale
    win.update_idletasks()
    need = win.footer.natural() / scale(win) + 2 * PAD + 4
    return max(minimum, min(maximum, round(need)))


def grow(win):
    """Let a window grow to content that arrived later (never shrink or move it)."""
    if not win.winfo_exists():
        return
    settle(win)
    need = win.winfo_reqheight()
    if need > win.winfo_height() + 1:
        from control_layout_preview import monitors
        x, y = win.winfo_rootx(), win.winfo_rooty()
        screen = next((r for r in monitors(win) if r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]), None)
        if screen is not None:
            need = min(need, screen[1] + screen[3] - y - px(win, 48))
        win.geometry(f'{win.winfo_width()}x{max(win.winfo_height(), need)}')


def fit(win, width, height=None, minimum=None, owner=None, center=True):
    """Size to content at the real display scale; keep the window on its owner's monitor.

    `width`/`height`/`minimum` are design pixels at 96 dpi. Without a height
    the window takes the content's natural height after text has wrapped to
    the final width.
    """
    from control_layout_preview import monitors
    from control_tooltip import position
    top = (owner or win.master).winfo_toplevel()
    win.update_idletasks()
    w = px(win, width)
    win.geometry(f'{w}x{max(1, win.winfo_reqheight())}')
    settle(win, w)
    h = px(win, height) if height is not None else win.winfo_reqheight()
    if height is None:
        # Once really laid out, correct any paragraph that wraps narrower than estimated.
        def first(event):
            if event.widget is win:
                win.unbind('<Configure>', token)
                win.after_idle(lambda: grow(win))
        token = win.bind('<Configure>', first, add='+')
    if minimum:
        h = max(h, px(win, minimum[1]))
        win.minsize(min(w, px(win, minimum[0])), px(win, minimum[1]))
    screens = monitors(win)
    cx = top.winfo_rootx() + top.winfo_width() / 2
    cy = top.winfo_rooty() + top.winfo_height() / 2
    sx, sy, sw, sh = next((r for r in screens if r[0] <= cx < r[0] + r[2] and r[1] <= cy < r[1] + r[3]), screens[0])
    w = min(w, sw - px(win, 24))
    h = min(h, sh - px(win, 72))
    win.geometry(f'{round(w)}x{round(h)}')
    if center:
        x = max(sx, min(cx - w / 2, sx + sw - w))
        y = max(sy, min(cy - h / 2, sy + sh - h - px(win, 48)))
        position(win, x, y)
    return win
