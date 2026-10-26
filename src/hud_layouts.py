"""Private named presentation layouts and bounded, atomic undo history."""
from copy import deepcopy
from datetime import datetime,timezone
import json,math
from pathlib import Path
from uuid import uuid4
from storage import atomic_json

KINDS=('main','tyres','strategy','pit','stint','weather')
SIZES={'main':(640,228),'tyres':(400,300),'strategy':(400,280),'pit':(370,210),'stint':(370,210),'weather':(370,210)}


def defaults():
    panels={}
    for i,kind in enumerate(KINDS):
        x,y=(70,70) if kind=='main' else (740,70 if kind=='tyres' else 395) if kind in ('tyres','strategy') else (1160,70+(i-3)*225)
        panels[kind]=dict(x=x,y=y,width=SIZES[kind][0],height=SIZES[kind][1],opacity=1. if kind=='main' else .97,visible=kind=='main')
    return dict(panels=panels,mode='normal',window='10',topmost=True,clickthrough=False)


def numeric_bounds(key):
    return (-100000,100000) if key in ('x','y') else (.2,1) if key=='opacity' else (60,8192)


def normalize(value):
    if not isinstance(value,dict) or not isinstance(value.get('panels'),dict):raise ValueError('布局数据无效')
    result=defaults()
    for kind in KINDS:
        panel=value['panels'].get(kind,result['panels'][kind])
        if not isinstance(panel,dict):raise ValueError('布局数据无效')
        for key in ('x','y','width','height','opacity'):
            v=panel.get(key,result['panels'][kind][key])
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('布局数值无效')
            low,high=numeric_bounds(key)
            if not low<=v<=high:raise ValueError('布局数值超出范围')
            result['panels'][kind][key]=float(v) if key=='opacity' else round(v)
        visible=panel.get('visible',result['panels'][kind]['visible'])
        if not isinstance(visible,bool):raise ValueError('布局显隐值无效')
        result['panels'][kind]['visible']=visible
    for key,allowed in [('mode',('normal','curves','controls')),('window',('5','10','20'))]:
        if value.get(key,result[key]) not in allowed:raise ValueError('布局显示模式无效')
        result[key]=value.get(key,result[key])
    if 'geometry_mode' in value:
        if value['geometry_mode'] not in ('normal','curves','controls'):raise ValueError('布局显示模式无效')
        result['geometry_mode']=value['geometry_mode']
    for key in ('topmost','clickthrough'):
        if not isinstance(value.get(key,result[key]),bool):raise ValueError('布局开关值无效')
        result[key]=value.get(key,result[key])
    return result


class LayoutStore:
    def __init__(self,root):self.path=Path(root)/'hud_layouts.json'
    def load(self):
        if not self.path.exists():return dict(version=1,active='',profiles={},history=[])
        try:
            if self.path.stat().st_size>2_000_000:raise ValueError('布局文件过大')
            value=json.loads(self.path.read_text(encoding='utf-8-sig'))
            if value.get('version')!=1 or not isinstance(value.get('profiles'),dict) or not isinstance(value.get('history'),list):raise ValueError('布局文件格式不受支持')
            if len(value['profiles'])>20 or len(value['history'])>12:raise ValueError('布局文件超出容量')
            for profile in value['profiles'].values():normalize(profile)
            if 'presentation' in value:normalize(value['presentation'])
            for item in value['history']:
                if not isinstance(item,dict) or not all(isinstance(item.get(k),str) for k in ('id','time','reason','active')) or not isinstance(item.get('profiles'),dict):raise ValueError('布局备份格式无效')
                normalize(item.get('runtime'))
            if value.get('active') and value['active'] not in value['profiles']:raise ValueError('当前布局不存在')
            return value
        except (OSError,TypeError,AttributeError,json.JSONDecodeError) as error:raise ValueError('布局文件无法读取，原文件已保留') from error
    def current(self):
        value=self.load()
        if 'presentation' in value:return normalize(value['presentation'])
        return normalize(value['profiles'][value['active']]) if value.get('active') else None
    def change(self,reason,runtime,edit):
        value=self.load();backup=dict(id=uuid4().hex,time=datetime.now(timezone.utc).isoformat(),reason=reason,
            active=value.get('active',''),profiles=deepcopy(value['profiles']),runtime=normalize(runtime))
        value['presentation']=normalize(runtime);edit(value);value['history']=(value['history']+[backup])[-12:];atomic_json(self.path,value);return value
    def save(self,name,snapshot,runtime):
        name=name.strip()
        if not name or len(name)>40 or any(ord(c)<32 for c in name):raise ValueError('布局名称需为 1–40 个可见字符')
        snapshot=normalize(snapshot)
        def edit(value):
            if name not in value['profiles'] and len(value['profiles'])>=20:raise ValueError('最多保存 20 套布局')
            value['profiles'][name]=snapshot;value['active']=name;value['presentation']=snapshot
        return self.change('save',runtime,edit)
    def select(self,name,runtime):
        def edit(value):
            if name not in value['profiles']:raise ValueError('布局不存在')
            value['active']=name
            value['presentation']=value['profiles'][name]
        return self.change('switch',runtime,edit)
    def backup(self,runtime):return self.change('backup',runtime,lambda value:None)
    def restore(self,identifier,runtime):
        current=self.load();entry=next((h for h in current['history'] if h['id']==identifier),None)
        if entry is None:raise ValueError('备份不存在')
        profiles={name:normalize(p) for name,p in entry['profiles'].items()};snapshot=normalize(entry['runtime'])
        if entry['active'] and entry['active'] not in profiles:raise ValueError('备份中的当前布局无效')
        def edit(value):value.update(active=entry['active'],profiles=profiles,presentation=snapshot)
        self.change('restore',runtime,edit);return snapshot
