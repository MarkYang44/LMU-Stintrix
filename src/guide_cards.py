"""Native editorial cards with disposable, viewport-driven WebP images."""
import tkinter as tk
from pathlib import Path
from control_theme import T
from control_widgets import GlassCard,px
from paths import ASSETS
from i18n import tr
from control_feedback import ImageSurface


def diagram_image(original,foreground):
    """Keep official geometry, grey layout differences, colours and alpha."""
    from PIL import Image,ImageChops,ImageOps,ImageColor
    image=original.convert('RGBA');rgb=image.convert('RGB');alpha=image.getchannel('A')
    colors=image.getcolors(image.width*image.height) or []
    ink=max(((count,color) for count,color in colors if color[3]>200),default=(0,(255,255,255,255)))[1]
    source_light=sum(ink[:3])>384;target_light=sum(ImageColor.getrgb(foreground))>384
    if source_light!=target_light:
        r,g,b=rgb.split();difference=ImageChops.lighter(ImageChops.difference(r,g),ImageChops.difference(g,b))
        greys=difference.point([255 if i<12 else 0 for i in range(256)])
        rgb=Image.composite(ImageOps.invert(rgb),rgb,greys)
    result=rgb.convert('RGBA');result.putalpha(alpha);return result


class Picture(ImageSurface):
    """Decode only visible images, release on scroll-away; no global image cache."""
    def __init__(self,parent,center,item):
        super().__init__(parent,height=210)
        self.center=center;self.item=item;self.photo=None;self.size=None;self.job=None;self.error='';self.loading=None;self.revision=0
        self.pack(fill='x',pady=(0,px(parent,16)))
        self.bind('<Configure>',self.changed);self.bind('<Destroy>',self.dispose,add='+')
        self.bind('<Unmap>',self.release,add='+');self.bind('<Map>',self.changed,add='+')
        self.command=self.register(self.view_changed)
        self.view_trace=center.scroll.tk.call('trace','add','execution',center.scroll._w,'leave',self.command)

    def view_changed(self,*args):self.changed()
    def picture_height(self,width):
        return round(min(width*.7,px(self,240))) if self.item.get('diagram') else round(min(1200,width)*9/16)
    def changed(self,_=None):
        width=self.winfo_width()
        if width>1:
            height=self.picture_height(width)
            if int(self.cget('height'))!=height:self.configure(height=height)
        self.coords(self.hint,max(1,width)/2,max(1,self.winfo_height())/2)
        if self.job is None and self.winfo_exists():self.job=self.after(90,self.render)
    def release(self,event=None):
        if self.job:
            try:self.after_cancel(self.job)
            except tk.TclError:pass
        self.job=None;self.revision+=1;self.loading=None
        try:self.motion.cancel();self.itemconfigure(self.bitmap,state='hidden')
        except tk.TclError:pass
        self.photo=None;self.image=None;self.size=None
    def dispose(self,event):
        if event.widget is not self:return
        self.release()
        try:self.tk.call('trace','remove','execution',self.center.scroll._w,'leave',self.command)
        except tk.TclError:pass

    def render(self):
        if self.job:
            try:self.after_cancel(self.job)
            except tk.TclError:pass
        self.job=None
        if not self.winfo_exists() or self.center.closing:return
        width=max(1,min(1200,self.winfo_width()));height=max(1,self.picture_height(width))
        # A smaller image on wide windows keeps the complete photograph visible.
        if self.winfo_width()<=1:return
        if int(self.cget('height'))!=height:self.configure(height=height)
        top=self.winfo_rooty();viewport=self.center.scroll
        visible=self.winfo_ismapped() and top+height>=viewport.winfo_rooty()-80 and top<=viewport.winfo_rooty()+viewport.winfo_height()+80
        if not visible:
            if self.photo is not None:self.itemconfigure(self.bitmap,state='hidden');self.photo=None;self.image=None;self.size=None
            return
        if self.size==(width,height):return
        if self.loading==(width,height):return
        if self.item.get('local_image'):
            path=Path(self.item['local_image']).resolve()
            if not path.is_relative_to((Path(self.center.data_path)/'assets/evo').resolve()):self.error='Invalid private image path';return
        else:
            path=(ASSETS/'guide'/self.item['image']).resolve()
            if not path.is_relative_to((ASSETS/'guide/media').resolve()):self.error='Invalid guide image path';return
        self.revision+=1;revision=self.revision;self.loading=(width,height)
        tint=T.FG
        self.itemconfigure(self.hint,text=tr('正在加载图片…'),state='normal')
        def decode():
            from PIL import Image,WebPImagePlugin
            with Image.open(path,formats=['WEBP','JPEG','PNG']) as original:
                original.thumbnail((width,height),Image.Resampling.LANCZOS)
                if self.item.get('diagram') and self.item.get('diagram_tint',True):
                    return diagram_image(original,tint)
                return original.copy()
        def ready(image,error):
            if not self.winfo_exists() or revision!=self.revision:return
            self.loading=None
            if error:
                self.error=error;self.itemconfigure(self.hint,text=tr('图片暂不可用'),state='normal');return
            if not self.winfo_ismapped():return
            top=self.winfo_rooty();viewport=self.center.scroll
            if top+height<viewport.winfo_rooty()-80 or top>viewport.winfo_rooty()+viewport.winfo_height()+80:return
            self.error='';self.size=(width,height);self.show(image)
        self.center.run_background(decode,ready)


class Sources(tk.Frame):
    """Sources are lazy, collapsed initially, and retained across menu rebuilds."""
    def __init__(self,parent,cards,pairs):
        from hashlib import sha256
        super().__init__(parent,bg=parent.cget('bg'))
        self.cards=cards;self.center=cards.center;self.library=cards.library;self.pairs=pairs
        self.flag=sha256('\n'.join(url for _,url in pairs).encode()).hexdigest()[:20]
        self.expanded=cards.page.state.setdefault('sources',[])
        self.opened=False;self.built=False
        self.pack(fill='x',pady=(6,12))
        row=self.center.row(self)
        self.heading=self.center.button(row,'',self.toggle,width=180)
        self.panel=tk.Frame(self,bg=T.FIELD)
        self.set_open(self.flag in self.expanded)
    def set_open(self,opened):
        self.opened=opened
        self.heading.label=('▾ ' if opened else '▸ ')+self.library.tr('来源链接','Sources')+f' · {len(self.pairs)}'
        self.heading.paint()
        if opened:
            if not self.built:
                content=tk.Frame(self.panel,bg=T.FIELD);content.pack(fill='x',padx=12,pady=12)
                for label,url in self.pairs:self.cards.text(content,label+'\n'+url,9,T.MUTED)
                self.center.button(self.center.row(content),self.library.tr('复制来源链接','Copy sources'),self.copy,width=150)
                self.built=True
            self.panel.pack(fill='x',pady=(4,0))
            if self.flag not in self.expanded:self.expanded.append(self.flag)
        else:
            self.panel.pack_forget()
            if self.flag in self.expanded:self.expanded.remove(self.flag)
    def toggle(self):self.set_open(not self.opened)
    def copy(self):
        self.center.root.clipboard_clear();self.center.root.clipboard_append('\n'.join(url for _,url in self.pairs))
        self.center.status.set(self.library.tr('来源链接已复制','Source URLs copied'))


class Cards:
    def __init__(self,page):self.page=page;self.center=page.center;self.library=page.library
    def text(self,parent,text,size=10,color=None,bold=False):
        label=self.center.label(parent,text,size,color,bold);label.pack(fill='x',pady=(0,px(parent,10)))
        label.bind('<Configure>',lambda e:label.configure(wraplength=max(80,e.width)))
        return label
    def surface(self,parent,title,subtitle=''):
        card=GlassCard(parent);card.pack(fill='x',pady=(0,px(parent,18)));body=card.body
        self.text(body,title,16,T.FG,True)
        if subtitle:self.text(body,subtitle,9,T.ACCENT)
        return body
    def sources(self,parent,values):
        pairs=[(label,url) for label,url in values if url]
        return Sources(parent,self,pairs) if pairs else None
    def practice(self,body,item):
        note=item['note'];tr=self.library.tr
        self.text(body,tr('来源摘记：','Source note: ')+self.library.text(note,'observation'),10,T.MUTED)
        self.text(body,tr('练习建议：','Practice: ')+self.library.text(note,'exercise'),11,T.FG)
        self.text(body,tr('资料检查：','Reviewed: ')+note['checked_on'],9,T.MUTED)
    def review(self,body,rec):
        value=rec['review'];tr=self.library.tr
        self.text(body,tr('适用游戏版本：','Applicable game version: ')+(value.get('applicable_version') or tr('未验证','Unverified'))+' · '+tr('资料检查：','Reviewed: ')+value['checked_on'],9,T.MUTED)
        self.text(body,tr('暂无该推荐的版本实测证据','No build-specific driving evidence for this recommendation'),9,T.MUTED)
    def actions(self,body,kind,item,key=None):
        tr=self.library.tr;row=self.center.row(body);slug=item['slug']
        title=('★ ' if slug in self.library.favorites[kind] else '☆ ')+tr('收藏','Favorite')
        button=self.center.button(row,title,lambda:self.page.favorite(kind,slug),width=120)
        self.page.favorite_buttons.setdefault((kind,slug),[]).append(button)
        if key:
            button=self.center.button(row,tr('移出对比','Remove') if key in self.page.state['comparison'] else tr('加入对比','Compare'),lambda:self.page.select(key),key in self.page.state['comparison'],width=130)
            self.page.compare_buttons.setdefault(key,[]).append(button)
    def car(self,parent,item,rec=None,comparison=False):
        tr=self.library.tr;key=rec['key'] if rec else 'car:'+item['slug']
        track=self.library.data['tracks'][rec['track_slug']] if rec else None
        from track_names import display
        subtitle=(display(track['name'],self.library.language)+' // ' if track else '')+item['car_class']+(' // SLEEPER PICK' if rec and rec['sleeper'] else '')
        body=self.surface(parent,item['name'],subtitle);Picture(body,self.center,item)
        if rec:self.text(body,self.library.text(rec,'fit'),11)
        self.text(body,tr('优点：','Strengths: ')+self.library.text(item,'strength'),11)
        self.text(body,tr('注意事项：','Caveats: ')+self.library.text(item,'caution'),11)
        self.practice(body,item)
        if rec:self.review(body,rec)
        self.actions(body,'cars',item,key)
        if not rec:self.recommendations(body,item)
        self.sources(body,[(tr('LMU 官方车型资料','Official LMU car page'),item['source_url']),(item['note']['source_name'],item['note']['source_url'])]+([(tr('推荐来源','Recommendation source'),url) for url in rec['review']['sources']] if rec else []))
        return body
    def recommendations(self,body,item):
        from track_names import display
        tr=self.library.tr;recs=item['recommendations'];holder=tk.Frame(body,bg=T.CARD)
        def toggle():
            expanded=self.page.state['expanded'];flag='car:'+item['slug']
            if holder.winfo_manager():holder.pack_forget();expanded[:]=[v for v in expanded if v!=flag];return
            if not holder.winfo_children():
                if not recs:self.text(holder,tr('原资料暂无车型推荐赛道。','No recommended circuits in this snapshot.'),10,T.MUTED)
                for value in recs:
                    target=self.library.data['tracks'][value['track_slug']]
                    panel=self.surface(holder,display(target['name'],self.library.language),'SLEEPER PICK' if value['sleeper'] else '')
                    self.text(panel,self.library.text(value,'fit'),11);self.review(panel,value)
                    row=self.center.row(panel);self.center.button(row,tr('查看赛道','View circuit'),lambda slug=target['slug']:self.page.jump('tracks',slug),width=140)
                    self.sources(panel,[(tr('来源','Source'),url) for url in value['review']['sources']])
            holder.pack(fill='x',pady=12)
            if flag not in expanded:expanded.append(flag)
        row=self.center.row(body);button=self.center.button(row,tr('推荐它的赛道','Recommended at')+f' · {len(recs)}',toggle,width=210)
        if 'car:'+item['slug'] in self.page.state['expanded']:toggle()
        return button
    def track(self,parent,item,recs):
        from track_names import display
        tr=self.library.tr;body=self.surface(parent,display(item['name'],self.library.language),self.library.text(item,'location')+' · '+item['length_km']+' km'+(' · DLC' if item['is_dlc'] else ''))
        Picture(body,self.center,item)
        for key,title in [('character',tr('赛道特性：','Circuit character: ')),('challenge',tr('主要挑战：','Challenge: ')),('advice',tr('驾驶建议：','Driving advice: '))]:self.text(body,title+self.library.text(item,key),11)
        self.practice(body,item);self.actions(body,'tracks',item)
        holder=tk.Frame(body,bg=T.CARD)
        def recommendations():
            expanded=self.page.state['expanded'];flag='track:'+item['slug']
            if holder.winfo_manager():holder.pack_forget();expanded[:]=[v for v in expanded if v!=flag];return
            if not holder.winfo_children():
                for rec in recs:self.car(holder,self.library.data['cars'][rec['car_slug']],rec)
            holder.pack(fill='x',pady=12)
            if flag not in expanded:expanded.append(flag)
        row=self.center.row(body);self.center.button(row,tr('展开 / 收起车型建议','Show / hide recommendations')+f' · {len(recs)}',recommendations,width=270)
        if 'track:'+item['slug'] in self.page.state['expanded']:recommendations()
        self.sources(body,[(tr('LMU 官方赛道资料','Official LMU circuit page'),item['source_url']),(item['note']['source_name'],item['note']['source_url'])])
        return body
