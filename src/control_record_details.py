"""One current and one latest detail read; small snapshots stay private in memory."""
import json
from collections import OrderedDict
from functools import partial
from pathlib import Path

FILES=('session.json','race_summary.json','fastest_lap_summary.json','inputs.csv','inputs.csv.gz','inputs.csv.stc','vehicle.csv','vehicle.csv.gz','vehicle.csv.stc','race_events.csv','race_events.csv.gz','race_events.csv.stc')


def key(entry):
    folder=Path(entry['folder']).resolve();stamps=[]
    for name in FILES:
        file=folder/name
        try:s=file.stat();stamps.append((name,s.st_size,s.st_mtime_ns))
        except FileNotFoundError:pass
    facts=dict(summary=entry.get('summary'),duration=entry.get('session',{}).get('duration_s'),fastest=entry.get('fastest_s'),xml=entry.get('official_result') if entry.get('xml_only') else None)
    return str(folder),tuple(stamps),json.dumps(facts,sort_keys=True,default=str)


class DetailLoader:
    def __init__(self,app,identity=key):
        self.app=app;self.identity=identity;self.page=None;self.backend=None;self.running=None;self.pending=None;self.desired=None;self.failures=OrderedDict();self.cache=OrderedDict()
    def attach(self,page,backend):self.page=page;self.backend=backend;self.desired=None;self.pending=None;page.details=self
    def detach(self,page):
        if self.page is page:self.page=None;self.desired=None;self.pending=None
    def alive(self):return self.page is not None and self.page.alive()
    def select(self,entry,force=False):
        if not self.alive():return
        if entry is None:self.desired=None;self.pending=None;self.page.feedback.busy('detail',False);return
        try:identity=self.identity(entry)
        except OSError as error:
            self.desired=None;self.pending=None;self.page.feedback.busy('detail',False);self.page.apply_detail(None,str(error) or '未提供错误详情');return
        self.desired=identity
        if force:self.cache.pop(identity,None);self.failures.pop(identity,None)
        if identity in self.cache:
            self.pending=None;self.cache.move_to_end(identity);self.page.feedback.busy('detail',False);self.page.apply_detail(self.cache[identity],None);return
        if identity in self.failures and not force:
            self.pending=None;self.failures.move_to_end(identity);self.page.feedback.busy('detail',False);self.page.apply_detail(None,self.failures[identity]);return
        self.page.detail_waiting();self.page.feedback.busy('detail')
        request=(identity,entry,self.backend)
        if self.running is not None:self.pending=request if self.running[0]!=identity else None;return
        self.start(request)
    def start(self,request):
        self.running=request;identity,entry,backend=request
        def done(value,error):
            self.running=None
            if error is not None:
                error=error or '未提供错误详情'
                self.failures[identity]=error;self.failures.move_to_end(identity)
                while len(self.failures)>2:self.failures.popitem(last=False)
            else:
                self.cache[identity]=value;self.cache.move_to_end(identity)
                while len(self.cache)>2:self.cache.popitem(last=False)
                self.failures.pop(identity,None)
            pending=self.pending;self.pending=None
            if not self.alive():return
            if pending is not None and pending[0]==self.desired:
                if pending[0] not in self.cache:self.start(pending);return
            if self.desired==identity:
                self.page.feedback.busy('detail',False);self.page.apply_detail(value,error)
            elif self.desired in self.cache:
                self.page.feedback.busy('detail',False);self.page.apply_detail(self.cache[self.desired],None)
        self.app.run_background(partial(backend,entry),done)
