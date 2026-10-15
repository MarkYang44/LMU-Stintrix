"""Real mapped snapshots and deterministic disconnect/session continuity regressions."""
import csv,ctypes,json,mmap,sys,tempfile,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from telemetry import SharedReader,extract
from engine import Engine
from tests.test_core import fixture

class ContinuityTests(unittest.TestCase):
 def test_unsignaled_notifications_do_not_gate_100_fresh_mapped_snapshots(self):
  data=fixture();name='Stintrix_NoGate_'+uuid.uuid4().hex
  with mmap.mmap(-1,ctypes.sizeof(data),tagname=name) as producer:
   producer.write(bytes(data));reader=SharedReader(name)
   # A zero-timeout legacy gate never succeeds. It must have no authority over
   # the production stable-snapshot read path, regardless of event presence.
   class LegacyGate:
    handles=[11,12]
    def ready(self):raise AssertionError('Update events must not be consumed')
   reader.gate=LegacyGate();reader.events=SimpleNamespace(handles=[11,12],lock_present=False,close=lambda:None)
   try:
    for i in range(100):
     data.telemetry.telemInfo[0].mElapsedTime=10+i*.01;producer.seek(0);producer.write(bytes(data));sample=reader.read()
     self.assertIsNotNone(sample);self.assertAlmostEqual(sample['et'],10+i*.01);self.assertFalse(sample['interface']['event_gate'])
    self.assertEqual(reader.monitor.frames,100)
   finally:reader.close()
 def test_event_diagnostics_only_open_and_close_handles_never_wait(self):
  from telemetry_contract import EventPresence
  calls=[]
  class API:
   def __init__(self,kind):self.kind=kind
   def __call__(self,*args):
    calls.append((self.kind,args))
    if self.kind=='wait':raise AssertionError('Diagnostics must not consume notifications')
    return 7 if self.kind=='event' else 8 if self.kind=='mapping' else True
  kernel=SimpleNamespace(OpenEventW=API('event'),OpenFileMappingW=API('mapping'),CloseHandle=API('close'),WaitForSingleObject=API('wait'))
  presence=EventPresence(kernel);self.assertEqual(len(presence.handles),2);presence.close();self.assertEqual(sum(k=='close' for k,args in calls),3);self.assertFalse(any(k=='wait' for k,args in calls))
 def simulate(self,mode):
  actual_run=Engine.run;clock=SimpleNamespace(value=0.)
  errored=[False]
  base=extract(fixture());base.update(track_length=1000,lap_start=0.,lap_invalidated=False,in_pits=False)
  class Wait:
   def __init__(self,*args):pass
   def until(self,*args):clock.value+=.1;return False
   def close(self):pass
  class Feed:
   def read(self):
    t=clock.value
    if t>=(210 if mode=='long_pit' else 8):instance.stop.set();return None
    if 1<=t<(205 if mode=='long_pit' else 5):
     if mode=='error' and not errored[0]:
      errored[0]=True;raise ValueError('temporary decode failure')
     if mode=='frozen':return dict(base,et=100.9)
     return None
    return dict(base,et=(t-5 if mode=='reset' and t>=5 else 100+t),session=5 if mode=='phase' and t>=5 else 10,finish=1 if t>=6 and mode=='finish' else 0)
   def interface_status(self):return dict(in_realtime=False if (mode in ('exit','long_pit') and 1<=clock.value<(205 if mode=='long_pit' else 5)) or (mode=='false_once' and 3.85<=clock.value<3.95) else True)
   def close(self):pass
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temporary:
   with patch.object(Engine,'run'):
    instance=Engine(output=Path(temporary)/'Logs',reader_factory=Feed,settings=dict(mode='fixed',fixed_hz=120));instance.thread.join()
   with patch('engine.time',SimpleNamespace(monotonic=lambda:clock.value,perf_counter=lambda:clock.value)),patch('engine.PreciseWait',Wait),patch('recorder.Recorder._report',staticmethod(lambda folder:None)):
    actual_run(instance)
    for thread in instance.recorder.pending_reports:thread.join()
   values=[]
   for p in sorted((Path(temporary)/'Logs').glob('*/session.json')):
    m=json.loads(p.read_text(encoding='utf-8'))
    with (p.parent/'inputs.csv').open(encoding='utf-8') as stream:rows=list(csv.DictReader(stream))
    values.append((m,rows))
   return values
 def test_disconnect_and_frozen_frames_rejoin_one_record_without_fake_samples(self):
  for mode in ('missing','frozen','error','false_once'):
   with self.subTest(mode=mode):
    values=self.simulate(mode);self.assertEqual(len(values),1);m,rows=values[0]
    self.assertTrue(any(float(r['session_time_s'])>=105 for r in rows));self.assertTrue(any(float(r['session_time_s'])<101 for r in rows))
    self.assertLess(len(rows),55);self.assertEqual(m['telemetry_gap_count'],1);self.assertEqual(m['end_reason'],'application closed')
 def test_real_session_phase_or_elapsed_reset_still_split_records(self):
  for mode in ('phase','reset'):
   with self.subTest(mode=mode):self.assertEqual(len(self.simulate(mode)),2)
 def test_confirmed_finish_does_not_restart_and_long_garage_rejoins_same_race(self):
  finished=self.simulate('finish');self.assertEqual(len(finished),1);self.assertEqual(finished[0][0]['end_reason'],'finish flag 1')
  for mode in ('exit','long_pit'):
   values=self.simulate(mode);self.assertEqual(len(values),1);self.assertEqual(values[0][0]['end_reason'],'application closed');self.assertTrue(any(float(r['session_time_s'])>=105 for r in values[0][1]))

if __name__=='__main__':unittest.main()
