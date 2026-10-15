"""Read-only LMU shared memory and validated telemetry snapshots."""
import ctypes
import math
import time
from itertools import islice
import vehiclelab
from race_journal import capture


def decode(value):
    return bytes(value).split(b'\0', 1)[0].decode('utf-8', 'replace')


def extract(data, race_cache=None):
    info = data.scoring.scoringInfo
    telemetry = data.telemetry
    if not info.mInRealtime or not telemetry.playerHasVehicle:
        return None
    count = min(104, max(0, int(info.mNumVehicles)))
    player = next((v for v in islice(data.scoring.vehScoringInfo,count) if v.mIsPlayer), None)
    if player is None:
        return None
    car = next((v for v in islice(telemetry.telemInfo,min(104,max(0,int(telemetry.activeVehicles))))
                if v.mID == player.mID), None)
    if car is None or not math.isfinite(car.mElapsedTime):
        return None
    values = [float(getattr(car, 'm' + prefix + name))
              for prefix in ('Unfiltered', 'Filtered') for name in ('Throttle', 'Brake', 'Steering')]
    if not all(math.isfinite(v) for v in values):
        return None
    if any(abs(v) > 1.01 for v in values) or any(values[i] < -0.01 for i in (0, 1, 3, 4)):
        return None
    position = [float(getattr(car.mPos, axis)) for axis in ('x','y','z')]
    return {'track': decode(info.mTrackName), 'driver': decode(player.mDriverName),
            'track_layout':decode(car.mTrackName) or decode(info.mTrackName),
            'vehicle_class':decode(player.mVehicleClass),
            'vehicle': decode(car.mVehicleModel) or decode(car.mVehicleName), 'session': int(info.mSession),
            'player_id': int(player.mID), 'et': float(car.mElapsedTime),
            'session_clock':float(info.mCurrentET),'race_mode': 'online' if int(info.mGameMode)==2 else 'unknown',
            'game_mode_raw':int(info.mGameMode),
            'lap': int(car.mLapNumber), 'distance': float(player.mLapDist),
            'controls': values, 'position':position if all(math.isfinite(v) for v in position) else None,
            'speed': math.sqrt(sum(float(getattr(car.mLocalVel, a)) ** 2
                                                      for a in ('x', 'y', 'z'))) * 3.6,
            'finish': int(player.mFinishStatus),
            'lap_start':float(car.mLapStartET),'lap_invalidated':bool(car.mLapInvalidated),
            'in_pits':bool(player.mInPits),'track_length':float(info.mLapDist),
            'conditions':{'fuel_l':float(car.mFuel) if math.isfinite(car.mFuel) and car.mFuel>=0 else '',
                'tyre_compound':int(car.mFrontTireCompoundIndex),
                'tyre_rear_compound':int(car.mRearTireCompoundIndex),
                'tyre_front_name':decode(car.mFrontTireCompoundName),
                'tyre_rear_name':decode(car.mRearTireCompoundName),
                'ambient_temp_c':float(info.mAmbientTemp) if math.isfinite(info.mAmbientTemp) else '',
                'rain':float(info.mRaining) if math.isfinite(info.mRaining) else '',
                'track_grip':int(info.mTrackGripLevel),
                'track_temp_c':float(info.mTrackTemp) if math.isfinite(info.mTrackTemp) else '',
                'wetness':float(info.mAvgPathWetness) if math.isfinite(info.mAvgPathWetness) and 0<=info.mAvgPathWetness<=1 else '',
                'tc_level':int(car.mTC),'abs_level':int(car.mABS),'tc_active':int(car.mTCActive),
                'abs_active':int(car.mABSActive),'gear':int(car.mGear)},
            'vehicle_data':vehiclelab.extract_vehicle(car,info,player),
            'race_state':capture(data,car,player,info,race_cache)}


class SharedReader:
    """Open an EXISTING map with FILE_MAP_READ; never create or alter it."""
    def __init__(self, map_name='LMU_Data'):
        from pyLMUSharedMemory.lmu_data import LMUObjectOut
        self.structure = LMUObjectOut
        self.size = ctypes.sizeof(LMUObjectOut)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        self.kernel.OpenFileMappingW.restype = ctypes.c_void_p
        self.kernel.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                            ctypes.c_uint32, ctypes.c_size_t]
        self.kernel.MapViewOfFile.restype = ctypes.c_void_p
        self.kernel.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.handle = self.kernel.OpenFileMappingW(4, False, map_name)
        if not self.handle:
            raise OSError('Waiting for LMU shared memory')
        self.pointer = self.kernel.MapViewOfFile(self.handle, 4, 0, 0, self.size)
        if not self.pointer:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
            raise OSError('Cannot read LMU shared memory')
        self.compare=ctypes.CDLL('msvcrt').memcmp
        self.compare.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t];self.compare.restype=ctypes.c_int
        self.snapshot=self.structure()
        self.verification=self.structure()
        self.cached_sample = None
        self.cached_at = 0
        self.race_cache = None
        from telemetry_contract import ReaderMonitor,EventPresence
        self.monitor=ReaderMonitor();self.events=EventPresence(self.kernel) if map_name=='LMU_Data' else None

    def read(self):
        if (self.cached_sample is not None and time.monotonic()-self.cached_at < 0.25
                and self.cached_id.value == self.cached_sample['player_id']
                and self.cached_et.value == self.cached_sample['et'] and self.cached_realtime.value):
            return self.cached_sample
        # Discard a snapshot if the producer changed it while it was copied.
        for _ in range(3):
            # Reuse two independent snapshots: full equality still detects tearing.
            ctypes.memmove(ctypes.addressof(self.snapshot),self.pointer,self.size)
            ctypes.memmove(ctypes.addressof(self.verification),self.pointer,self.size)
            if self.compare(ctypes.addressof(self.snapshot),ctypes.addressof(self.verification),self.size)==0:
                data = self.snapshot
                # Bounds validation precedes decoding any variable-size vehicle inventory.
                if not 0<=int(data.scoring.scoringInfo.mNumVehicles)<=104 or not 0<=int(data.telemetry.activeVehicles)<=104:
                    self.monitor.observe(data,None);return None
                sample = extract(data,getattr(self,'race_cache',None))
                self.monitor.observe(data,sample)
                if sample is not None:sample['interface']=dict(game_version=self.monitor.last_version,sdk_commit='6cef58e22bf025268acee93e9e5ea4f569939c1b',snapshot='stable_double_copy',event_gate=False,event_notifications=bool(self.events and self.events.handles))
                self.race_cache = sample.get('race_state') if sample else None
                self.cached_sample = sample
                self.cached_at = time.monotonic()
                if sample is not None:
                    index = next(i for i in range(min(104,int(data.telemetry.activeVehicles)))
                                 if data.telemetry.telemInfo[i].mID == sample['player_id'])
                    telem_type, car_type = type(data.telemetry), type(data.telemetry.telemInfo[0])
                    address = (self.pointer+self.structure.telemetry.offset+telem_type.telemInfo.offset
                               +index*ctypes.sizeof(car_type))
                    fields = {entry[0]:entry[1] for entry in car_type._fields_}
                    self.cached_id = fields['mID'].from_address(address+car_type.mID.offset)
                    self.cached_et = fields['mElapsedTime'].from_address(address+car_type.mElapsedTime.offset)
                    score_type, info_type = type(data.scoring), type(data.scoring.scoringInfo)
                    address = self.pointer+self.structure.scoring.offset+score_type.scoringInfo.offset
                    field = next(entry[1] for entry in info_type._fields_ if entry[0]=='mInRealtime')
                    self.cached_realtime = field.from_address(address+info_type.mInRealtime.offset)
                return sample
        self.monitor.torn+=1
        return None

    def interface_status(self):
        return dict(self.monitor.snapshot(),event_gate=False,event_notifications=bool(self.events and self.events.handles),lock_present=bool(self.events and self.events.lock_present),synchronization='stable snapshots; notifications not consumed')

    def close(self):
        if getattr(self,'events',None):self.events.close()
        self.cached_sample=None;self.race_cache=None
        self.snapshot=None;self.verification=None
        if getattr(self, 'pointer', None):
            self.kernel.UnmapViewOfFile(self.pointer)
            self.pointer = None
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
