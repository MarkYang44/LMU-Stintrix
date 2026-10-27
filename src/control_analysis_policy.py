"""Responsive condition fields using the unchanged analytical policy validator."""
import tkinter as tk
from condition_match import settings,DEFAULTS
from control_fields import Field
from control_validation import Feedback
from control_theme import T
from i18n import tr

SPECS=(('fuel_l','油量容差 / L',0,20),('track_temp_c','赛道温度容差 / °C',0,20),('ambient_temp_c','气温容差 / °C',0,20),('wetness','湿度容差 / 0–1',0,.5),('rain','雨强容差 / 0–1',0,.5),('min_laps','稳定性最低圈数',3,20))


class PolicyForm:
    def __init__(self,panel,app,policy):
        self.panel=panel;self.inputs={};self.fields={};self.tiles=[];self.feedback=Feedback();self.flags={};body=panel.body
        row=app.row(body);self.toggle=app.button(row,'编辑分析条件',self.expand,False,150)
        self.defaults=app.button(row,'恢复默认条件',self.reset,False,150);panel.editors.append(self.defaults)
        self.summary=panel.variable();label=app.label(row,self.summary,9,T.MUTED);label.pack(side='left',fill='x',expand=True);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
        self.row=row;self.form=tk.Frame(body,bg=T.CARD);self.expanded=False
        for key,title,low,high in SPECS:
            tile=tk.Frame(self.form,bg=T.CARD);self.tiles.append(tile);heading=app.label(tile,title,9);heading.pack(fill='x');heading.bind('<Configure>',lambda e,w=heading:w.configure(wraplength=max(80,e.width)))
            var=panel.variable(str(policy[key]));self.inputs[key]=var;field=Field(tile,textvariable=var,width=12);field.pack(fill='x');self.fields[key]=field;panel.editors.append(field)
            hint=app.label(tile,'',9,T.RED);self.feedback.add(key,field,title,hint);var.trace_add('write',lambda *_:self.changed())
        self.form.bind('<Configure>',self.layout);self.describe()
    def layout(self,event):
        columns=max(1,min(3,event.width//230))
        for i in range(6):self.form.columnconfigure(i,weight=1 if i<columns else 0)
        for i,tile in enumerate(self.tiles):tile.grid(row=i//columns,column=i%columns,sticky='nsew',padx=8,pady=5)
    def expand(self):
        if self.expanded:self.form.pack_forget()
        else:self.form.pack(fill='x',after=self.row,pady=5)
        self.expanded=not self.expanded;self.toggle.configure(selected=self.expanded)
    def changed(self):self.describe();self.panel.changed()
    def reset(self):
        if self.panel.exporting or self.panel.writing:return
        self.feedback.clear()
        for key,variable in self.inputs.items():variable.set(str(DEFAULTS[key]))
        for key,variable in self.flags.items():variable.set(DEFAULTS[key])
        self.describe();self.panel.changed()
    def describe(self):
        self.summary.set(tr('油量 {fuel} L · 赛温 {track} °C · 气温 {ambient} °C · 湿度 {wet} · 雨强 {rain} · 最低 {laps} 圈').format(fuel=self.inputs['fuel_l'].get(),track=self.inputs['track_temp_c'].get(),ambient=self.inputs['ambient_temp_c'].get(),wet=self.inputs['wetness'].get(),rain=self.inputs['rain'].get(),laps=self.inputs['min_laps'].get()))
        from control_widgets import px
        for button in (self.toggle,self.defaults):button.configure(width=max(px(button,150),button.font.measure(tr(button.label))+px(button,36)))
    def read(self,flags):
        self.feedback.clear()
        for key,title,low,high in SPECS:
            try:settings({key:self.inputs[key].get()})
            except (ValueError,TypeError):
                error=ValueError(tr(title)+' · '+tr('请输入整数' if key=='min_laps' else '请输入有效数值'));error.fields=(key,);error.limits=(low,high)
                if not self.expanded:self.expand()
                self.feedback.show(error);raise error
        return settings({**{k:v.get() for k,v in self.inputs.items()},**flags})
