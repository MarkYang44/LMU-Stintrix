"""Keyboard graph browsing reuses exact observed entries and existing selection."""
import csv,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_chart_keyboard_boundaries_gaps_enter_focus_themes_and_history_reuse(self):
        script=r'''
import sys,time,traceback,tkinter as tk
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
from control_history_chart import ProgressChart
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.withdraw();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.15):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 def press(chart,key):chart.focus_force();pump(.08);chart.event_generate('<'+key+'>');pump(.04)
 w=show(app,app.data_path/'Logs/evo');w.geometry('1050x820');pump(.7);c=w.lap_overview;r=c['rhythm'];original=deepcopy(c['state']['result']['index']);c['set_goal']('0:20.411');r.toggle();pump();chart=r.chart
 assert [p[2]['number'] for p in chart.points]==[2,3,5,7,8] and chart.cget('takefocus')=='1'
 with patch('evo_laps.index',side_effect=AssertionError('No navigation index read')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No navigation samples')),patch.object(app,'run_background',side_effect=AssertionError('No navigation background task')):
  press(chart,'End');assert chart.hover==4;press(chart,'Right');assert chart.hover==4
  press(chart,'Home');assert chart.hover==0;press(chart,'Left');assert chart.hover==0
  press(chart,'Right');press(chart,'Right');assert chart.points[chart.hover][2]['number']==5 and '+0.274 s' in chart.itemcget(chart.tooltip,'text')
  chart.event_generate('<Leave>');pump(.05);assert chart.hover==2
  before=(tuple(c['table'].order),c['query'].get(),c['kind'].get());press(chart,'Return');assert not r.visible and c['table'].selection()==('4',) and before==(tuple(c['table'].order),c['query'].get(),c['kind'].get())
  r.toggle();pump();press(chart,'End');r.button.focus_force();pump();assert chart.hover is None
  app.set_theme('light');app.toggle_language();w.geometry('800x600');pump(.35);chart=r.chart;assert chart.winfo_ismapped() and chart.winfo_height()>70
  assert not c['buttons']['run'].winfo_ismapped();press(chart,'Home');assert 'Difference to target' in chart.itemcget(chart.tooltip,'text'),(chart.hover,chart.target,chart.itemcget(chart.tooltip,'text'),app.root.focus_get())
  hint=next(x for x in r.host.winfo_children() if x.winfo_class()=='Label');assert 'Left/Right' in hint.cget('text') and int(hint.cget('wraplength'))<=r.host.winfo_width()
  assert hint.winfo_rootx()+hint.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1
  assert c['state']['result']['index']==original
  press(chart,'Return');assert not r.visible and c['buttons']['run'].winfo_ismapped() and c['table'].selection()==('1',)
 # The same keys select the original LMU history entry, retaining time semantics.
 history_window=tk.Toplevel(w);history_window.geometry('750x400');chosen=[];history=ProgressChart(history_window,chosen.append,axis='time');history.pack(fill='both',expand=True)
 entries=[dict(observed_utc='2026-10-29T12:00:00Z',time_s=100.12345678901234),dict(observed_utc='2026-10-29T13:00:00Z',time_s=99.12345678901234)];history.set(entries);pump()
 press(history,'End');press(history,'Return');assert chosen==[entries[-1]] and chosen[0] is entries[-1]
 press(history,'Home');press(history,'Return');assert chosen[-1] is entries[0] and history.target is None
 history.set([]);press(history,'End');press(history,'Return');assert len(chosen)==2
 history_window.destroy();w.destroy();assert not errors,errors;app.request_close();pump(.1)
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
