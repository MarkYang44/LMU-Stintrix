"""Aligned native comparison rows with a readable stacked narrow layout."""
import tkinter as tk
from control_theme import T
from control_widgets import px
from guide_cards import Picture
from track_names import display


class Comparison(tk.Frame):
    def __init__(self,parent,page):
        super().__init__(parent,bg=T.BG);self.page=page;self.sections=[];self.wide=None
        self.items=[(key,*page.library.item(key)) for key in page.state['comparison'] if page.library.item(key)[0]]
        self.pack(fill='x');self.bind('<Configure>',self.layout)
        self.section('',self.identity)
        self.section('',lambda cell,key,car,rec:Picture(cell,page.center,car))
        self.section(page.tr('优点','Strengths'),lambda cell,key,car,rec:self.text(cell,page.library.text(car,'strength')))
        self.section(page.tr('注意事项','Caveats'),lambda cell,key,car,rec:self.text(cell,page.library.text(car,'caution')))
        self.section(page.tr('练习建议','Practice'),lambda cell,key,car,rec:self.text(cell,page.library.text(car['note'],'exercise')))
        self.section(page.tr('来源摘记','Source note'),lambda cell,key,car,rec:self.text(cell,page.library.text(car['note'],'observation')))
        self.section(page.tr('赛道适配与验证','Circuit fit and evidence'),self.fit)
        self.section('',lambda cell,key,car,rec:page.cards.actions(cell,'cars',car,key))
        self.section(page.tr('资料来源','Sources'),self.sources)
        self.layout()

    def text(self,parent,text,size=11,color=None,bold=False):
        label=self.page.center.label(parent,text,size,color or T.FG,bold);label.configure(wraplength=240)
        label.pack(fill='x',padx=10,pady=8);label.bind('<Configure>',lambda e:label.configure(wraplength=max(80,e.width)));return label

    def section(self,title,builder):
        heading=self.page.center.label(self,title,10,T.ACCENT,True) if title else None
        cells=[]
        for key,car,rec in self.items:
            cell=tk.Frame(self,bg=T.CARD);caption=self.page.center.label(cell,car['name'],9,T.MUTED)
            caption.configure(wraplength=240);caption.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(80,e.width)))
            builder(cell,key,car,rec);cells.append((cell,caption))
        self.sections.append((heading,cells))

    def identity(self,cell,key,car,rec):
        index=next(i for i,item in enumerate(self.items) if item[0]==key)
        self.text(cell,chr(65+index)+' / '+car['name'],14,T.FG,True)
        text=car['car_class']
        if rec:text+=' · '+display(self.page.library.data['tracks'][rec['track_slug']]['name'],self.page.library.language)+(' · SLEEPER PICK' if rec['sleeper'] else '')
        self.text(cell,text,10,T.ACCENT)

    def fit(self,cell,key,car,rec):
        library=self.page.library;tr=self.page.tr
        if rec:
            self.text(cell,library.text(rec,'fit'))
            self.text(cell,tr('适用游戏版本：','Applicable game version: ')+(rec['review'].get('applicable_version') or tr('未验证','Unverified')),9,T.MUTED)
            self.text(cell,tr('暂无该推荐的版本实测证据','No build-specific driving evidence for this recommendation'),9,T.MUTED)
            self.text(cell,tr('资料检查：','Reviewed: ')+rec['review']['checked_on'],9,T.MUTED)
        else:
            names=list(dict.fromkeys(display(library.data['tracks'][v['track_slug']]['name'],library.language) for v in car['recommendations']))
            self.text(cell,' · '.join(names) or tr('原资料暂无车型推荐赛道。','No recommended circuits in this snapshot.'))
            self.text(cell,tr('适配来自原资料，尚无版本实测证据。','Fits are from the source snapshot, without build-specific driving evidence.'),9,T.MUTED)
            self.page.cards.recommendations(cell,car)
        self.text(cell,tr('资料检查：','Reviewed: ')+car['note']['checked_on'],9,T.MUTED)

    def sources(self,cell,key,car,rec):
        tr=self.page.tr
        pairs=[(tr('LMU 官方车型资料','Official LMU car page'),car['source_url']),(car['note']['source_name'],car['note']['source_url'])]
        if rec:pairs.extend((tr('推荐来源','Recommendation source'),url) for url in rec['review']['sources'])
        self.page.cards.sources(cell,pairs)

    def layout(self,_=None):
        count=len(self.items);wide=self.winfo_width()>=px(self,320*count)
        if self.wide==wide:return
        self.wide=wide
        for i in range(max(1,count)):self.columnconfigure(i,weight=1 if wide or i==0 else 0,uniform='comparison' if wide else '',minsize=0)
        row=0
        for heading,cells in self.sections:
            if heading is not None:heading.grid(row=row,column=0,columnspan=count if wide else 1,sticky='w',pady=(16,5));row+=1
            for i,(cell,caption) in enumerate(cells):
                if wide:caption.pack_forget()
                else:caption.pack(fill='x',padx=10,pady=(8,0),before=next(c for c in cell.winfo_children() if c is not caption))
                cell.grid(row=row if wide else row+i,column=i if wide else 0,sticky='nsew',padx=(0,px(self,8)) if wide and i<count-1 else 0,pady=(0,6))
            row+=1 if wide else len(cells)
