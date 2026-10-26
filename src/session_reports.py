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
    use_worker=getattr(sys,'frozen',False) if isolated is None else isolated
    if use_worker:
        from report_worker import run
        return run(folder,ROOT)
    from report_state import plan,save,begin_step,ERRORS,DEPENDENCIES,invalidate
    from report_worker import ReportDeferred
    steps=plan(folder)
    invalidate(steps)
    from race_model import read_json
    fastest=read_json(folder/'fastest_lap_summary.json',None) if steps['fastest'].get('state')=='ready' else None
    for name in steps:
        if steps[name].get('state')=='ready':continue
        blocked=[d for d in DEPENDENCIES.get(name,()) if steps[d].get('state')!='ready']
        if blocked:
            steps[name].update(state='blocked',waiting_for=blocked);save(folder,steps);continue
        begin_step(folder,name,steps)
        try:
            if name=='analysis':analyze_session(folder)
            elif name=='endurance':endurance.analyze(folder)
            elif name=='fastest':
                library=folder.parent
                _,fastest=export_fastest(folder,ASSETS/'compare.html',library)
                if library in (ROOT/'Logs',ROOT/'DemoLogs',ROOT/'ImportedLogs'):
                    selection=library_laps(library)
                    write_compare(ROOT/('DemoFastestLapCompare.html' if library.name=='DemoLogs' else 'FastestLapCompare.html'),ASSETS/'compare.html',selection)
            elif name=='review':render_review(folder,fastest)
            elif name=='images':
                from race_report import generate
                generate(folder)
            elif name=='compression':
                from session_compression import after_report
                after_report(folder)
        except ReportDeferred as error:
            steps[name].update(state='deferred',error=str(error));save(folder,steps,reason=error);raise
        except Exception as error:
            steps[name].update(state='error',error=str(error))
            if name in ERRORS:(folder/ERRORS[name]).write_text(str(error),encoding='utf-8')
        else:steps[name].update(state='ready');steps[name].pop('error',None)
        save(folder,steps)
    from cache_budget import enforce
    enforce(folder.parent.parent)
    return save(folder,steps)



def render_review(folder, fastest=None):
    """Upgrade a review page without rewriting its CSV or lap exports."""
    reporting.render_review(folder,ASSETS,track_script(ASSETS),fastest,local=True)
