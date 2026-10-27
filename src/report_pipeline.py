"""One receipt/retry loop; game adapters supply operations and prerequisites."""
from pathlib import Path


def execute(folder,policy,build_operations):
    from report_state import plan,save,begin_step,ERRORS,invalidate
    from report_worker import ReportDeferred
    folder=Path(folder);steps=plan(folder);dependencies=dict(policy.dependencies)
    invalidate(steps,dependencies)
    operations=build_operations(steps)
    for name in policy.steps:
        if steps[name].get('state')=='ready':continue
        blocked=[d for d in dependencies.get(name,()) if steps[d].get('state')!='ready']
        if blocked:
            steps[name].update(state='blocked',waiting_for=blocked);save(folder,steps);continue
        begin_step(folder,name,steps)
        try:operations[name]()
        except ReportDeferred as error:
            steps[name].update(state='deferred',error=str(error));save(folder,steps,reason=error);raise
        except Exception as error:
            steps[name].update(state='error',error=str(error))
            if policy.error_markers and name in ERRORS:(folder/ERRORS[name]).write_text(str(error),encoding='utf-8')
        else:steps[name].update(state='ready');steps[name].pop('error',None)
        save(folder,steps)
    if policy.cache_budget:
        from cache_budget import enforce
        enforce(folder.parent.parent)
    return save(folder,steps)
