"""Small standalone SVGs from observed data; no plotting dependencies."""
import html
from datetime import datetime
from i18n import tr

def trajectory(report):
    g=report.get('geometry',[]);zones=report['priorities'];esc=lambda x:html.escape(str(x));parts=[]
    if len(g)>1 and (max(p[1] for p in g)-min(p[1] for p in g)>=1 or max(p[2] for p in g)-min(p[2] for p in g)>=1):
        xs=[p[1] for p in g];ys=[p[2] for p in g];scale=min(900/max(1,max(xs)-min(xs)),280/max(1,max(ys)-min(ys)));cx=(max(xs)+min(xs))/2;cy=(max(ys)+min(ys))/2
        points=[(500+(x-cx)*scale,185-(y-cy)*scale,d) for d,x,y in g]
        for a,b in zip(points,points[1:]):
            d=(a[2]+b[2])/2;zone=next((z for z in zones if z['start']<=d<z['end']),None);color='#778020' if zone is zones[0] else '#8490a0'
            for key,c in (('abs','#c5ac16'),('tc','#2670c9')):
                if any(lo<=d<=hi for lo,hi,_ in report.get('reference_features',{}).get('intervals',{}).get(key,[])):color=c
            parts.append(f'<path d="M{a[0]:.2f},{a[1]:.2f} L{b[0]:.2f},{b[1]:.2f}" fill="none" stroke="{color}" stroke-width="3"><title>{esc(zone["name"] if zone else "")} · {d:.0f} m</title></path>')
        label=tr('实测轨迹 · 高亮为分析区间 · 黄 ABS / 蓝 TC（参考圈）')
    else:
        length=max((z['end'] for z in zones),default=1);label=tr('距离分段视图：没有坐标，未绘制赛道形状')
        for z in zones:
            a=35+930*z['start']/length;b=35+930*z['end']/length
            parts.append(f'<rect x="{a:.1f}" y="115" width="{max(0,b-a-2):.1f}" height="100" fill="#dfe5cb"><title>{esc(z["name"])} · {z["start"]:.0f}–{z["end"]:.0f} m</title></rect><text x="{a:.1f}" y="240" font-size="12">{z["start"]:.0f} m</text>')
    return '<svg role="img" aria-label="'+esc(label)+'" viewBox="0 0 1000 360" style="width:100%;max-height:360px;background:white"><title>'+esc(label)+'</title><text x="20" y="30" font-size="17">'+esc(label)+'</text>'+''.join(parts)+'</svg>'

def progress(value):
    ss=value['sessions'];esc=lambda x:html.escape(str(x))
    if not ss:return '<p>'+esc(tr('样本不足，未生成提升结论'))+'</p>'
    times=[datetime.fromisoformat(s['observed_utc'].replace('Z','+00:00')).timestamp() for s in ss];values=[s[k] for s in ss for k in ('median_s','best_s')];lo=min(values);hi=max(values);pad=max(.1,(hi-lo)*.1);lo-=pad;hi+=pad
    parts=['<text x="20" y="25" font-size="16">'+esc(tr('典型圈速'))+' / '+esc(tr('最快圈'))+'</text>']
    for i in range(4):
        y=55+i/3*235;v=hi-i/3*(hi-lo);label=f'{int(v//60)}:{v%60:06.3f}'
        parts.append(f'<path d="M95 {y:.1f} H965" stroke="#e0e5ea"/><text x="8" y="{y+5:.1f}" font-size="13">{label}</text>')
    for k,color in (('median_s','#6b7927'),('best_s','#2670c9')):
        points=[]
        for s,t in zip(ss,times):
            x=530 if times[0]==times[-1] else 95+870*(t-times[0])/(times[-1]-times[0]);y=290-235*(s[k]-lo)/(hi-lo);points.append(f'{x:.1f},{y:.1f}')
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" opacity="{1 if s["qualified"] else .5}"><title>{esc(s["observed_utc"])} · {s[k]:.3f} s · n={s["count"]}</title></circle>')
        if len(points)>1:parts.append('<polyline points="'+' '.join(points)+'" stroke="'+color+'" fill="none" stroke-width="2"/>')
    parts.append('<text x="95" y="326" font-size="13">'+esc(ss[0]['observed_utc'][:10])+'</text><text x="965" y="326" text-anchor="end" font-size="13">'+esc(ss[-1]['observed_utc'][:10])+'</text>')
    return '<svg role="img" viewBox="0 0 1000 350" style="width:100%;background:white"><title>'+esc(tr('同条件进步分析'))+'</title>'+''.join(parts)+'</svg>'
