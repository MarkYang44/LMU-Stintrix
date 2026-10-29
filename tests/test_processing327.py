"""Sparse scratch bytes, evidence-only lap facts and selected-lap handoff."""
import json,math,os,struct,subprocess,sys,tempfile,unittest,weakref
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Data(unittest.TestCase):
    def test_sparse_transitions_keep_wire_precision_failure_and_immediate_cleanup(self):
        from analysis_spool import DiskTable
        rows=[[1.2345678901234567,-0.,None,2**53],[1e-250,1e250,None,-12.],
            [None,None,None,None],[1.,2.,3.,4.],[True,False,None,5.]]
        expected=b''.join(struct.pack('<4d',*(math.nan if x is None else x for x in row)) for row in rows)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for nullable in (False,True):
                table=DiskTable(rows,4,t,nullable=nullable);table._file.seek(0);self.assertEqual(table._file.read(),expected)
                self.assertLess(math.copysign(1,table[0][1]),0)
                self.assertEqual(table[3],[1.,2.,3.,4.]);self.assertIsNone(table[0][2]) if nullable else self.assertTrue(math.isnan(table[0][2]))
                table._sealed=False
                with self.assertRaises((TypeError,struct.error)):table.append(['bad',None,1,2])
                with self.assertRaises(ValueError):table.append([1])
                self.assertEqual(len(table),len(rows));table.seal()
                with self.assertRaises(ValueError):table.append([1,2,None,4])
                file=table._file;ref=weakref.ref(table);del table
                self.assertIsNone(ref());self.assertTrue(file.closed,'Sparse packer must not retain its table in a cycle')

    def test_evo_summary_uses_export_evidence_and_loads_plain_packed_without_source_edits(self):
        from evo_lap_overview import load,summary
        from tests.test_processing325 import record
        from column_store import convert
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=record(root,'valid');before={p:p.read_bytes() for p in (folder/'inputs.csv',folder/'session.json')}
            result=load(root,folder);value=result['index'];s=result['summary']
            self.assertEqual(s['valid'],2);self.assertEqual(s['median'],(value['laps'][1]['time']+value['laps'][2]['time'])/2)
            self.assertEqual(s['fastest'],20.);self.assertEqual(s['std'],0.)
            different=json.loads(json.dumps(value));different['laps'][2]['time']=21.23456789012345
            self.assertGreater(summary(different)['std'],0)
            duplicate=json.loads(json.dumps(value));duplicate['laps'].append(duplicate['laps'][1].copy())
            self.assertEqual(summary(duplicate)['valid'],1)
            for row in duplicate['laps']:row['valid']=None
            self.assertEqual(summary(duplicate),dict(total=len(duplicate['laps']),valid=0,fastest=None,median=None,std=None))
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)
            self.assertTrue(convert(folder/'inputs.csv',replace=True)['converted']);self.assertEqual(load(root,folder)['summary'],s)
            foreign=Path(t)/'Logs/lmu';foreign.mkdir(parents=True);(foreign/'session.json').write_text('{"status":"complete"}','utf-8')
            with self.assertRaises(ValueError):load(root,foreign)
            with self.assertRaises(ValueError):load(Path(t),folder)
            import evo_laps
            original=evo_laps.index
            def changed(f):
                value=original(f);meta=json.loads((folder/'session.json').read_text('utf-8'));meta['changed']=True
                (folder/'session.json').write_text(json.dumps(meta),'utf-8');return value
            with patch('evo_laps.index',side_effect=changed):
                with self.assertRaises(OSError):load(root,folder)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_evo_lap_overview_filters_exact_handoff_export_and_failed_refresh(self):
        script=r'''
import sys,time,traceback,ctypes
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
from control_lap_pair import show as pair
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(.5);app.tree.selection_set(app.tree.get_children()[:1]);app.update_toolbar()
 app.review_menu.invoke('lap-overview');pump(.7);w=next(iter(app.evo_lap_windows.values()));c=w.lap_overview
 assert c['state']['result']['summary']['valid']==2 and len(c['state']['rows'])==4,c['state']
 folder=c['folder'];assert show(app,folder) is w;pump(.3)
 c['kind'].set('valid');c['populate']();assert len(c['state']['rows'])==2
 valid=list(c['table'].get_children());c['table'].selection_set(valid);pump(.1);assert c['buttons']['compare'].enabled
 c['buttons']['compare'].invoke();pump(.7);p=app.lap_pair_window;pc=p.pair_controls
 def chosen():return [pc['state']['laps'][k].get(pc['numbers'][k].get()) for k in ('A','B')]
 assert chosen()==[2,3] and pc['compare'].enabled,chosen()
 assert pair(app,app.data_path,selected=[(folder,3),(folder,2)]) is p;pump(.15);assert chosen()==[3,2]
 pair(app,app.data_path,selected=[(folder,999),(folder,2)]);pump(.15);assert chosen()==[None,2] and not pc['compare'].enabled
 p.destroy()
 with patch('control_evo_exports.filedialog.askdirectory',return_value=str(app.data_path/'exports')):
  c['buttons']['csv'].invoke();pump(.7)
 job=app.batch_job;assert not job.busy and job.states==['已完成','已完成'],job.errors
 assert [v['number'] for _,v in sorted(job.results.items())]==[2,3]
 job.window.destroy();c['kind'].set('all');c['populate']();c['table'].selection_set(('0',));pump(.1)
 assert not c['buttons']['csv'].enabled and not c['buttons']['compare'].enabled
 app.set_theme('light');app.toggle_language();w.geometry('900x700');pump(.5)
 assert 'Valid laps' in c['facts'].get() and 'Showing' in c['status'].get() and w.title()=='AC EVO · Lap overview'
 assert c['table'].labels['samples']=='Samples' and c['table'].labels['lap']=='Lap'
 for b in c['buttons'].values():assert b.winfo_rootx()+b.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1 and b.winfo_rooty()+b.winfo_height()<=w.winfo_rooty()+w.winfo_height()+1
 c['kind'].set('valid');c['populate']();c['table'].selection_set(c['table'].get_children());pump(.1)
 with patch('control_evo_lap_overview.offline_ready',return_value=False),patch('control_lap_pair.show',side_effect=AssertionError('Capture must prevent analysis')):c['buttons']['compare'].invoke()
 with patch('evo_lap_overview.load',side_effect=OSError('Source changed')):c['refresh']();pump(.4)
 assert c['state']['result'] is None and not c['table'].get_children() and not c['buttons']['csv'].enabled
 w.destroy();assert not app.evo_lap_windows
 try:pair(app,app.data_path,selected=[(folder,True),(folder,2)])
 except ValueError:pass
 else:raise AssertionError('Boolean lap accepted')
 assert not errors,errors;app.request_close();pump(.15)
print('EVO lap overview: valid statistics, reused window, filtered selection, exact A/B identities, CSV, language/theme and failed refresh OK')
'''
        from tests.test_processing325 import record
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=record(Path(t)/'Simulators/ac_evo','valid');before={p:p.read_bytes() for p in (folder/'session.json',folder/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            child=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(child.returncode,0,child.stdout+child.stderr)
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)


if __name__=='__main__':unittest.main()
