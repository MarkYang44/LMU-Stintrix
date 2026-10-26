"""One finalized-report scope: share bounded scratch data, never live telemetry."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from comparison_cache import source

_active=ContextVar('stintrix_report_data',default=None)


class ReportData:
    def __init__(self,folder):self.folder=Path(folder).resolve();self.signature=source(self.folder);self.values={}
    def check(self):
        if source(self.folder)!=self.signature:raise OSError('赛事数据已变化，请重新选择并重试')


def current(folder):
    value=_active.get()
    if value is None or value.folder!=Path(folder).resolve():return None
    value.check();return value


@contextmanager
def batch(folder):
    old=_active.get();folder=Path(folder).resolve()
    if old is not None and old.folder==folder:
        old.check();yield old;return
    value=ReportData(folder);token=_active.set(value)
    try:yield value
    finally:_active.reset(token);value.values.clear()


def scoped(function):
    @wraps(function)
    def run(folder,*args,**kwargs):
        with batch(folder):return function(folder,*args,**kwargs)
    return run
