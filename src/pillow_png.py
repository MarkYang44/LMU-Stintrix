"""Portable raster canvas implementing the shared report drawing contract."""
from functools import lru_cache
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps


@lru_cache(maxsize=48)
def font(size, bold=False):
    candidates = (
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        'msyhbd.ttc' if bold else 'msyh.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf',
    )
    for name in candidates:
        try:return ImageFont.truetype(name, int(size))
        except OSError:pass
    return ImageFont.load_default(size=int(size))


class Canvas:
    def __init__(self, width, height):
        self.image = Image.new('RGB', (int(width), int(height)))
        self.draw = ImageDraw.Draw(self.image)

    def clear(self, color):self.draw.rectangle((0, 0, *self.image.size), fill=color)

    def fill(self, x, y, width, height, color):
        self.draw.rectangle((round(x), round(y), round(x + width - 1), round(y + height - 1)), fill=color)

    def text(self, value, x, y, width, height=45, size=27, color='#edf3fc', bold=False, align=0):
        if width <= 0 or height <= 0:return
        face=font(size,bold);value=str(value)
        # Clip each cell on its own surface, so CJK and long names cannot draw
        # over adjacent columns. Ellipsis uses measured glyph widths.
        if self.draw.textlength(value,font=face)>width:
            lo,hi=0,len(value)
            while lo<hi:
                mid=(lo+hi+1)//2
                if self.draw.textlength(value[:mid]+'…',font=face)<=width:lo=mid
                else:hi=mid-1
            value=value[:lo]+'…'
        layer=Image.new('RGBA',(max(1,round(width)),max(1,round(height))))
        pen=ImageDraw.Draw(layer);length=pen.textlength(value,font=face)
        left=0 if align==0 else (width-length)/2 if align==1 else width-length
        pen.text((left,0),value,font=face,fill=color,anchor='lt',stroke_width=1 if bold else 0)
        self.image.paste(layer,(round(x),round(y)),layer)

    def photo(self, path, bounds, destination):
        with Image.open(path) as original:
            w,h=original.size;left,top,right,bottom=bounds
            if not 0<=left<right<=1 or not 0<=top<bottom<=1:raise ValueError('Invalid image crop')
            crop=original.convert('RGBA').crop((round(left*w),round(top*h),round(right*w),round(bottom*h)))
        x,y,w,h=destination
        with ImageOps.contain(crop,(round(w),round(h)),Image.Resampling.LANCZOS) as image:
            self.image.paste(image,(round(x+(w-image.width)/2),round(y+(h-image.height)/2)),image)
        crop.close()

    def save(self,path):self.image.save(path,format='PNG')
    def close(self):self.image.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
