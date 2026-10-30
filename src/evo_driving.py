"""EVO display-only activity edges; all native samples remain in inputs.csv."""
import math
from buffers import NumericRing

ASSISTS=('ABS','TC','ESC')


def activity(native):
    return tuple(v if type(v) is int and v in (0,1) else math.nan
                 for v in (native.get('evo_'+name.lower()+'_active') for name in ASSISTS))


class ActivityHistory:
    """Only transitions occupy HUD memory. Not a recorder or a polling source."""
    def __init__(self):
        self.edges=NumericRing(4,80001);self.last=None;self.state=None

    def clear(self):
        self.edges.clear();self.last=None;self.state=None

    def add(self,stamp,native):
        state=activity(native)
        # Break disconnected observations at the last actual sample, not at
        # a guessed transition time inside a telemetry gap.
        if self.last is not None and stamp-self.last>3:
            self.edges.append((self.last,math.nan,math.nan,math.nan));self.state=None
        if state!=self.state:self.edges.append((stamp,*state));self.state=state
        self.last=stamp
        while len(self.edges)>1 and self.edges[1][0]<stamp-20:self.edges.popleft()

    def snapshot(self,cutoff):
        start=max(0,self.edges.lower_bound(cutoff)-1)
        return tuple(self.edges[i] for i in range(start,len(self.edges))),self.last


def marker_segments(snapshot,now,window,x0,x1):
    """Pixel-merge only the paint path; keep brief captured pulses visible."""
    edges,last=snapshot;lanes=[[],[],[]]
    if last is None:return lanes
    scale=(x1-x0)/window;cutoff=now-window
    for i,edge in enumerate(edges):
        end=edges[i+1][0] if i+1<len(edges) else last
        if end<cutoff or edge[0]>now:continue
        left=max(x0,x1-(now-max(edge[0],cutoff))*scale)
        right=min(x1,max(left+1,x1-(now-min(end,now))*scale))
        for lane,value in enumerate(edge[1:]):
            if value!=1:continue
            spans=lanes[lane]
            if spans and left<=spans[-1][1]+1:spans[-1]=(spans[-1][0],max(right,spans[-1][1]))
            else:spans.append((left,right))
    return lanes


def instruments(sample):
    native=sample.get('native',{}) if sample else {}
    gear=native.get('evo_gear');rpm=native.get('evo_rpm');fraction=native.get('evo_rpm_percent')
    gear='R' if gear==0 else 'N' if gear==1 else str(gear-1) if type(gear) is int and 2<=gear<=16 else '—'
    rpm=str(rpm) if type(rpm) is int and 0<=rpm<=65535 else '—'
    fraction=fraction if isinstance(fraction,(int,float)) and not isinstance(fraction,bool) and math.isfinite(fraction) and 0<=fraction<=1.5 else None
    speed=sample.get('speed') if sample else None
    speed=f'{speed:.0f}' if isinstance(speed,(int,float)) and math.isfinite(speed) and 0<=speed<=1500 else '—'
    return dict(gear=gear,rpm=rpm,fraction=fraction,speed=speed,up=native.get('evo_shift_up')==1,
        limiter=native.get('evo_rpm_limiter')==1,activity=activity(native))
