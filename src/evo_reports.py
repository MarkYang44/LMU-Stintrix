"""EVO phase-one record overview and the shared lossless compression pipeline."""
from html import escape
import json
from pathlib import Path
import os,tempfile


def make_report(folder):
    """Compatibility entrypoint; both games use the shared executor."""
    folder=Path(folder);meta=json.loads((folder/'session.json').read_text('utf-8-sig'))
    if meta.get('simulator_id')!='ac_evo' or meta.get('status')=='recording':raise ValueError('Not a completed EVO record')
    from session_reports import make_report as generate
    return generate(folder,isolated=False)


def operations(folder,meta):
    """EVO input/clock semantics remain independent of LMU lap analysis."""
    from session_compression import after_report
    if meta.get('simulator_id')!='ac_evo' or meta.get('status')=='recording':raise ValueError('Not a completed EVO record')
    def fastest():
        from evo_laps import export
        return export(folder)
    def images():
        from race_report import generate
        return generate(folder)
    return dict(fastest=fastest,review=lambda:overview(folder,meta),images=images,compression=lambda:after_report(folder))


def overview(folder,meta):
    rows=[('Simulator / 模拟器','Assetto Corsa EVO'),('Track / 赛道',meta.get('track','')),
        ('Layout / 布局',meta.get('track_layout','')),('Car / 车辆',meta.get('vehicle','')),
        ('Driver / 车手',meta.get('driver','')),('Started UTC / 开始时间',meta.get('started_utc','')),
        ('Samples / 输入采样',meta.get('samples',0)),('Capture seconds / 采集时长',meta.get('duration_s',0)),
        ('Mode / 参赛方式',meta.get('race_mode','unknown'))]
    table=''.join('<tr><th>'+escape(k)+'</th><td>'+escape(str(v))+'</td></tr>' for k,v in rows)
    from evo_laps import index
    from race_model import lap_time,lap_status
    value=index(folder)
    lap_rows=''.join('<tr><td>'+str(lap['num'])+'</td><td>'+lap_time(lap['time'])+'</td><td>'+escape(lap_status(lap))+'</td></tr>' for lap in value['laps'])
    links='<p><a href="圈速单.png">圈速单 / Lap sheet</a> · <a href="比赛日志.png">赛事日志 / Session log</a>'
    if value['fastest']:links+=' · <a href="fastest_lap.html">完整圈曲线 / Lap inputs</a>'
    links+='</p>'
    document='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>STINTRIX · AC EVO</title><style>body{background:#191919;color:#eee;font:16px system-ui;margin:0;padding:5vw}main{max-width:960px;margin:auto}small{color:#d0d447}h1{font-size:38px}section{background:#262626;border:1px solid #414141;border-top:2px solid #d0d447;padding:24px;clip-path:polygon(12px 0,100% 0,100% calc(100% - 12px),calc(100% - 12px) 100%,0 100%,0 12px)}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #3a3a3a;overflow-wrap:anywhere}th{color:#aaa;width:42%}p{color:#bbb;line-height:1.7}</style>
<main><small>STINTRIX / AC EVO / LOCAL &amp; PRIVATE</small><h1>赛事记录概览 · Session record</h1><section><table>'''+table+'''</table>'''+links+'''<table><tr><th>LAP</th><th>TIME</th><th>状态 / Status</th></tr>'''+lap_rows+'''</table>
<p>已保存物理输入和仪表输入，两者更新频率不同；不表示 LMU 的原始／过滤后通道。时间轴使用本机单调采集时钟，不冒充游戏计时。完整原值可在控制中心导出 CSV 或赛事包。</p>
<p>圈速使用游戏毫秒计时；只将连续、完整、有效且未进站的圈计入个人纪录。旧记录缺少完圈计时证据时保留为部分记录，不补造圈速。名次仅为观测值，不表示官方完赛结果。分段、碰撞和车辆分析尚不可用。</p></section></main></html>'''
    fd,path=tempfile.mkstemp(prefix='.evo-review-',suffix='.pending',dir=folder)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='') as out:out.write(document)
        os.replace(path,folder/'review.html')
    finally:
        if os.path.exists(path):os.unlink(path)
