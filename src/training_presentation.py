"""Readable, escaped offline training report; generated only under private data."""
import html
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from i18n import tr
from track_names import display,layout
from record_presentation import number


def content(report):
    e=report['entry'];r=report['reference'];p=report['priorities'];esc=lambda v:html.escape(str(v))
    def fmt(value,unit=' s'):return number(value,unit,3 if unit==' s' else 1)
    rows=[]
    for i,z in enumerate(p):
        d=z['differences'];kind='反复损失' if z['slower_fraction']>=.75 and z['median_loss_s']>.02 else '波动优先' if z['std_s']>.1 else '巩固节奏'
        rows.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (i+1,z['name'] if z.get('source')=='user_distance' else tr(z['name'].split()[0])+' '+z['name'].split()[-1],f"{z['start']:.0f}–{z['end']:.0f} m",tr(kind),fmt(z['median_loss_s']),fmt(z['std_s']),str(z['count']),fmt(d['brake_m'],' m'),fmt(d['minimum_kmh'],' km/h'),fmt(d['full_m'],' m'),fmt(d.get('coast_s')),fmt(d.get('abs_s')),fmt(d.get('tc_s'))))+'</tr>')
    columns=('优先级','分析区间','距离','训练方向','典型时间差','波动','样本圈数','制动点差','最低速度差','全油门恢复差','滑行时间差','ABS 触发时间差','TC 触发时间差')
    def para(value):return '<p>'+esc(value)+'</p>'
    body='<h1>'+esc(tr('训练优先级报告'))+'</h1><h2>'+esc(display(e['track']))+'</h2>'
    body+=para(layout(e['track'],e['layout'],e['length_m'])+' · '+str(e['session'].get('vehicle','')))
    body+=para(tr('实际参考圈')+f" · {int(r['time_s']//60)}:{r['time_s']%60:06.3f} · "+tr('第 ')+str(r['number'])+tr(' 圈')+' · '+str(r['session'].get('started_utc','')))
    body+=para(tr('可用圈数')+f" {report['count']} / "+tr('无效或不完整排除')+f" {report['excluded']} / "+tr('条件差异排除')+f" {report['condition_excluded']}")
    body+=para(tr('条件未知字段')+': '+(', '.join(report['unknown']) or tr('无')))
    from analysis_svg import trajectory
    body+=trajectory(report)
    body+='<table><thead><tr>'+''.join('<th>'+esc(tr(v))+'</th>' for v in columns)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table>'
    for line in (
        '优先级 = 正的典型时间差 + 0.25 × 时间差标准差；这是训练排序，不是保证能提升的秒数。',
        '区间来自参考圈制动输入；没有明显制动时使用等距离区间，不代表官方弯号。',
        '时间差与速度差：正值表示比参考圈耗时更长、速度更高；距离差：正值表示更晚制动或更晚恢复全油门。',
        '条件匹配：圈起点油量 ±2 L、赛道与气温 ±5 °C、湿度 ±0.1、降雨 ±0.05，胎种、抓地状态及 TC/ABS 一致；缺失字段仅标注未知，不证明条件相同。',
        '先练反复损失区间，再练波动大的区间；一次只调整一个输入，重新录制有效圈验证。',
        '仅描述输入与时间差，无法确定车辆设定、路况或驾驶动作的因果关系。'):
        body+=para(tr(line))
    body+=para(tr('滑行定义为油门与刹车均低于 3%；ABS/TC 缺失显示未知，触发时间为区间统计，不说明动作的因果关系。'))
    body+=para(tr('自定义区间为用户距离定义；名称不代表官方弯号。'))
    if report['errors']:body+=para(tr('未读取记录')+': '+'; '.join(report['errors']))
    return '<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+esc(tr('训练优先级报告'))+'</title><style>body{font:16px system-ui;margin:40px auto;padding:0 24px;max-width:1400px;background:#fafafa;color:#192333}h1{font-size:36px}p{line-height:1.65;color:#526070}table{border-collapse:collapse;width:100%;background:white}th,td{padding:14px 10px;text-align:left;border-bottom:1px solid #e3e7ec}th{background:#eaf0f8}tbody tr:first-child{background:#f0f6df}</style>'+body+'</html>'


def save(root,report):
    folder=Path(root)/'PersonalRecords/TrainingReports';folder.mkdir(parents=True,exist_ok=True)
    path=folder/('training-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:8]+'.html')
    path.write_text(content(report),encoding='utf-8');return str(path)
