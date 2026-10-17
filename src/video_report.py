"""Standalone, local interactive report. Video estimates remain visibly marked."""
import html
import json
from pathlib import Path

STYLE='''
:root{font:16px "Segoe UI",system-ui,sans-serif;color:#172236;background:#f4f6f9}
body{max-width:1240px;margin:50px auto;padding:0 24px}h1{font-size:34px;letter-spacing:-1px;margin:0 0 12px}
h2{font-size:20px}p{line-height:1.7;color:#536176}section{background:white;border-radius:20px;padding:24px;margin:20px 0;border:1px solid #e1e6ed}
.badge{font-size:13px;color:#976000;background:#fff4d8;padding:7px 12px;border-radius:9px;display:inline-block}
button,input{font:inherit;border:1px solid #ccd4df;border-radius:9px;padding:8px 12px;background:white;color:#172236}
button{cursor:pointer;margin-right:8px}canvas{width:100%;height:290px;display:block;margin-top:20px}#tip{min-height:24px;color:#536176;font-variant-numeric:tabular-nums}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{border-bottom:1px solid #e1e6ed;padding:12px;text-align:left}pre{white-space:pre-wrap;line-height:1.6;font-size:13px}
.tools{display:flex;gap:10px;flex-wrap:wrap;align-items:center}input{width:90px}small{color:#536176}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:18px 0}.metric{background:#f4f6f9;padding:15px;border-radius:12px}.metric span{display:block;font-size:13px;color:#536176;margin-bottom:8px}.metric strong{font-size:23px}summary{cursor:pointer;color:#536176}details{margin-top:16px}details pre{max-height:320px;overflow:auto}
'''

SCRIPT=r'''
const report=JSON.parse(document.getElementById('payload').textContent),
comparison=['stintrix.video-comparison','stintrix.video-history-comparison'].includes(report.format),history=report.format==='stintrix.video-history-comparison', rows=comparison?report.curves[0]:report.rows,
other=comparison?report.curves[1]:[],canvas=document.getElementById('pedals'),tip=document.getElementById('tip');
let axis='lap_time_s',lo=0,hi=rows.at(-1)?.lap_time_s||1;
function points(key,data=rows){return data.map(r=>[r[axis],r[key]]);}
function draw(){
 const ctx=canvas.getContext('2d'),w=canvas.clientWidth,h=290,d=devicePixelRatio||1;canvas.width=w*d;canvas.height=h*d;ctx.scale(d,d);
 ctx.clearRect(0,0,w,h);ctx.font='12px Segoe UI';ctx.lineWidth=1;
 const x=v=>50+(v-lo)/(hi-lo)*(w-70),y=v=>240-v*190;
 for(let i=0;i<=4;i++){let v=i/4;ctx.strokeStyle='#e3e8ef';ctx.beginPath();ctx.moveTo(50,y(v));ctx.lineTo(w-20,y(v));ctx.stroke();ctx.fillStyle='#536176';ctx.fillText(Math.round(v*100)+'%',6,y(v)+4);ctx.fillText((lo+(hi-lo)*v).toFixed(axis==='distance_m'?0:1),x(lo+(hi-lo)*v)-10,270);}
 const lines=[['throttle','#00a87a',rows,false],['brake','#ed3559',rows,false],['native_throttle','#2779c7',rows,true],['native_brake','#8f64c9',rows,true],['throttle',history?'#2779c7':'#00a87a',other,true],['brake',history?'#8f64c9':'#ed3559',other,true]];
 for(const [key,color,data,dash] of lines){ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.setLineDash(dash?[5,4]:[]);ctx.beginPath();let active=false,previous=null;
  for(const r of data){const t=r[axis],v=r[key];if(t==null||v==null||t<lo||t>hi||previous!=null&&r.lap_time_s-previous>Math.max(.3,report.frameGap||.3)){active=false;previous=r.lap_time_s;if(t==null||v==null||t<lo||t>hi)continue;}if(active)ctx.lineTo(x(t),y(v));else ctx.moveTo(x(t),y(v));active=true;previous=r.lap_time_s;}ctx.stroke();}
 ctx.setLineDash([]);ctx.fillStyle='#536176';ctx.fillText(axis==='distance_m'?'赛道进度 / m':'圈内时间 / s',w-150,287);
}
function reset(){lo=0;hi=1;for(const data of [rows,other])for(const r of data)if(r[axis]!=null)hi=Math.max(hi,r[axis]);document.getElementById('from').value=lo;document.getElementById('to').value=hi.toFixed(2);draw();}
document.getElementById('time').onclick=()=>{axis='lap_time_s';reset();};
document.getElementById('distance').onclick=()=>{axis='distance_m';reset();};
document.getElementById('zoom').onclick=()=>{const a=+document.getElementById('from').value,b=+document.getElementById('to').value;if(Number.isFinite(a)&&Number.isFinite(b)&&b>a){lo=a;hi=b;draw();}};
document.getElementById('reset').onclick=reset;
if(!report.distanceReady)document.getElementById('distance').disabled=true;
canvas.onmousemove=e=>{const t=lo+Math.max(0,Math.min(1,(e.offsetX-50)/(canvas.clientWidth-70)))*(hi-lo);
 const read=(data,label)=>{let nearest=null,first=null,last=null;for(const row of data){if(row[axis]==null)continue;first??=row[axis];last=row[axis];if(!nearest||Math.abs(row[axis]-t)<Math.abs(nearest[axis]-t))nearest=row;}
  if(!nearest||t<first||t>last||Math.abs(nearest[axis]-t)>(axis==='distance_m'?30:.3))return label+'：无样本';
  const fmt=v=>v==null?'缺失':(v*100).toFixed(1)+'%';return `${label} 油门 ${fmt(nearest.throttle)} · 刹车 ${fmt(nearest.brake)}`;};
 tip.textContent=`${axis==='distance_m'?'距离':'圈内时间'} ${t.toFixed(3)} ${axis==='distance_m'?'m':'s'} · ${read(rows,comparison?'A':'视频')}`+(comparison?' | '+read(other,history?'B 历史':'B'):'');
};
new ResizeObserver(draw).observe(canvas);reset();
const delta=document.getElementById('delta');
if(delta&&report.delta.length){const ctx=delta.getContext('2d'),w=1200,h=260;delta.width=w;delta.height=h;
 const valid=report.delta.filter(r=>r[1]!=null),max=Math.max(.1,...valid.map(r=>Math.abs(r[1]))),length=report.identity.length_m;
 ctx.font='16px Segoe UI';ctx.fillStyle='#536176';ctx.fillText('Δ / s  (B − A)   ±'+max.toFixed(3),20,22);ctx.strokeStyle='#ccd4df';ctx.beginPath();ctx.moveTo(20,130);ctx.lineTo(1180,130);ctx.stroke();
 ctx.strokeStyle='#7357c7';ctx.beginPath();let active=false;for(const [d,v] of report.delta){if(v==null){active=false;continue;}const x=20+d/length*1160,y=130-v/max*100;active?ctx.lineTo(x,y):ctx.moveTo(x,y);active=true;}ctx.stroke();}
'''


def sampled(rows, limit=12000):
    # Preserve gaps and pedal extrema when reducing dense display traces.
    if len(rows)<=limit:return rows
    step=max(1,(len(rows)+limit//5-1)//(limit//5));out=[]
    for i in range(0,len(rows),step):
        chunk=rows[i:i+step];indices={0,len(chunk)-1}
        for key in ('throttle','brake'):
            indices.add(max(range(len(chunk)),key=lambda j:chunk[j].get(key) or 0))
        missing=next((j for j,r in enumerate(chunk) if r.get('status')!='estimated'),None)
        if missing is not None:indices.add(missing)
        out.extend(chunk[j] for j in sorted(indices))
    return out


def page(path,title,payload,body):
    safe=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('&','\\u0026')
    content='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    content+='<title>'+html.escape(title)+'</title><style>'+STYLE+'</style><body><span class="badge">VIDEO HUD · 估算数据</span><h1>'+html.escape(title)+'</h1>'
    content+='<p>绿色：油门 · 红色：刹车。缺口留空，识别分数只表示圆弧形态一致性。视频数据不会计入最快圈、领奖台或训练报告。</p>'+body
    content+='''<section><h2>油门 / 刹车</h2><div class="tools"><button id="time">时间轴</button><button id="distance">距离轴</button><input id="from" aria-label="范围起点"><input id="to" aria-label="范围终点"><button id="zoom">查看范围</button><button id="reset">完整一圈</button></div><canvas id="pedals" aria-label="油刹曲线"></canvas><div id="tip">移动鼠标查看样本</div></section>'''
    content+='<script type="application/json" id="payload">'+safe+'</script><script>'+SCRIPT+'</script></body></html>'
    Path(path).write_text(content,encoding='utf-8')


def write_report(path,result):
    from track_names import display,layout_label
    quality=result['quality'];identity=result['identity']
    title=display(identity['track'])+' / '+layout_label(identity['track'],identity['track_layout'])
    warning='' if quality['pedal_readable_ratio']>=.9 else '<p class="badge">HUD 可读覆盖不足 90%，请重新检查标定 / 遮挡；当前结果不宜用于驾驶结论。</p>'
    mode={'time':'普通 POV · 时间轴','distance_hud':'距离与计时 HUD · OCR','telemetry':'同圈遥测 · 同步校准'}[result['mode']]
    metrics=[('HUD 可读覆盖',f"{quality['pedal_readable_ratio']:.1%}"),('缺失样本',str(quality.get('missing_samples',0))),
             ('最大帧间隔',f"{quality['max_frame_gap_s']*1000:.0f} ms"),('距离对齐','可用 · 估算' if quality.get('distance_usable') else '仅时间轴')]
    body='<section><h2>输入与质量</h2>'+warning+'<p>'+html.escape(result['video_file'])+' · '+mode+' · '+str(round(result['end_s']-result['start_s'],3))+' s</p><div class="metrics">'
    body+=''.join('<div class="metric"><span>'+k+'</span><strong>'+v+'</strong></div>' for k,v in metrics)+'</div>'
    if quality.get('pedal_mae'):
        values=quality['pedal_mae'];fmt=lambda v:'缺失' if v is None else f'{v*100:.2f} 个百分点'
        body+='<p>对照过滤后遥测：油门平均绝对差 '+fmt(values['throttle'])+'，刹车 '+fmt(values['brake'])+'。蓝 / 紫虚线为遥测油门 / 刹车；HUD 显示延迟会影响差异。</p>'
    if quality.get('distance_reason'):body+='<p class="badge">'+html.escape(quality['distance_reason'])+'</p>'
    body+='<p>距离 OCR 和手动同步均未保证绝对误差。时间差受视频帧间隔、HUD 延迟、量化与同步点误差影响。两点同步无法独立验证时钟漂移；建议至少三个可核对事件。</p>'
    body+='<details><summary>识别与同步详情</summary><pre>'+html.escape(json.dumps(quality,ensure_ascii=False,indent=2))+'</pre></details></section>'
    if result.get('landmarks'):
        body+='<details><summary>固定地标（视频秒数）</summary><table>'+''.join('<tr><td>'+html.escape(m['name'])+'</td><td>'+str(m['video_s'])+'</td></tr>' for m in result['landmarks'])+'</table></details>'
    payload=dict(result,rows=sampled(result['rows']),distanceReady=quality.get('distance_usable'),frameGap=quality.get('frame_gap_limit_s',.25))
    page(path,title,payload,body)


def write_comparison(path,result,a,b):
    body='<section><h2>两圈对比</h2><p>'+html.escape(result['note'])+' 实线 A / 虚线 B；距离差值与地标分段均为估算。</p>'
    body+='<table><tr><th>地标分段</th><th>A / s</th><th>B / s</th><th>Δ / s</th></tr>'
    for s in result['segments']:body+='<tr><td>'+html.escape(s['name'])+'</td>'+''.join(f'<td>{s[k]:.3f}</td>' for k in ('a_s','b_s','delta_s'))+'</tr>'
    body+='</table></section>'
    if result['delta']:body+='<section><h2>相同赛道进度的累计时间差</h2><canvas id="delta"></canvas><p>缺口超过允许值时不插值；负值表示 B 更快。这里不是逐弯精确增益测量。</p></section>'
    page(path,'视频单圈对比',dict(result,curves=[sampled(a['rows']),sampled(b['rows'])],distanceReady=bool(result['delta'])),body)


def write_history_comparison(path,result,video,reference):
    from track_names import display,layout_label
    meta=result['reference'];ident=result['identity'];esc=html.escape
    channel='游戏过滤后输入' if meta['channel']=='filtered' else '原始输入'
    body='<section><h2>视频 A / 历史单圈 B</h2><p>'+esc(result['note'])+'</p>'
    body+='<p><strong>实线绿 / 红：视频油门 / 刹车；虚线蓝 / 紫：历史油门 / 刹车。</strong></p>'
    body+='<p>视频：'+esc(video['video_file'])+'<br>历史：'+esc(str(meta['date'])[:19])+' · '+esc(meta['vehicle'])+' · 第 '+str(meta['number'])+' 圈 · '+channel+'</p>'
    metrics=[('A 视频圈时',f"{result['video_duration_s']:.3f} s"),('B 历史圈时',f"{result['reference_duration_s']:.3f} s"),
        ('整圈 Δ（B − A）',f"{result['reference_duration_s']-result['video_duration_s']:+.3f} s"),('对齐方式','距离进度 · 估算' if result['delta'] else '圈起点 / 时间轴')]
    body+='<div class="metrics">'+''.join('<div class="metric"><span>'+k+'</span><strong>'+v+'</strong></div>' for k,v in metrics)+'</div>'
    body+='<p>时间轴叠加保留各自真实圈时，不拉伸、不用平均速度换算距离；同一时刻的油刹差异不等于同一弯道的操作差异。车辆、天气、油量、轮胎及输入通道可能不同。</p>'
    if result['layout_bound']:
        old=result['video_identity']
        body+='<p class="badge">已由用户确认关联历史布局；仅用于本次时间轴对比。视频原标注：'+esc(str(old['track_layout']))+' / '+str(old['length_m'])+' m；历史布局：'+esc(str(ident['track_layout']))+' / '+str(ident['length_m'])+' m。原始提取结果未改写。</p>'
    q=video['quality'];body+=f"<p>视频可读覆盖 {q['pedal_readable_ratio']:.1%}，缺失 {q.get('missing_samples',0)} 点；该比例不是准确率。视频估算未成为已验证历史圈。</p></section>"
    if result['segments']:
        body+='<section><h2>同名固定地标分段</h2><table><tr><th>分段</th><th>A / s</th><th>B / s</th><th>Δ / s</th></tr>'
        for s in result['segments']:body+='<tr><td>'+esc(s['name'])+'</td>'+''.join(f'<td>{s[k]:.3f}</td>' for k in ('a_s','b_s','delta_s'))+'</tr>'
        body+='</table><p>必须使用相同物理位置及过线判据；结果受人工标记误差影响。</p></section>'
    if result['delta']:body+='<section><h2>相同距离的累计时间差</h2><canvas id="delta"></canvas><p>缺失位置留空，Δ = B − A；未经精确误差认证。</p></section>'
    # Remove the same-lap verification overlay from A: B is the explicitly selected comparison lap.
    clean=[{k:v for k,v in row.items() if k not in ('native_throttle','native_brake')} for row in sampled(video['rows'])]
    circuit=display(ident['track']);layout=layout_label(ident['track'],ident['track_layout'])
    title=circuit+(' / '+layout if layout!=circuit else '')+' · 视频与历史圈'
    page(path,title,
        dict(result,curves=[clean,sampled(reference['rows'])],distanceReady=bool(result['delta'])),body)
