"""Optional compact tyre/strategy overlays and local per-car preferences."""
import tkinter as tk
from control_theme import T
from pathlib import Path
from storage import atomic_json
import vehiclelab


fmt=lambda x,n=1:'—' if x is None else f'{x:.{n}f}'


class Panels:
    def __init__(self,app,root):
        self.app=app;self.root=Path(root);self.windows={};self.labels={};self.passthrough={};self.topmost={};self.dialog=None
        self.refresh_visibility()
        if getattr(app,'simulator','lmu')=='lmu':app.root.after(100,self.tick)

    def save(self):atomic_json(self.root/'vehicle_settings.json',self.app.vehicle_settings)

    def toggle(self,kind):
        getattr(self.app,'layout_visibility',{}).pop(kind,None)
        self.app.vehicle_settings[kind+'_enabled']=getattr(self.app,kind+'_on').get();self.save();self.refresh_visibility()

    def hide(self,kind):
        getattr(self.app,kind+'_on').set(False);self.toggle(kind)

    def create(self,kind):
        w=tk.Toplevel(self.app.root);w.title('Stintrix · '+('四轮轮胎 HUD' if kind=='tyres' else '燃油与能量 HUD'))
        width,height=(400,300) if kind=='tyres' else (400,280)
        x,y=self.app.vehicle_settings.get(kind+'_position',[740,70 if kind=='tyres' else 395])
        w.geometry(f'{width}x{height}{int(x):+d}{int(y):+d}');w.configure(bg=T.BG);w.overrideredirect(True);w.attributes('-topmost',True);w.attributes('-alpha',.97)
        w.protocol('WM_DELETE_WINDOW',lambda:self.hide(kind))
        w.update_idletasks()
        handle=self.app.user32.GetParent(w.winfo_id()) or w.winfo_id()
        style=self.app.user32.GetWindowLongW(handle,-20)
        self.app.user32.SetWindowLongW(handle,-20,(style|0x40000)&~0x80)
        title=tk.Frame(w,bg=T.FIELD);title.pack(fill='x');tk.Label(title,text='TYRES / 四轮轮胎' if kind=='tyres' else 'STINT / 燃油与能量',fg=T.FG,bg=T.FIELD,font=('Segoe UI',10,'bold')).pack(side='left',padx=10,pady=5)
        tk.Button(title,text='×',command=lambda:self.hide(kind),bg=T.FIELD,fg=T.FG,bd=0,padx=10).pack(side='right')
        origin=[None]
        def begin(e):origin[0]=(e.x_root-w.winfo_x(),e.y_root-w.winfo_y())
        def move(e):
            if origin[0]:w.geometry(f'{e.x_root-origin[0][0]:+d}{e.y_root-origin[0][1]:+d}')
        def end(e):
            self.app.vehicle_settings[kind+'_position']=[w.winfo_x(),w.winfo_y()];self.save();origin[0]=None
        for child in [title,*title.winfo_children()]:
            if isinstance(child,tk.Button):continue
            child.bind('<Button-1>',begin);child.bind('<B1-Motion>',move);child.bind('<ButtonRelease-1>',end)
        # Built when opened, like the HUD's own menu (hud_menu.panel).
        w.bind('<Button-3>',lambda e,k=kind:__import__('hud_menu').popup_panel(self.app,k,self.hide,e))
        body=tk.Frame(w,bg=T.BG);body.pack(fill='both',expand=True,padx=10,pady=7);labels={}
        if kind=='tyres':
            for i,name in enumerate(('左前 FL','右前 FR','左后 RL','右后 RR')):
                frame=tk.Frame(body,bg=T.CARD,highlightbackground=T.EDGE,highlightthickness=1);frame.grid(row=i//2,column=i%2,sticky='nsew',padx=3,pady=3)
                tk.Label(frame,text=name,fg=T.ACCENT,bg=T.CARD,font=('Segoe UI',9,'bold')).pack(anchor='w',padx=7,pady=(4,1))
                label=tk.Label(frame,text='—',fg=T.FG,bg=T.CARD,justify='left',anchor='w',font=('Segoe UI',9));label.pack(fill='both',expand=True,padx=7,pady=(0,5));labels[vehiclelab.WHEELS[i]]=label
            for row in (0,1):body.rowconfigure(row,weight=1)
            for col in (0,1):body.columnconfigure(col,weight=1)
        else:
            for key,size in [('fuel',17),('estimate',10),('target',10),('energy',10),('status',9)]:
                label=tk.Label(body,text='—',fg=T.FG if key=='fuel' else T.MUTED,bg=T.BG,font=('Segoe UI',size,'bold' if key=='fuel' else 'normal'),anchor='w',justify='left',wraplength=375)
                label.pack(fill='x',pady=2);labels[key]=label
        foot=tk.Label(w,text='等待真实遥测 · F8 穿透 / 解锁',fg=T.MUTED,bg=T.BG,font=('Segoe UI',8),anchor='w',wraplength=380);foot.pack(side='bottom',fill='x',padx=10,pady=(0,7),before=body);labels['foot']=foot
        w.attributes('-topmost',self.app.top.get());self.topmost[kind]=self.app.top.get()
        self.windows[kind]=w;self.labels[kind]=labels;return w

    def refresh_visibility(self):
        from hud_presentation import visible
        for kind in ('tyres','strategy'):
            enabled=visible(self.app,kind,getattr(self.app,kind+'_on').get());w=self.windows.get(kind)
            if enabled:
                if w is None or not w.winfo_exists():w=self.create(kind)
                w.deiconify()
            elif w is not None and w.winfo_exists():w.withdraw()

    def tick(self):
        app=self.app
        if app.closing:return
        with app.engine.lock:
            latest=app.engine.latest;values=app.engine.vehicle_latest or {};estimate=(app.engine.vehicle_estimate or {}) if latest else {}
        name=latest.get('vehicle','') if latest else '';p=app.vehicle_settings['profiles'].get(name,app.vehicle_settings['profiles'].get('*',vehiclelab.DEFAULT_PROFILE))
        for kind,w in self.windows.items():
            if not getattr(app,'layout_visibility',{}).get(kind,getattr(app,kind+'_on').get()):continue
            if self.topmost.get(kind)!=app.top.get():
                w.attributes('-topmost',app.top.get());self.topmost[kind]=app.top.get()
            if self.passthrough.get(kind)!=app.clickthrough:
                handle=app.user32.GetParent(w.winfo_id()) or w.winfo_id();style=app.user32.GetWindowLongW(handle,-20)
                app.user32.SetWindowLongW(handle,-20,(style|0x80000|0x20) if app.clickthrough else style&~0x20);self.passthrough[kind]=app.clickthrough
            labels=self.labels[kind]
            if kind=='tyres':
                for wheel in vehiclelab.WHEELS:
                    temp=values.get(wheel+'_middle_c');alert=vehiclelab.tyre_alerts(values,p)
                    color='#ff9c94' if any(m.startswith(wheel.upper()) for m in alert) else T.FG
                    text='内/中/外 '+('/'.join(fmt(values.get(wheel+'_'+f),0) for f in ('inner_c','middle_c','outer_c')))+' °C\n'+fmt(values.get(wheel+'_pressure_kpa'))+' kPa · 胎体 '+fmt(values.get(wheel+'_carcass_c'),0)+'°\n胎况 '+fmt(values.get(wheel+'_wear_fraction')*100 if values.get(wheel+'_wear_fraction') is not None else None)+'%'
                    labels[wheel].configure(text=text,fg=color)
                alerts=vehiclelab.tyre_alerts(values,p);labels['foot'].configure(text=(' / '.join(alerts) if alerts else ('DEMO · ' if latest and latest.get('demo') else '')+(name or '等待真实遥测')+' · '+('自定义阈值' if p['alerts'] else '温压报警未启用')),fg='#ffb69c' if alerts else T.MUTED)
            else:
                labels['fuel'].configure(text='燃油 '+fmt(values.get('fuel_l'),2)+' L',fg=T.FG)
                labels['estimate'].configure(text='近期 '+str(estimate.get('count',0))+' 圈 · '+fmt(estimate.get('rate_l'),3)+' L/圈 · 可跑 '+fmt(estimate.get('range_laps'),2)+' 圈')
                labels['target'].configure(text='目标需 '+fmt(estimate.get('required_l'),2)+' L · 余量 '+fmt(estimate.get('margin_l'),2)+' L',fg='#ff9c94' if estimate.get('margin_l') is not None and estimate['margin_l']<0 else '#80ddbc')
                labels['energy'].configure(text='电池 '+fmt(values.get('battery_soc_pct'))+'% · VE '+fmt(values.get('virtual_energy_pct'))+'%\n回收 '+fmt(values.get('regen_kw'))+' kW · VE 可跑 '+fmt(estimate.get('energy_range_laps'),2)+' 圈')
                labels['status'].configure(text=('建议补 '+fmt(estimate.get('add_l'),2)+' L · 目标超油箱，需停站' if estimate.get('exceeds_capacity') else '建议补 '+fmt(estimate.get('add_l'),2)+' L · 安全余量 '+fmt(app.vehicle_settings['reserve_l'])+' L'))
                labels['foot'].configure(text=('DEMO · ' if latest and latest.get('demo') else '')+((estimate.get('remaining_source') or '赛程未知') if latest else '等待真实遥测')+' · '+('保守最高耗油' if app.vehicle_settings['rate_mode']=='conservative' else '中位耗油')+' · F8 穿透')
        app.root.after(100,self.tick)

    def settings_dialog(self):
        """These preferences are edited in the control center's Settings page."""
        self.app.open_settings('车辆策略')
