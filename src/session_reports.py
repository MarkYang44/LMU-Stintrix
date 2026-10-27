"""Session analysis and report orchestration, independent of the HUD."""
import endurance
import reporting
from app_config import ROOT
from laps import export_fastest, library_laps, track_script, write_compare
from paths import ASSETS
from sessionlab import analyze_session
from processing_context import scoped


@reporting.serialized
@scoped
def make_report(folder,isolated=None):
    # Portable builds isolate large Python/native heaps; source callers can opt in.
    import sys
    from pathlib import Path
    folder=Path(folder)
    from race_model import read_json
    use_worker=getattr(sys,'frozen',False) if isolated is None else isolated
    if use_worker:
        from report_worker import run
        return run(folder,ROOT)
    from runtime_activity import busy
    if busy():
        from report_worker import ReportDeferred
        raise ReportDeferred('HUD 记录运行中，报告与压缩等待停止记录；原始采样已保存')
    from simulator_profiles import profile
    from report_pipeline import execute
    meta=read_json(folder/'session.json',{});game=profile(meta.get('simulator_id','lmu'))
    return execute(folder,game.reports,lambda steps:game.reports.build(folder,meta,steps))


def operations(folder,steps):
    """LMU data semantics, separate from task lifecycle and receipt handling."""
    from race_model import read_json
    fastest=read_json(folder/'fastest_lap_summary.json',None) if steps['fastest'].get('state')=='ready' else None
    def export():
        nonlocal fastest
        library=folder.parent
        _,fastest=export_fastest(folder,ASSETS/'compare.html',library)
        if library in (ROOT/'Logs',ROOT/'DemoLogs',ROOT/'ImportedLogs'):
            selection=library_laps(library)
            write_compare(ROOT/('DemoFastestLapCompare.html' if library.name=='DemoLogs' else 'FastestLapCompare.html'),ASSETS/'compare.html',selection)
    def images():
        from race_report import generate
        return generate(folder)
    def compress():
        from session_compression import after_report
        return after_report(folder)
    return dict(analysis=lambda:analyze_session(folder),endurance=lambda:endurance.analyze(folder),
        fastest=export,review=lambda:render_review(folder,fastest),images=images,compression=compress)

def render_review(folder, fastest=None):
    """Upgrade a review page without rewriting its CSV or lap exports."""
    from race_model import read_json
    from pathlib import Path
    if read_json(Path(folder)/'session.json',{}).get('simulator_id')=='ac_evo':
        from evo_reports import overview
        return overview(Path(folder),read_json(Path(folder)/'session.json',{}))
    reporting.render_review(folder,ASSETS,track_script(ASSETS),fastest,local=True)
