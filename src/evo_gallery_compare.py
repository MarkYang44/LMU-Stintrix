"""Two exact EVO catalogue entries, using the shared viewport image component."""
import tkinter as tk
import webbrowser
from control_theme import T
from control_widgets import px
from control_flow import install
from evo_art import item,catalog
from guide_cards import Picture
from i18n import tr


class Comparison(tk.Frame):
    def __init__(self,parent,app,entries):
        super().__init__(parent,bg=T.CARD);self.cells=[];self.pack(fill='x');self.bind('<Configure>',self.layout)
        from evo_gallery import GROUPS
        for i,entry in enumerate(entries):
            cell=tk.Frame(self,bg=T.FIELD);self.cells.append(cell)
            for text,size,color,bold in [(chr(65+i)+' / '+entry['name'],14,T.FG,True),
                    (entry['brand']+' · '+tr(GROUPS[entry['group']]),10,T.ACCENT,False)]:
                label=app.label(cell,text,size,color,bold);label.configure(wraplength=280);label.pack(fill='x',padx=12,pady=9)
                label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(80,e.width)))
            art=item('cars',entry['name'],root=app.data_path)
            if art:Picture(cell,app,art)
            else:app.label(cell,'图片尚未下载或该型号暂无匹配官方图。',10,T.MUTED).pack(fill='x',padx=12,pady=28)
            row=app.row(cell);install(row)
            app.button(row,'官方图片来源',lambda e=entry:webbrowser.open(e.get('source',catalog()['source'])),False,145)
        self.layout()

    def layout(self,_=None):
        wide=self.winfo_width()>=px(self,660)
        for i,cell in enumerate(self.cells):
            cell.grid(row=0 if wide else i,column=i if wide else 0,sticky='nsew',padx=(0,8) if wide and i==0 else 0,pady=(0,10))
        self.columnconfigure(0,weight=1,uniform='evo-cars' if wide else '')
        self.columnconfigure(1,weight=1 if wide else 0,uniform='evo-cars' if wide else '')
