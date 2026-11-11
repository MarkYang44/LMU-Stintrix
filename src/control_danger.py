"""One consistent destructive confirmation, with explicit action and frozen targets."""
import tkinter as tk
from tkinter import ttk
from control_theme import T
from control_video_widgets import Action
from control_motion import blend
from i18n import tr


class Danger(Action):
    def paint(self):
        super().paint()
        # Without a target the action stays as quiet as any unavailable button;
        # the red treatment appears only once deleting is actually possible.
        if not self.enabled:return
        self.itemconfigure(self.surface,fill=blend(T.CARD,T.RED,.06+self.amount*.06),outline=T.FG if self.focused else T.RED);self.itemconfigure(self.caption,fill=T.RED);self.itemconfigure(self.accent,fill=T.RED)


def confirm(parent,title,summary,details,action='永久删除',warning=''):
    from control_window import window as sheet,fit,modal,note
    from control_widgets import px
    owner=parent.winfo_toplevel();window=sheet(owner,title,summary,escape=False,tone=T.RED);window.header.subtitle.configure(fg=T.FG,font=(T.FONT,10))
    holder=tk.Frame(window.body,bg=T.FIELD);holder.pack(fill='both',expand=True)
    lines=max(1,min(9,sum(str(d).count(chr(10))+1 for d in details)))
    text=tk.Text(holder,bg=T.FIELD,fg=T.FG,font=(T.FONT,10),wrap='word',relief='flat',padx=12,pady=10,height=lines,width=1)
    bar=ttk.Scrollbar(holder,command=text.yview,orient='vertical',style='Lab.Vertical.TScrollbar');text.configure(yscrollcommand=bar.set)
    if lines>=9:bar.pack(side='right',fill='y')
    text.pack(fill='both',expand=True);text.insert('1.0',chr(10).join(map(str,details)));text.configure(state='disabled')
    if warning:note(window.body,warning).pack(fill='x',pady=(px(window,10),0))
    answer=[False]
    def close(ok=False):answer[0]=ok;window.destroy()
    remove=window.add_action(action,lambda:close(True),False,max(150,len(tr(action))*9),True);cancel=window.add_action('取消',close,False,110)
    window.danger_buttons=dict(cancel=cancel,delete=remove);owner._stintrix_danger=window
    window.on_close=close;window.bind('<Escape>',lambda _:(close(),'break')[1])
    fit(window,640,owner=owner)
    try:modal(window,owner,cancel)
    finally:owner._stintrix_danger=None
    return answer[0]
