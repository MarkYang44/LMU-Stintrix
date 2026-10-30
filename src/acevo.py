"""Read-only EVO input adapter. Missing game clocks/fields stay missing on disk."""
import ctypes as ct
import math
import time
from acevo_structs import SPageFilePhysics, SPageFileGraphicEvo, SPageFileStaticEvo
from lap_validity import evo_flags

MAPS=(('physics',r'Local\acevo_pmf_physics',SPageFilePhysics),
      ('graphics',r'Local\acevo_pmf_graphics',SPageFileGraphicEvo),
      ('static',r'Local\acevo_pmf_static',SPageFileStaticEvo))
EXTRA=('evo_physics_packet','evo_graphics_packet','evo_lap_time_ms','evo_npos',
       'evo_status','evo_event_id','evo_session_id','evo_session_type',
       'evo_last_lap_time_ms','evo_best_lap_time_ms','evo_current_pos','evo_total_drivers')
DRIVING_COLUMNS=('evo_abs_active','evo_tc_active','evo_esc_active','evo_gear','evo_rpm',
    'evo_rpm_percent','evo_shift_up','evo_shift_down','evo_rpm_limiter',
    'evo_physics_gear','evo_physics_rpm','evo_physics_max_rpm',
    'evo_physics_abs_active','evo_physics_tc_active')
VALIDITY_COLUMNS=('evo_is_valid_lap','evo_timing_invalid')
EXTRA=(*EXTRA,*DRIVING_COLUMNS,*VALIDITY_COLUMNS)


def text(value):return bytes(value).split(b'\0',1)[0].decode('utf-8',errors='strict')


def extract(physics,graphics,static,now):
    """Distinct physics/HUD inputs, never relabelled as raw/filtered equivalents."""
    if graphics.status!=2:return None  # No recording of menus, replay or paused packets.
    if (graphics.focused_car_id_a,graphics.focused_car_id_b)!=(graphics.player_car_id_a,graphics.player_car_id_b):return None
    track=text(static.track);car=text(graphics.car_model)
    if not track or not car or not text(static.sm_version) or static.session not in (-1,0,1,2,3):return None
    controls=[float(physics.gas),float(physics.brake),float(physics.steerAngle),
              float(graphics.gas_percent),float(graphics.brake_percent),float(graphics.steering_percent)]
    if not all(math.isfinite(v) and abs(v)<=1.01 for v in controls) or any(controls[i]<-.01 for i in (0,1,3,4)):return None
    if not math.isfinite(physics.speedKmh) or not 0<=physics.speedKmh<=1500:return None
    if not math.isfinite(static.track_length_m) or not 0<=static.track_length_m<=200000:return None
    if graphics.total_lap_count<0 or graphics.total_lap_count>100000:return None
    if graphics.car_location not in (0,1,2,3,4):return None
    length=float(static.track_length_m);npos=float(graphics.npos)
    extra=dict(zip(EXTRA,(int(physics.packetId),int(graphics.packetId),int(graphics.current_lap_time_ms),
        npos if math.isfinite(npos) else '',int(graphics.status),int(static.event_id),int(static.session_id),int(static.session),
        int(graphics.last_laptime_ms),int(graphics.best_laptime_ms),int(graphics.current_pos),int(graphics.total_drivers))))
    # Preserve the two producers separately. Activity is not the configured level;
    # never combine graphics flags with physics settings or guessed thresholds.
    extra.update(zip(DRIVING_COLUMNS,(int(graphics.abs_active),int(graphics.tc_active),int(graphics.esc_active),
        int(graphics.gear_int),int(graphics.rpm),float(graphics.rpm_percent),
        int(graphics.is_change_up_rpm),int(graphics.is_change_down_rpm),int(graphics.is_rpm_limiter_on),
        int(physics.gear),int(physics.rpms),int(physics.currentMaxRpm),int(physics.absInAction),int(physics.tcinAction))))
    valid=evo_flags(int(graphics.is_valid_lap),int(graphics.timing_state.is_invalid))
    extra.update(evo_is_valid_lap=int(graphics.is_valid_lap),evo_timing_invalid=int(graphics.timing_state.is_invalid))
    result=dict(simulator_id='ac_evo',track=track,track_layout=text(static.track_configuration) or track,
        driver=(text(graphics.driver_name)+' '+text(graphics.driver_surname)).strip(),vehicle=car,vehicle_class='',
        session={0:5,1:10,2:0,3:0}.get(static.session,-1),simulator_session=int(static.session),
        session_uid=(int(static.event_id),int(static.session_id)),
        session_name=text(static.session_name),player_id=str(graphics.player_car_id_a)+':'+str(graphics.player_car_id_b),
        et=now,frame_id=int(physics.packetId),clock_source='host_monotonic',lap=int(graphics.total_lap_count)+1,
        controls=controls,speed=float(physics.speedKmh),finish=1 if graphics.session_state.end_session_flag else 0,
        race_mode='online' if static.is_online else 'single',
        in_pits=bool(graphics.is_in_pit_box or graphics.is_in_pit_lane),
        lap_invalidated=None if valid is None else not valid,
        conditions={},native=extra,
        interface=dict(simulator='ac_evo',layout='SharedFileOut v1 / 2026-04-28',
            sm_version=text(static.sm_version),game_version=text(static.ac_evo_version),
            inputs=['physics gas/brake/steerAngle','graphics gas_percent/brake_percent/steering_percent'],
            clock='host monotonic acquisition; session_time_s unavailable',cross_page_atomic=False))
    if length>0:result['track_length']=length
    if length>0 and math.isfinite(npos) and 0<=npos<=1:result['distance']=npos*length
    return result


class SharedReader:
    """Attach only: no CreateFileMapping, writes, events or game installation edits."""
    def __init__(self):
        self.maps={};self.frames=0;self.rejected=0;self.last_packet=None;self.last_physics=None;self.last_sample=None;self.last_fresh=None
        self.kernel=ct.WinDLL('kernel32',use_last_error=True)
        self.kernel.OpenFileMappingW.argtypes=[ct.c_uint32,ct.c_int,ct.c_wchar_p];self.kernel.OpenFileMappingW.restype=ct.c_void_p
        self.kernel.MapViewOfFile.argtypes=[ct.c_void_p,ct.c_uint32,ct.c_uint32,ct.c_uint32,ct.c_size_t];self.kernel.MapViewOfFile.restype=ct.c_void_p
        self.kernel.UnmapViewOfFile.argtypes=[ct.c_void_p];self.kernel.CloseHandle.argtypes=[ct.c_void_p]
        try:
            for key,name,kind in MAPS:
                handle=self.kernel.OpenFileMappingW(4,False,name)
                if not handle:raise ct.WinError(ct.get_last_error())
                pointer=self.kernel.MapViewOfFile(handle,4,0,0,ct.sizeof(kind))
                if not pointer:
                    self.kernel.CloseHandle(handle);raise ct.WinError(ct.get_last_error())
                self.maps[key]=(handle,pointer,kind)
        except Exception:self.close();raise

    def snapshot(self,key):
        _,pointer,kind=self.maps[key];size=ct.sizeof(kind)
        for _ in range(3):
            first=ct.string_at(pointer,size);second=ct.string_at(pointer,size)
            if first==second:return kind.from_buffer_copy(first),first
        raise ValueError('AC EVO snapshot changed during read')

    def read(self):
        try:
            if self.last_packet is not None:
                # Exactly the key the full path would reject as a duplicate.
                # Recheck both packet IDs around the static page copy; changed
                # graphics (including finish) or metadata always takes the full path.
                pp=self.maps['physics'][1];gp=self.maps['graphics'][1]
                pkey=ct.string_at(pp,4);gkey=ct.string_at(gp,4)
                if (int.from_bytes(pkey,'little',signed=True)==self.last_packet[0] and
                    int.from_bytes(gkey,'little',signed=True)==self.last_packet[1] and
                    ct.string_at(self.maps['static'][1],ct.sizeof(self.maps['static'][2]))==self.last_packet[2] and
                    ct.string_at(pp,4)==pkey and ct.string_at(gp,4)==gkey):return None
            # The producer updates pages at different rates. Each page must be stable;
            # a physics or graphics update across the read is retried, never interpolated.
            for _ in range(3):
                p,pb=self.snapshot('physics');g,gb=self.snapshot('graphics');s,sb=self.snapshot('static')
                if (ct.string_at(self.maps['physics'][1],4)!=pb[:4] or
                    ct.string_at(self.maps['graphics'][1],4)!=gb[:4] or
                    ct.string_at(self.maps['static'][1],ct.sizeof(s))!=sb):continue
                key=(int(p.packetId),int(g.packetId),sb)
                if self.last_packet is None:
                    # Another consumer can keep mappings alive after game exit.
                    # Establish a baseline and require a producer update before recording.
                    self.last_packet=key;self.last_physics=int(p.packetId);return None
                if key==self.last_packet:return None
                advanced=int(p.packetId)!=self.last_physics
                self.last_physics=int(p.packetId);self.last_packet=key
                if not advanced and not (self.last_sample and g.session_state.end_session_flag):return None
                value=extract(p,g,s,time.monotonic())
                if value is not None:
                    self.frames+=1;self.last_sample=value;self.last_fresh=time.monotonic()
                elif g.status==2:self.rejected+=1
                return value
        except (ValueError,UnicodeError):pass
        self.rejected+=1;return None

    def interface_status(self):
        value=dict(simulator_id='ac_evo',frames=self.frames,rejected=self.rejected,
            age_s=None if self.last_fresh is None else time.monotonic()-self.last_fresh,
            channels_available=self.last_sample is not None,read_only=True,
            synchronization='stable page snapshots; independent producer rates',
            layout='SharedFileOut v1 / 2026-04-28',live_game_verified=False)
        value.update(self.last_sample['interface'] if self.last_sample else {})
        return value

    def close(self):
        for handle,pointer,_ in self.maps.values():
            self.kernel.UnmapViewOfFile(pointer);self.kernel.CloseHandle(handle)
        self.maps.clear();self.last_sample=None
