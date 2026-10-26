"""One consistent destructive confirmation, with explicit action and frozen targets."""
import tkinter as tk
from tkinter import ttk
from control_theme import T
from control_video_widgets import Action
from control_motion import blend
from i18n import tr


class Danger(Action):
    def paint(self):
        super().paint();self.itemconfigure(self.surface,fill=blend(T.CARD,T.RED,.06+self.amount*.06),outline=T.FG if self.focused else T.RED);self.itemconfigure(self.caption,fill=T.RED);self.itemconfigure(self.accent,fill=T.RED)


def confirm(parent,title,summary,details,action='永久删除',warning=''):
    owner=parent.winfo_toplevel();window=tk.Toplevel(owner);window.title(tr(title));window.configure(bg=T.BG);window.geometry('820x480');window.minsize(620,360);window.transient(owner)
    footer=tk.Frame(window,bg=T.BG);footer.pack(side='bottom',fill='x',padx=24,pady=(0,18))
    body=tk.Frame(window,bg=T.BG);body.pack(fill='both',expand=True,padx=24,pady=18)
    tk.Label(body,text=tr(summary),bg=T.BG,fg=T.FG,font=(T.FONT,14,'bold'),anchor='w').pack(fill='x',pady=(0,12))
    holder=tk.Frame(body,bg=T.FIELD);holder.pack(fill='both',expand=True)
    text=tk.Text(holder,bg=T.FIELD,fg=T.FG,font=(T.FONT,10),wrap='word',relief='flat',padx=12,pady=12)
    bar=ttk.Scrollbar(holder,command=text.yview,orient='vertical',style='Lab.Vertical.TScrollbar');bar.pack(side='right',fill='y');text.configure(yscrollcommand=bar.set);text.pack(fill='both',expand=True);text.insert('1.0','\n\n'.join(details));text.configure(state='disabled')
    label=tk.Label(footer,text=tr(warning),bg=T.BG,fg=T.MUTED,font=(T.FONT,10),justify='left',anchor='w');label.pack(fill='x',pady=10);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    row=tk.Frame(footer,bg=T.BG);row.pack(fill='x');answer=[False]
    def close(ok=False):answer[0]=ok;window.destroy()
    cancel=Action(row,'取消',close,130);cancel.pack(side='left',padx=(0,12));remove=Danger(row,action,lambda:close(True),180);remove.pack(side='left')
    window.danger_buttons=dict(cancel=cancel,delete=remove);owner._stintrix_danger=window
    previous=owner.grab_current();window.protocol('WM_DELETE_WINDOW',close);window.bind('<Escape>',lambda _:close())
    try:
        window.update_idletasks()
        from control_layout_preview import monitors
        from control_tooltip import position
        cx=owner.winfo_rootx()+owner.winfo_width()/2;cy=owner.winfo_rooty()+owner.winfo_height()/2
        sx,sy,sw,sh=next((r for r in monitors(owner) if r[0]<=cx<r[0]+r[2] and r[1]<=cy<r[1]+r[3]),monitors(owner)[0])
        position(window,max(sx,min(cx-window.winfo_width()/2,sx+sw-window.winfo_width())),max(sy,min(cy-window.winfo_height()/2,sy+sh-window.winfo_height())))
        window.grab_set();cancel.focus_set();owner.wait_window(window)
    finally:
        owner._stintrix_danger=None
        if previous is not None and previous.winfo_exists():previous.grab_set()
    return answer[0]
