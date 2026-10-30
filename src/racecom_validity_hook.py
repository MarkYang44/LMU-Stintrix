"""Stintrix-only bridge: game validity controls color; eligibility controls stats.

Loaded by the user's existing local RaceCom hook. No third-party source is copied.
"""
from contextlib import contextmanager
from functools import lru_cache
import json
from pathlib import Path


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


@contextmanager
def statistics(sheet):
    saved=[]
    try:
        value=payload(sheet.source);eligible={row['num']:row.get('statistics_eligible') is True for row in value['laps']} if value else {}
        for lap in sheet.laps:
            if lap.num in eligible:
                saved.append((lap,lap.valid));lap.valid=eligible[lap.num]
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
        rows={lap['num']:lap for lap in value['laps']}
        for lap in sheet.laps:
            row=rows.get(lap.num)
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
    def rows(self):
        result=original_rows(self)
        if self.sheet is None or payload(self.sheet.source) is None:return result
        return [(*row[:6],lap.extra_note) for row,lap in zip(result,self.sheet.laps)]
    pil_type.rows=rows
    renderer=ns['RaceLogRenderer'];original_flags=renderer._lap_row_flags
    def flags(self,rows):
        value=payload(self.data.source_txt)
        if value is None:return original_flags(self,rows)
        eligible={lap['num'] for lap in value['laps'] if lap.get('statistics_eligible') is True}
        statistical=[]
        for row in rows:
            copy=list(row)
            if int(copy[0]) not in eligible:copy[6]='无效'
            statistical.append(copy)
        return original_flags(self,statistical)
    renderer._lap_row_flags=flags
    sheet_type._stintrix_game_validity=True
