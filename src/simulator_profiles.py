"""Immutable game capabilities and report policies; no Tk, file IO or SDK imports."""
from dataclasses import dataclass
from typing import Protocol,Callable
from types import MappingProxyType


class InputReader(Protocol):
    """Common input boundary. Missing game clocks/channels remain unavailable."""
    def read(self) -> dict | None: ...
    def close(self) -> None: ...


@dataclass(frozen=True,slots=True)
class Capabilities:
    driving_instruments:bool=False
    vehicle_telemetry:bool=False
    endurance:bool=False
    reference_laps:bool=False
    lap_comparison:bool=False
    selected_laps:bool=False
    record_history:bool=False
    video_analysis:bool=False
    training:bool=False
    native_import:bool=False
    official_results:bool=False
    full_review:bool=False

    def panel(self,key):
        if key=='main':return True
        if key in ('tyres','strategy'):return self.vehicle_telemetry
        if key in ('pit','stint','weather'):return self.endurance
        return False


@dataclass(frozen=True,slots=True)
class ReportPolicy:
    steps:tuple[str,...]
    build:Callable
    dependencies:tuple[tuple[str,tuple[str,...]],...]=()
    error_markers:bool=True
    cache_budget:bool=True
    legacy_outputs:bool=True


@dataclass(frozen=True,slots=True)
class SimulatorProfile:
    id:str
    name:str
    short:str
    title:str
    reader_type:Callable[[],type[InputReader]]
    capabilities:Capabilities
    reports:ReportPolicy
    catalogue:str
    recording_hint:str
    input_labels:tuple[str,str]
    clock_source:str
    defer_reports_during_capture:bool=False
    reset_on_counter_rewind:bool=False


def _lmu_reader():
    from telemetry import SharedReader
    return SharedReader


def _evo_reader():
    from acevo import SharedReader
    return SharedReader


def _lmu_reports(folder,meta,steps):
    from session_reports import operations
    return operations(folder,steps)


def _evo_reports(folder,meta,steps):
    from evo_reports import operations
    return operations(folder,meta)


PROFILES=MappingProxyType({
    'lmu':SimulatorProfile('lmu','Le Mans Ultimate','LMU','LMU Stintrix',
        _lmu_reader,Capabilities(vehicle_telemetry=True,endurance=True,reference_laps=True,
            lap_comparison=True,selected_laps=True,record_history=True,video_analysis=True,training=True,native_import=True,official_results=True,full_review=True),
        ReportPolicy(('analysis','endurance','fastest','review','images','compression'),
            _lmu_reports,
            (('endurance',('analysis',)),('review',('analysis','endurance','fastest')),
             ('compression',('analysis','endurance','fastest','review','images')))),
        'guide','排位和正赛自动保存；练习赛完整记录可在设置中开启。',
        ('原始输入','游戏过滤后'),'game_session'),
    'ac_evo':SimulatorProfile('ac_evo','Assetto Corsa EVO','AC EVO','Stintrix · AC EVO',
        _evo_reader,Capabilities(selected_laps=True,record_history=True,driving_instruments=True),
        # EVO partial reports are independent; preserve its existing retry rules.
        ReportPolicy(('fastest','review','images','compression'),_evo_reports,error_markers=False,cache_budget=False,legacy_outputs=False),
        'official','计时赛和正赛自动保存；练习与巡航可在设置中开启。',
        ('EVO 物理输入','EVO 仪表输入'),'host_capture',True,True),
})


def profile(simulator):
    try:return PROFILES[simulator]
    except (KeyError,TypeError):raise ValueError('Unknown simulator: '+str(simulator)) from None


def capabilities(simulator):return profile(simulator).capabilities
