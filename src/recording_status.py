"""UI snapshot only: no disk reads, locks over CSV, or sampling-rate work."""
import time

def report_snapshot(report):
    labels={'queued':'记录已保存 · 等待生成报告','building':'记录已保存 · 正在生成报告','deferred':'记录已保存 · 报告等待可用内存','ready':'记录与报告已保存','error':'记录已保存 · 报告生成失败','partial':'记录已保存 · 部分分析或图片未生成'}
    labels['incomplete']='记录已保存 · 报告尚未完成'
    if report not in labels:return None
    return dict(state='error' if report in ('error','partial','incomplete') else 'building' if report in ('queued','building','deferred') else 'saved',text=labels[report],gaps=None)

def snapshot(engine,now=None):
    now=time.monotonic() if now is None else now;r=engine.recorder
    failure=getattr(engine,'recording_failure',None)
    if failure:return dict(state='error',text='保存失败 · '+str(failure),gaps=r.meta.get('telemetry_gap_count'))
    if r.file is not None:
        last=getattr(engine,'last_fresh_at',None);waiting=last is None or now-last>3
        return dict(state='waiting' if waiting else 'recording',text='等待数据恢复 · 保留同场记录' if waiting else '正在记录',gaps=r.meta.get('telemetry_gap_count'))
    report=getattr(r,'report_state','idle')
    folder=getattr(r,'report_folder',None)
    if folder:
        from report_state import latest
        value=latest(folder)
        if value:report=value['state']
    saved=report_snapshot(report)
    if saved:return saved
    return dict(state='live' if getattr(engine,'latest',None) else 'idle',text='实时显示 · 当前阶段不录制' if getattr(engine,'latest',None) else '等待游戏数据',gaps=None)
