"""Official LMU website vector mark, rendered natively without image caches.

Source: https://lemansultimate.com/wp-content/themes/motorsport-games/build/img/lm-logo.svg
"""
import re

PATHS=(
 'M32.4732 35H4.8293C1.8032 35 -0.399615 32.1343 0.383379 29.2155L7.30791 3.40614C7.84661 1.39701 9.67032 0 11.7533 0H19.5616L13.2604 23.4882C13.1039 24.072 13.5445 24.6449 14.1498 24.6449H28.989L28.988 24.6495H28.9792L28.9849 24.6609L32.4732 34.9995V35Z',
 'M70.3207 5.78451L63.3966 31.5939C62.8574 33.603 61.0342 35 58.9507 35H52.0438L58.9549 9.23759L57.7943 6.81693L50.233 35H40.2901L47.195 9.26131L46.0365 6.81641L38.4757 35H34.2988L30.8053 24.6501H30.8017L30.8033 24.6454L34.9372 9.23501L29.7744 0H65.8747C68.9008 0 71.1031 2.8657 70.3207 5.78451Z')

def points(path):
    tokens=re.findall(r'[MLHVCZ]|-?\d+(?:\.\d+)?',path);out=[];i=0;x=y=0
    while i<len(tokens):
        command=tokens[i];i+=1
        count={'M':2,'L':2,'H':1,'V':1,'C':6,'Z':0}[command]
        v=list(map(float,tokens[i:i+count]));i+=count
        if command in ('M','L'):x,y=v;out.append((x,y))
        elif command=='H':x=v[0];out.append((x,y))
        elif command=='V':y=v[0];out.append((x,y))
        elif command=='C':
            a,b,c,d,e,f=v
            for j in range(1,13):
                t=j/12;u=1-t;out.append((u**3*x+3*u*u*t*a+3*u*t*t*c+t**3*e,u**3*y+3*u*u*t*b+3*u*t*t*d+t**3*f))
            x,y=e,f
    return out

SHAPES=tuple(points(path) for path in PATHS)

def draw(canvas,x,y,width,color='#FF1D43'):
    factor=width/71
    for shape in SHAPES:canvas.create_polygon(*[v for a,b in shape for v in (x+a*factor,y+b*factor)],fill=color,outline='')
