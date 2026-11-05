"""Stintrix-only bridge: game validity controls color; eligibility controls stats.

Loaded by the user's existing local RaceCom hook. No third-party source is copied.
"""
from contextlib import contextmanager
from functools import lru_cache
import json
from pathlib import Path
from collections import defaultdict,deque
import math


def payload(path):
    try:
        path=Path(path).parent/'race_log.json';stamp=path.stat()
        if stamp.st_size>4_000_000:return None
        return _payload(str(path.resolve()),stamp.st_size,stamp.st_mtime_ns)
    except (OSError,ValueError,AttributeError):return None


@lru_cache(maxsize=8)
def _payload(path,size,mtime):
    value=json.loads(Path(path).read_text('utf-8-sig'))
    return value if isinstance(value,dict) and value.get('stintrix_validity_policy')==1 else None


def key(number,time):
    try:
        if isinstance(time,str) and ':' in time:
            minutes,seconds=time.split(':');time=float(minutes)*60+float(seconds)
        time=float(time)
        return (int(number),round(time*1000)) if math.isfinite(time) and time>0 else None
    except (ValueError,TypeError,OverflowError):return None


def matched(items,rows,identify):
    """Repeated lap numbers need time plus occurrence, not a number dictionary."""
    queues=defaultdict(deque)
    for row in rows:
        identity=key(row.get('num'),row.get('time'))
        if identity is not None:queues[identity].append(row)
    for item in items:
        queue=queues.get(key(*identify(item)))
        yield item,queue.popleft() if queue else None


class StatisticTime(str):
    """Keep the displayed time intact while the renderer computes highlights."""
    def __new__(cls,text,eligible):
        value=super().__new__(cls,text);value.eligible=eligible;return value


@contextmanager
def statistics(sheet):
    saved=[]
    try:
        value=payload(sheet.source)
        if value:
            for lap,row in matched(sheet.laps,value['laps'],lambda lap:(lap.num,lap.time)):
                saved.append((lap,lap.valid));lap.valid=row is not None and row.get('statistics_eligible') is True
        yield
    finally:
        for lap,valid in saved:lap.valid=valid


def install(ns):
    sheet_type=ns['LapSheet']
    if getattr(sheet_type,'_stintrix_game_validity',False):return
    original_load=ns['load_lap_sheet'];original_recompute=ns['recompute_lap_flags']
    def recompute(sheet):
        with statistics(sheet):
            result=original_recompute(sheet)
            for lap in sheet.laps:
                if not lap.valid:
                    lap.best=False;lap.delta=None
                    for name in ('s1_best','s2_best','s3_best'):
                        if hasattr(lap,name):setattr(lap,name,False)
            return result
    def load(path):
        sheet=original_load(path);value=payload(path)
        if value is None:return sheet
        for lap,row in matched(sheet.laps,value['laps'],lambda lap:(lap.num,lap.time)):
            if row is None:continue
            lap.valid=row.get('game_valid') is not False
            lap.extra_note=row.get('note','')
        recompute(sheet);return sheet
    for name in ('reference_best','best_lap','best_sector'):
        descriptor=vars(sheet_type)[name];original=descriptor.fget if isinstance(descriptor,property) else descriptor
        def wrapped(self,*args,_original=original,**kwargs):
            with statistics(self):return _original(self,*args,**kwargs)
        setattr(sheet_type,name,property(wrapped) if isinstance(descriptor,property) else wrapped)
    ns['load_lap_sheet']=load;ns['recompute_lap_flags']=recompute
    if hasattr(sheet_type,'valid_count'):
        original_count=sheet_type.valid_count
        def valid_count(self):
            value=payload(self.source)
            return sum(row.get('game_valid') is True for row in value['laps']) if value else original_count(self)
        sheet_type.valid_count=valid_count
    pil_type=ns['LapSheetPilRenderer'];original_rows=pil_type.rows
    parse=ns.get('parse_lap_time')
    if callable(parse):
        def parse_statistic_time(value):
            # RaceCom uses zero for missing statistics and tests the result > 0.
            return 0.0 if isinstance(value,StatisticTime) and not value.eligible else parse(value)
        ns['parse_lap_time']=parse_statistic_time
    def rows(self):
        result=original_rows(self)
        value=payload(self.sheet.source) if self.sheet is not None else None
        if value is None:return result
        output=[]
        for row,source in matched(result,value['laps'],lambda row:(row[0],row[1])):
            copy=list(row)
            if source is not None:copy[6]=source.get('note','')
            # The original PIL table recomputes highlights from its row text,
            # independently of LapSheet.best_lap. Restrict this fix to LMU.
            if callable(parse) and value.get('simulator_id','lmu')=='lmu':
                for column in (1,3,4,5):copy[column]=StatisticTime(copy[column],source is not None and source.get('statistics_eligible') is True)
            output.append(tuple(copy))
        return output
    pil_type.rows=rows
    renderer=ns['RaceLogRenderer'];original_flags=renderer._lap_row_flags
    def flags(self,rows):
        value=payload(self.data.source_txt)
        if value is None:return original_flags(self,rows)
        statistical=[]
        for row,source in matched(rows,value['laps'],lambda row:(row[0],row[1])):
            copy=list(row)
            if source is None or source.get('statistics_eligible') is not True:copy[6]='无效'
            statistical.append(copy)
        return original_flags(self,statistical)
    renderer._lap_row_flags=flags
    sheet_type._stintrix_game_validity=True
