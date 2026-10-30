"""Optional observed target overlays; source data and default history stay intact."""
import csv,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_rhythm_target_line_exact_hover_range_clear_language_and_failed_refresh(self):
        script=r'''
import sys,time,traceback,tkinter as tk
from copy import deepcopy
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
from control_history_chart import ProgressChart
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.withdraw();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.18):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 w=show(app,app.data_path/'Logs/evo');w.geometry('1050x820');pump(.7);c=w.lap_overview;r=c['rhythm'];table=c['table'];original=deepcopy(c['state']['result']['index'])
 assert r.chart is None
 with patch('evo_laps.index',side_effect=AssertionError('No target index read')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No target telemetry read')),patch.object(app,'run_background',side_effect=AssertionError('No target background task')):
  c['set_goal']('0:20.411');assert r.chart is None
  r.toggle();pump();chart=r.chart;assert chart.target==20.411 and len(chart.points)==5 and len(chart.find_withtag('target'))==2
  target=next(i for i in chart.find_withtag('target') if chart.type(i)=='line');line=chart.coords(target)
  equal=next(p for p in chart.points if p[2]['number']==3);assert abs(line[1]-equal[1])<1e-8
  assert len(chart.find_withtag('series'))==2  # Only 2–3 and 7–8 connect; invalid/unknown laps leave gaps.
  chart.hover=next(i for i,p in enumerate(chart.points) if p[2]['number']==5);chart.update_hover();assert '+0.274 s' in chart.itemcget(chart.tooltip,'text')
  before=(table.selection(),tuple(table.order),table.offset);c['set_goal']('100');pump();assert chart.target==100 and len(chart.points)==5
  for target in chart.find_withtag('target'):
   if chart.type(target)=='line':assert 0<=chart.coords(target)[1]<=chart.winfo_height()
  c['set_goal']('0.001');pump();assert len(chart.points)==5 and not any(chart.itemcget(i,'text').startswith('-') for i in chart.find_all() if chart.type(i)=='text')
  c['set_goal']('');pump();assert chart.target is None and not chart.find_withtag('target') and len(chart.points)==5 and before==(table.selection(),tuple(table.order),table.offset)
  r.toggle();c['set_goal']('0:20.411');r.toggle();pump();assert chart.target==20.411
  app.set_theme('light');app.toggle_language();w.geometry('800x600');pump(.3);chart=r.chart
  assert any(chart.itemcget(i,'text').startswith('Target ') for i in chart.find_withtag('target') if chart.type(i)=='text')
  chart.hover=0;chart.update_hover();assert 'Difference to target' in chart.itemcget(chart.tooltip,'text')
  # The shared time-history chart retains its original behavior and no target.
  host=tk.Frame(w);history=ProgressChart(host,lambda _:None,axis='time');history.set([dict(observed_utc='2026-10-29T12:00:00Z',time_s=100.)],target=99.)
  assert history.target is None and not history.find_withtag('target');history.destroy();host.destroy()
  assert c['state']['result']['index']==original
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.4)
 assert not r.chart.points and not r.chart.find_withtag('target') and c['state']['result'] is None
 w.destroy();assert not errors,errors;app.request_close();pump(.1)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=8);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
                if row['lap']=='6':row['lap_invalidated']=''
            with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')};env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
