"""Debounced, user-changed video options; geometry remains separately verified."""
import tkinter as tk


def install(w):
    w.options_job=None;w.options_dirty=False;w.options_traces=[]
    def flush():
        w.options_job=None
        if not w.options_dirty:return
        from video_preferences import save_options
        try:save_options(w.root,w.hz.get(),w.smooth_120hz.get(),w.fields['ffmpeg'].get());w.options_dirty=False
        except (OSError,ValueError,tk.TclError) as error:
            if w.alive():w.status.set(str(error))
    def changed(*_):
        w.options_dirty=True
        if w.options_job:w.window.after_cancel(w.options_job)
        w.options_job=w.window.after(400,flush)
    def dispose():
        if w.options_job:
            try:w.window.after_cancel(w.options_job)
            except tk.TclError:pass
            w.options_job=None
        flush()
        for variable,trace in w.options_traces:
            try:variable.trace_remove('write',trace)
            except tk.TclError:pass
        w.options_traces=[]
    w.flush_options=dispose
    for variable in (w.hz,w.smooth_120hz,w.fields['ffmpeg']):w.options_traces.append((variable,variable.trace_add('write',changed)))
