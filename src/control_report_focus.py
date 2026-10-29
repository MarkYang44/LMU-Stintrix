"""Temporary report location preserves the browser's filters and prior selection."""
import tkinter as tk
from pathlib import Path
from control_theme import T


class Focus:
    def __init__(self,view):
        self.view=view;self.targets=();self.previous=None;self.pending=False
        self.strip=tk.Frame(view.table.master,bg=T.CARD)
        view.app.label(self.strip,'已定位所选赛事报告；当前筛选保持不变',9,T.ACCENT).pack(side='left',fill='x',expand=True)
        view.app.button(self.strip,'返回原筛选',self.restore,False,140).pack(side='right')
        view.include=lambda item:item['folder'] in self.targets
        view.on_loaded=self.loaded
        view.query.trace_add('write',lambda *_:self.clear())
        view.filter.bind('<<ComboboxSelected>>',lambda _:(self.clear(),view.render()))

    def clear(self):
        self.targets=();self.previous=None;self.pending=False;self.strip.pack_forget()

    def locate(self,folders):
        view=self.view;root=Path(view.app.data_path).resolve()
        targets=tuple(dict.fromkeys(str(Path(folder).resolve()) for folder in folders
            if Path(folder).resolve()!=root and Path(folder).resolve().is_relative_to(root)))
        if not targets:return
        if self.previous is None:self.previous=(view.remembered,view.table.offset,view.table.xoffset)
        self.targets=targets;self.pending=True;view.remembered=targets
        self.strip.pack(fill='x',before=view.table);view.render()
        if not view.loading:self.loaded()

    def loaded(self):
        view=self.view
        if not self.pending or view.loading or view.error:return
        self.pending=False;chosen=tuple(key for key in self.targets if key in view.table.rows)
        if chosen:
            view.table.selection_set(chosen);view.table.scroller.move(view.table.order.index(chosen[0])*view.table.rowheight);view.selected()
        else:view.say('尚未在列表找到目标赛事，可刷新或返回原筛选')

    def restore(self):
        view=self.view;previous=self.previous;self.clear()
        if previous:view.remembered=previous[0]
        view.render()
        if previous:view.table.scroller.move(previous[1]);view.table.xoffset=previous[2];view.table.schedule()
