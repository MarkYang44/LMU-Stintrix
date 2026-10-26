"""Inline error decoration and focus without changing validation rules."""
import tkinter as tk
from control_theme import T
from i18n import tr


def reveal(widget):
    current=widget
    while current.master is not None:
        if current.__class__.__name__=='ScrollPage':
            current.update_idletasks();canvas=current.canvas;body=current.body
            y=widget.winfo_rooty()-body.winfo_rooty();top=canvas.canvasy(0)
            if y<top or y+widget.winfo_height()>top+canvas.winfo_height():canvas.yview_moveto(max(0,y-36)/max(1,body.winfo_height()))
            break
        current=current.master


class Feedback:
    def __init__(self):self.fields={}
    def add(self,key,widget,label,hint):
        self.fields[key]=(widget,label,hint);hint.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(100,e.width)))
    def clear(self,key=None):
        for name,(widget,_,hint) in self.fields.items():
            if key is not None and key!=name:continue
            if widget.winfo_exists():
                if hasattr(widget,'set_error'):widget.set_error('')
                hint.configure(text='');hint.pack_forget()
    def show(self,error,focus=True):
        self.clear();keys=getattr(error,'fields',())
        if not keys:return False
        first=None
        for key in keys:
            if key not in self.fields:continue
            widget,label,hint=self.fields[key];message=str(error).replace(key,tr(label))
            if getattr(error,'limits',None) is not None:
                low,high=error.limits;message=tr(label)+' · '+tr('允许范围')+f' {low:g}–{high:g}'
                if '整数' in str(error):message+=' · '+tr('请输入整数')
            elif '超出范围' in str(error):message=tr(label)+' · '+tr('数值超出允许范围')
            elif '必须是整数' in str(error):message=tr(label)+' · '+tr('请输入整数')
            elif '必须是数值' in str(error):message=tr(label)+' · '+tr('请输入有效数值')
            elif '最低采样率不能大于最高采样率' in str(error):message=tr('最小值不能大于最大值')
            hint.configure(text=tr(message),fg=T.RED);hint.pack(fill='x',pady=(0,3))
            if hasattr(widget,'set_error'):widget.set_error(message)
            if first is None:first=widget
        if first is not None and focus:reveal(first);first.focus_set()
        return first is not None
