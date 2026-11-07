"""The newest video extractions on the data page itself, each one click from its report.

Reading runs in the background (the same bounded inventory as the results
window, three entries). The full list with search, history comparison and
folders stays one click away in the results window.
"""
import os
import tkinter as tk
from datetime import datetime
from control_theme import T
from i18n import tr


class RecentVideos(tk.Frame):
    LIMIT=3

    def __init__(self,app,parent):
        super().__init__(parent,bg=T.CARD);self.app=app;self.generation=0;self.entries=[]
        self.pack(fill='x',pady=(12,0))
        app.label(self,'最近提取',9,T.MUTED).pack(anchor='w',pady=(0,4))
        self.list=tk.Frame(self,bg=T.CARD);self.list.pack(fill='x')
        self.note=app.label(self.list,'正在读取最近结果…',9,T.MUTED);self.note.pack(anchor='w',pady=2)
        self.refresh()

    def refresh(self):
        from video_results import inventory
        self.generation+=1;generation=self.generation;root=self.app.data_path
        def finish(result,error):
            if generation==self.generation and self.winfo_exists():self.show(result,error)
        self.app.run_background(lambda:inventory(root,limit=self.LIMIT),finish)

    def show(self,items,error):
        from track_names import display
        for child in self.list.winfo_children():child.destroy()
        self.entries=[]
        if error is not None or not items:
            text='读取结果失败，可在「全部提取结果」中重试' if error is not None else '还没有提取结果；用「视频分析与标定」开始第一段。'
            self.note=self.app.label(self.list,text,9,T.MUTED);self.note.pack(anchor='w',pady=2);return
        for item in items:
            stamp=item.get('created_utc','')
            try:stamp=datetime.strptime(stamp,'%Y%m%dT%H%M%SZ').strftime('%Y-%m-%d %H:%M')
            except (ValueError,TypeError):stamp=str(stamp)
            track=display(item.get('identity',{}).get('track',''));name=str(item.get('video_file',''))
            if len(name)>48:name=name[:47]+'…'
            row=tk.Frame(self.list,bg=T.CARD);row.pack(fill='x',pady=2)
            kind='raw' if 'raw' in item['reports'] else 'smooth'
            button=self.app.button(row,'打开报告',lambda f=item['reports'][kind]:self.open(f),False,110);button.pack(side='right')
            self.app.label(row,' · '.join(v for v in (stamp,track) if v),10,T.FG,True).pack(side='left')
            self.app.label(row,name,9,T.MUTED).pack(side='left',padx=(10,0))
            self.entries.append((item,button))

    def open(self,file):
        try:os.startfile(file)
        except OSError as error:self.app.status.set(str(error))
