"""Read-only contract inspection and bounded freshness diagnostics."""
import ctypes,time,math,re
from pathlib import Path
from paths import discover_game

# Interface declarations only; proprietary SDK headers are not redistributed.
HEADER_DECLARATIONS={'SharedMemoryInterface.hpp':('SharedMemoryObjectOut','LMU_Data_HoldEvent','LMU_Data_DataEvent'),'InternalsPlugin.hpp':('TelemInfoV01','ScoringInfoV01'),'PluginObjects.hpp':('PluginObject',)}
SDK_COMMIT='6cef58e22bf025268acee93e9e5ea4f569939c1b'

def installed_contract(game=None):
    game=Path(game) if game else discover_game();checks=[]
    if game:
        for name,expected in HEADER_DECLARATIONS.items():
            path=game/'Support/SharedMemoryInterface'/name
            content=path.read_text(encoding='utf-8',errors='replace') if path.is_file() else ''
            checks.append(dict(file=name,present=bool(content),interface_declarations=all(token in content for token in expected)))
    from pyLMUSharedMemory.lmu_data import LMUObjectOut
    return dict(sdk_commit=SDK_COMMIT,structure_size=ctypes.sizeof(LMUObjectOut),offsets={k:getattr(LMUObjectOut,k).offset for k in ('generic','paths','scoring','telemetry')},headers=checks,
        header_status='interface_found' if checks and all(c['interface_declarations'] for c in checks) else 'changed_or_missing' if checks else 'game_not_found')

class ReaderMonitor:
    def __init__(self):
        self.last_et=None;self.fresh_at=None;self.last_version=None;self.frames=0;self.rejected=0;self.reads=0;self.torn=0;self.latest={};self.version_changes=0
    def observe(self,data,sample,now=None):
        now=time.monotonic() if now is None else now;self.reads+=1
        version=int(data.generic.gameVersion);count=int(data.scoring.scoringInfo.mNumVehicles);active=int(data.telemetry.activeVehicles)
        if not 0<=count<=104 or not 0<=active<=104:self.rejected+=1;return False
        changed=self.last_version is not None and version!=self.last_version
        if changed:self.fresh_at=None;self.last_et=None;self.version_changes+=1
        self.last_version=version
        if sample is not None:
            et=sample['et']
            if self.last_et is None or et!=self.last_et:self.fresh_at=now;self.frames+=1;self.last_et=et
        self.latest=dict(game_version=version,version_changed=changed,scoring_vehicles=count,telemetry_vehicles=active,in_realtime=bool(data.scoring.scoringInfo.mInRealtime),player_vehicle=bool(data.telemetry.playerHasVehicle),channels_available=sample is not None)
        return True
    def snapshot(self,now=None):
        now=time.monotonic() if now is None else now;age=now-self.fresh_at if self.fresh_at is not None else None
        return dict(self.latest,age_s=age,stale=age is not None and age>1,frames=self.frames,reads=self.reads,rejected=self.rejected,torn_snapshots=self.torn,version_changes=self.version_changes)

class EventPresence:
    """Inspect notification objects without waiting on or consuming their signals."""
    def __init__(self,kernel):
        self.kernel=kernel;self.handles=[];self.lock_present=False
        kernel.OpenEventW.argtypes=[ctypes.c_uint32,ctypes.c_int,ctypes.c_wchar_p];kernel.OpenEventW.restype=ctypes.c_void_p
        for name in ('LMU_Data_HoldEvent','LMU_Data_DataEvent'):
            handle=kernel.OpenEventW(0x00100000,False,name)
            if handle:self.handles.append(handle)
            else:self.close();break
        lock=kernel.OpenFileMappingW(4,False,'LMU_SharedMemoryLockData')
        if lock:self.lock_present=True;kernel.CloseHandle(lock)
    def close(self):
        for h in self.handles:self.kernel.CloseHandle(h)
        self.handles=[]

def probe(game=None,live=None):
    value=installed_contract(game)
    if live is not None:value.update(live);return value
    from telemetry import SharedReader
    reader=None
    try:
        reader=SharedReader();deadline=time.monotonic()+.6
        while time.monotonic()<deadline:reader.read();time.sleep(.02)
        value.update(reader.interface_status());value['connection']='opened'
    except OSError as e:value.update(connection='waiting',message=str(e))
    finally:
        if reader:reader.close()
    return value
