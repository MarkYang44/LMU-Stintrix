"""Calibrated LMU pedal arcs; missing HUD is distinct from pedal zero."""
import math


def number(value, low=None, high=None):
    value=float(value)
    if not math.isfinite(value) or low is not None and value<low or high is not None and value>high:
        raise ValueError('数值超出范围')
    return value


def clock(value):
    parts=str(value).strip().split(':')
    if not 1<=len(parts)<=3:raise ValueError('时间使用 秒 或 分:秒 或 时:分:秒')
    values=[number(v,0) for v in parts]
    if len(values)>1 and any(v>=60 for v in values[1:]):raise ValueError('分秒必须小于 60')
    return sum(v*60**i for i,v in enumerate(reversed(values)))


def arc_points(arc, steps=101):
    center,zero,full=arc['points'];cx,cy=center
    radius=math.dist(center,zero);other=math.dist(center,full)
    if radius<8 or abs(radius-other)>max(6,radius*.15):raise ValueError('圆心、零点和满量程点不在同一圆弧上')
    a=math.atan2(zero[1]-cy,zero[0]-cx);b=math.atan2(full[1]-cy,full[0]-cx)
    direction=1 if arc.get('clockwise',True) else -1
    sweep=(direction*(b-a))%(2*math.pi)
    if not .08<sweep<math.pi*1.6:raise ValueError('请检查圆弧方向；零点与满量程点不能重合')
    thickness=number(arc.get('thickness',6),2,40)
    return [[(round(cx+(radius+offset)*math.cos(a+direction*sweep*i/(steps-1))),
              round(cy+(radius+offset)*math.sin(a+direction*sweep*i/(steps-1))))
             for offset in (-thickness/3,0,thickness/3)] for i in range(steps)]


def colored(rgb, channel):
    r,g,b=rgb
    if channel=='throttle':return g>65 and g>r*1.25 and g>b*1.08
    return r>85 and r>g*1.45 and r>b*1.15


def pedal(image, points, channel):
    px=image.load();w,h=image.size;hits=[]
    for samples in points:
        hits.append(sum(0<=x<w and 0<=y<h and colored(px[x,y],channel) for x,y in samples)>=2)
    # A valid fill is a prefix from the calibrated zero, allowing small compression holes.
    active=[i for i,v in enumerate(hits) if v]
    if not active:return 0.,1.
    edge=max(active);continuity=sum(hits[:edge+1])/(edge+1)
    if continuity<.75 or min(active)>5:return None,0.
    value=min(1.,(edge+1)/(len(hits)-1))
    return value,continuity


def anchor_signature(image, box):
    from PIL import ImageStat
    patch=image.crop(box).convert('L').resize((32,16))
    if ImageStat.Stat(patch).stddev[0]<12:raise ValueError('HUD 可见性锚点对比度太低；框选固定文字（例如 KPH）')
    return list(patch.get_flattened_data())


def visible(image, box, signature):
    current=list(image.crop(box).convert('L').resize((32,16)).get_flattened_data())
    # A fixed label must remain legible; a black/covered HUD cannot be pedal zero.
    count=len(current);total=sum(current)
    # Exact population-variance threshold on integer pixels; no Fraction/stddev
    # work per frame, with the same threshold and anchor comparison as before.
    if count*sum(v*v for v in current)-total*total<100*count*count:return False
    return sum(abs(a-b) for a,b in zip(current,signature))<35*len(signature)


def ocr_number(text, timer=False, unit='m'):
    import re
    text=text.strip().replace('，','.').replace(',','.').replace('：',':')
    text=text.replace('O','0').replace('o','0').replace(' ','')
    if timer:text=text.replace('•.',':').replace('•',':').replace('·',':')
    pattern=r'\d{1,2}:\d{2}(?:\.\d{1,3})?' if timer else r'\d+(?:\.\d+)?'
    match=re.fullmatch(pattern,text)
    if match is None:return None
    try:return clock(text) if timer else number(text,0)*(1000 if unit=='km' else 1)
    except ValueError:return None
