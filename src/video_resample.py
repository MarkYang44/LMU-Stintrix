"""Derived 120 Hz pedal interpolation; never mutates or replaces source rows."""
import bisect
import csv
import json
import math
from pathlib import Path


def slopes(x, y):
    h=[b-a for a,b in zip(x,x[1:])]
    d=[(b-a)/dt for a,b,dt in zip(y,y[1:],h)]
    if len(x)==2:return [d[0],d[0]]
    def edge(h0,h1,d0,d1):
        m=((2*h0+h1)*d0-h0*d1)/(h0+h1)
        if m*d0<=0:return 0.0
        return math.copysign(min(abs(m),3*abs(d0)),m) if d0*d1<=0 else m
    out=[edge(h[0],h[1],d[0],d[1])]
    for i in range(1,len(x)-1):
        a,b=d[i-1],d[i]
        w1,w2=2*h[i]+h[i-1],h[i]+2*h[i-1]
        out.append((w1+w2)/(w1/a+w2/b) if a*b>0 else 0.0)
    return out+[edge(h[-1],h[-2],d[-1],d[-2])]


def resample(result):
    raw=result['rows']
    if not raw:raise ValueError('没有原始样本')
    times=[r['lap_time_s'] for r in raw]
    if any(not math.isfinite(t) or t<0 for t in times) or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError('原始时间戳必须有限且严格递增')
    if times[-1]>1800:raise ValueError('插值选段不能超过 30 分钟')
    gap=result['quality'].get('frame_gap_limit_s',.25)
    if not math.isfinite(gap) or gap<=0:raise ValueError('无效的帧间隔限制')
    out=[dict(lap_time_s=i/120,throttle=None,brake=None,status='missing') for i in range(math.floor(times[-1]*120)+1)]
    for key in ('throttle','brake'):
        runs=[];run=[]
        for r in raw:
            t,v=r['lap_time_s'],r.get(key)
            valid=v is not None and math.isfinite(v) and 0<=v<=1 and r.get('status')!='hud_missing'
            if run and (not valid or t-run[-1][0]>gap):runs.append(run);run=[]
            if valid:run.append((t,v))
        if run:runs.append(run)
        for run in runs:
            x,y=map(list,zip(*run))
            if len(x)==1:
                i=round(x[0]*120)
                if 0<=i<len(out) and abs(out[i]['lap_time_s']-x[0])<1e-10:out[i][key]=y[0]
                continue
            m=slopes(x,y)
            for i in range(max(0,math.ceil(x[0]*120-1e-9)),min(len(out),math.floor(x[-1]*120+1e-9)+1)):
                t=out[i]['lap_time_s'];j=min(len(x)-2,max(0,bisect.bisect_right(x,t)-1))
                h=x[j+1]-x[j];u=max(0,min(1,(t-x[j])/h))
                v=(2*u**3-3*u*u+1)*y[j]+(u**3-2*u*u+u)*h*m[j]+(-2*u**3+3*u*u)*y[j+1]+(u**3-u*u)*h*m[j+1]
                out[i][key]=max(0,min(1,v))
    for row in out:
        row['status']='interpolated' if row['throttle'] is not None and row['brake'] is not None else 'missing'
    return dict(format='stintrix.video-interpolated',version=1,source='video_hud_interpolation',method='PCHIP',hz=120,
        source_samples=len(raw),frame_gap_limit_s=gap,precision='120 Hz 插值估算；不增加原视频的时间精度；缺口不补齐',rows=out)


def export(folder,result):
    derived=resample(result);folder=Path(folder)
    with (folder/'curve_120hz.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['lap_time_s','throttle','brake','status']);writer.writeheader();writer.writerows(derived['rows'])
    (folder/'curve_120hz.json').write_text(json.dumps(derived,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    from video_report import write_report
    write_report(folder/'report_120hz.html',result,derived)
    return dict(report=str(folder/'report_120hz.html'),csv=str(folder/'curve_120hz.csv'),samples=len(derived['rows']),hz=120)
