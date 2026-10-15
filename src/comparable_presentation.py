"""Escaped standalone comparable-condition report; no telemetry upload."""
import html,json
from pathlib import Path
from uuid import uuid4
from i18n import tr
from control_history_chart import lap_time
from analysis_svg import progress
from track_names import display

def content(value):
    esc=lambda x:html.escape(str(x));e=value['entry'];rows=[]
    for s in value['sessions']:
        from analysis_scope import phase
        from race_mode import mode,LABELS
        quality='探索性：条件未知' if s['unknown'] else '样本不足' if not s['qualified'] else '可比样本'
        cells=[s['observed_utc'],tr(LABELS[mode(s)])+' / '+tr(phase(s)),s['count'],lap_time(s['median_s']),lap_time(s['best_s']),f"{s['std_s']:.3f}" if s['std_s'] is not None else tr('未知'),tr(quality),', '.join(s['unknown']) or tr('无')]
        rows.append('<tr>'+''.join('<td>'+esc(x)+'</td>' for x in cells)+'</tr>')
    summary=value['summary'];heading=tr('样本不足，未生成提升结论') if not summary else tr('典型圈速提升')+f" {summary['pace_gain_s']:.3f} s / "+tr('波动减少')+f" {summary['consistency_gain_s']:.3f} s"
    cols=['时间 (UTC)','参赛方式 / 阶段','有效圈数','典型圈速','最快圈','波动 / 秒','样本与条件','条件未知字段']
    return '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+esc(tr('同条件进步分析'))+'</title><style>body{font:16px system-ui;color:#26303a;background:#fafafa;margin:32px auto;max-width:1200px;padding:20px}table{border-collapse:collapse;width:100%;background:white}td,th{border-bottom:1px solid #ddd;text-align:left;padding:12px}p{line-height:1.6}</style><h1>'+esc(tr('同条件进步分析'))+'</h1><h2>'+esc(display(e['track'])+' · '+e['session'].get('vehicle',''))+'</h2><p>'+esc(heading)+'</p><p>'+esc(tr('条件基准是所选纪录圈；统计来自实测有效圈，不进行油量修正或因果推断。'))+'</p><p>'+esc(json.dumps(value['policy'],ensure_ascii=False))+'</p>'+progress(value)+'<table><tr>'+''.join('<th>'+esc(tr(x))+'</th>' for x in cols)+'</tr>'+''.join(rows)+'</table><p>'+esc(tr('未知条件与样本不足的赛事仍可查看，但不计入可靠的长期变化结论。'))+'</p><p>'+esc(json.dumps(value['excluded'],ensure_ascii=False))+'</p>'

def save(root,value):
    folder=Path(root)/'PersonalRecords/ComparableReports';folder.mkdir(parents=True,exist_ok=True);path=folder/('comparable-'+uuid4().hex+'.html');path.write_text(content(value),encoding='utf-8');return str(path)
