"""Local-only PNG achievement cards with explicit privacy choices."""
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from record_presentation import number,tire,session_type
from track_names import display,layout
from i18n import tr


def payload(entry,details,show_name=False,show_date=False):
    s=entry['session'];podium='place' in entry
    c=details.get('start',{}) if podium else details.get('conditions',{})
    duration=details.get('fastest_s') if podium else entry['time_s']
    result=dict(title=tr({1:'冠军',2:'亚军',3:'季军'}[entry['place']])+' · '+tr('同组领奖台') if podium else tr('赛道最快圈'),
        track=display(entry['track']),layout=layout(entry['track'],entry['layout'],entry['length_m']) if entry.get('length_m') else display(entry['layout']),
        vehicle=str(s.get('vehicle') or tr('未知')),group=entry['vehicle_class'],
        time=f'{int(duration//60)}:{duration%60:06.3f}' if isinstance(duration,(int,float)) and duration>0 else tr('未知'),
        time_label=tr('个人最快圈'),footer_label=tr('来自本机真实赛事记录'),
        conditions=[(tr('圈起点油量') if not podium else tr('记录起点油量'),number(c.get('fuel_l'),' L')),
            (tr('前轮胎种'),tire(c,'front')),(tr('赛道温度'),number(c.get('track_temp_c'),' °C')),
            (tr('路面湿度'),number(c.get('wetness')*100 if isinstance(c.get('wetness'),(int,float)) else None,' %',0))])
    if podium:
        from control_podiums import place,elapsed
        summary=entry['summary'];result['result']=tr('同组发车名次')+' '+place(summary.get('grid_class_place'))+' / '+tr('同组完赛名次')+' '+place(entry['place'])
        result['context']=tr('官方 XML 成绩 · 无遥测条件') if entry.get('xml_only') else tr('比赛用时')+' '+(elapsed(details.get('race_s')) if details.get('race_s') is not None else tr('未知'))
    else:result['result']=tr('第 ')+str(entry['lap']['number'])+tr(' 圈');result['context']=tr('最快有效完整圈')
    result['context']+=' · '+session_type(s.get('session'))
    if show_name:result['driver']=str(s.get('driver') or tr('未知'))
    if show_date:result['date']=str(s.get('started_utc') or tr('未知'))
    return result


def compose(value):
    from PIL import Image,ImageDraw,ImageFont,ImageOps
    from control_record_art import vehicle_picture
    from paths import ASSETS
    image=Image.new('RGB',(1920,1080),'#f6f7f9');draw=ImageDraw.Draw(image)
    regular=Path('C:/Windows/Fonts/msyh.ttc');bold=Path('C:/Windows/Fonts/msyhbd.ttc')
    def font(size,strong=False):return ImageFont.truetype(str(bold if strong else regular),size)
    def text(label,xy,size=28,color='#172335',strong=False,width=1750):
        f=font(size,strong);label=str(label)
        if draw.textlength(label,font=f)>width:
            while label and draw.textlength(label+'…',font=f)>width:label=label[:-1]
            label+='…'
        draw.text(xy,label,font=f,fill=color)
    text('STINTRIX', (78,54),36,strong=True);text('LE MANS ULTIMATE',(1440,66),24,color='#6d7988',width=400)
    text(value['title'],(80,135),28,color='#778020',strong=True)
    text(value['track'],(76,195),54,strong=True,width=1710)
    text(value['layout'],(80,277),25,color='#687586')
    draw.rounded_rectangle((80,340,970,900),radius=28,fill='white')
    item=vehicle_picture(value['vehicle']);photo=None
    if item:
        path=(ASSETS/'guide'/item['image']).resolve()
        if path.is_relative_to((ASSETS/'guide/media').resolve()):
            with Image.open(path) as source:photo=ImageOps.contain(source.convert('RGB'),(842,460),Image.Resampling.LANCZOS)
    if photo:image.paste(photo,(104+(842-photo.width)//2,365+(460-photo.height)//2))
    else:text(value['vehicle'],(120,520),30,width=790)
    text(value['group']+' · '+value['vehicle'],(116,832),25,strong=True,width=805)
    text(value['time'],(1020,350),106,color='#536623',strong=True,width=800)
    text(value.get('time_label',tr('个人最快圈')),(1030,490),25,color='#687586')
    text(value['result'],(1030,550),28,strong=True,width=790)
    text(value['context'],(1030,600),26,color='#687586',width=790)
    for i,(label,data) in enumerate(value['conditions']):
        x=1020+(i%2)*398;y=665+(i//2)*120
        draw.rounded_rectangle((x,y,x+375,y+106),radius=18,fill='white')
        text(label,(x+20,y+12),22,color='#687586',width=335);text(data,(x+20,y+49),30,strong=True,width=335)
    footer=[]
    if 'driver' in value:footer.append(value['driver'])
    if 'date' in value:footer.append(value['date'])
    text(' · '.join(footer) if footer else value.get('footer_label',tr('来自本机真实赛事记录')),(80,955),25,color='#687586',width=1600)
    text('LMU STINTRIX  /  DRIVE · RECORD · REFLECT',(80,1010),20,color='#87929e')
    return image


def render(root,value):
    return save_image(root,compose(value))


def save_image(root,image):
    """Write the approved full-resolution preview; never overwrite an older card."""
    folder=Path(root)/'PersonalRecords/AchievementCards';folder.mkdir(parents=True,exist_ok=True)
    path=folder/('stintrix-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:8]+'.png')
    if path.exists():raise FileExistsError(str(path))
    pending=folder/('.'+uuid4().hex+'.pending');created=False
    try:
        with pending.open('xb') as stream:created=True;image.save(stream,format='PNG')
        # Windows rename is atomic and refuses to overwrite an existing target.
        if path.exists():raise FileExistsError(str(path))
        pending.rename(path);return str(path)
    finally:
        if created:pending.unlink(missing_ok=True)
