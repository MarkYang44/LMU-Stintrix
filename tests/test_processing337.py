"""Unchanged LZX receipts and explicit EVO multi-view reuse keep source evidence."""
import json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_compression_reuses_only_current_identity_physical_size_and_bounded_receipt(self):
        import session_compression as c
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);(folder/'session.json').write_text('{"status":"complete"}','utf-8')
            files=[folder/'a.json',folder/'b.html'];payload=b'1.2345678901234567,-0.0,null\r\n'*3000
            for p in files:p.write_bytes(payload)
            sizes={str(p):4096 for p in files}
            with patch.object(c,'ntfs',return_value=True),patch.object(c,'physical_size',side_effect=lambda p:sizes[str(p)]),patch.object(c.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as spawn:
                result=c.compress(folder);self.assertEqual(spawn.call_count,2);self.assertEqual(result['version'],3)
                spawn.reset_mock();second=c.compress(folder);self.assertEqual(second['reused_files'],2);spawn.assert_not_called();self.assertEqual(second['saved_bytes'],0)
                stat=files[0].stat();os.utime(files[0],ns=(stat.st_atime_ns,stat.st_mtime_ns+1000000))
                spawn.reset_mock();self.assertEqual(c.compress(folder)['reused_files'],1);self.assertEqual(spawn.call_count,1)
                sizes[str(files[1])]+=4096;spawn.reset_mock();self.assertEqual(c.compress(folder)['reused_files'],1);self.assertEqual(spawn.call_count,1)
                # Replacing a file with identical bytes/time still changes its physical identity.
                old=files[0].stat();replacement=folder/'replacement.pending';replacement.write_bytes(payload);os.utime(replacement,ns=(old.st_atime_ns,old.st_mtime_ns));replacement.replace(files[0])
                spawn.reset_mock();self.assertEqual(c.compress(folder)['reused_files'],1);self.assertEqual(spawn.call_count,1)
                receipt=folder/'storage_compression.json';receipt.write_text('{broken','utf-8')
                spawn.reset_mock();self.assertEqual(c.compress(folder)['reused_files'],0);self.assertEqual(spawn.call_count,2)
                value=json.loads(receipt.read_text('utf-8'));value['version']=2;receipt.write_text(json.dumps(value),'utf-8')
                spawn.reset_mock();self.assertEqual(c.compress(folder)['reused_files'],0);self.assertEqual(spawn.call_count,2)
                # A change after the first stat must not be reported as reusable.
                moved=[False]
                def changing(p):
                    if p==files[0] and not moved[0]:
                        moved[0]=True;s=p.stat();os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns+1000000))
                    return sizes[str(p)]
                with patch.object(c,'physical_size',side_effect=changing):
                    result=c.compress(folder);self.assertEqual(len(result['errors']),1);self.assertIn('变化',result['errors'][0]['error'])
                self.assertFalse((folder/c.LOCK).exists())
                for p in files:self.assertEqual(p.read_bytes(),payload)
                receipt.write_bytes(b' '*(1048576+1))
                with patch.object(c.json,'loads',side_effect=AssertionError('Oversized receipt must not decode')):self.assertEqual(c._previous(folder),{})

    def test_multi_context_is_game_scoped_bounded_and_opens_without_analysis(self):
        from control_evo_compare import remember_multi,last_multi,open_multi
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';pages=root/'LapComparisons';pages.mkdir(parents=True);page=pages/'EVO_Multi_fixture.html';page.write_text('saved complete comparison','utf-8')
            app=SimpleNamespace(data_path=root,closing=False,status=Mock(),lap_pair_context={'unchanged':'A/B'})
            remember_multi(app,root,page,6);self.assertEqual(last_multi(app),dict(page=str(page.resolve()),count=6));self.assertEqual(app.lap_pair_context,{'unchanged':'A/B'})
            self.assertEqual(app.evo_multi_context,{str(root.resolve()):dict(page=str(page.resolve()),count=6)})
            with patch('control_evo_compare.os.startfile') as opened,patch('evo_laps.index',side_effect=AssertionError('Do not analyze saved page')):
                self.assertTrue(open_multi(app));opened.assert_called_once_with(str(page.resolve()))
            for count in (True,2,7):
                with self.assertRaises(ValueError):remember_multi(app,root,page,count)
            outside=Path(t)/'EVO_Multi_other.html';outside.write_text('other game','utf-8')
            with self.assertRaises(ValueError):remember_multi(app,root,outside,3)
            context=app.evo_multi_context;app.data_path=Path(t)/'lmu';self.assertIsNone(last_multi(app));app.data_path=root
            context[str(root.resolve())]['page']=str(outside);self.assertIsNone(last_multi(app))
            remember_multi(app,root,page,3);page.rename(page.with_suffix('.old'));self.assertIsNone(last_multi(app))
            with patch('control_evo_compare.os.startfile') as opened:self.assertFalse(open_multi(app));opened.assert_not_called()


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_overview_remembers_multi_and_reopens_from_review_and_manager_without_reads(self):
        script=r'''
import hashlib,sys,time,traceback
from pathlib import Path
from copy import deepcopy
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
from control_evo_compare import last_multi,open_multi
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.withdraw();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(.8);action=next(a for a in app.review_menu.actions if a.key=='multi-reopen');assert not action.enabled()
 app.lap_pair_context={str(app.data_path.resolve()):dict(query='keep A/B',result='previous-pair')};ab=deepcopy(app.lap_pair_context)
 w=show(app,app.data_path/'Logs/evo');pump(.5);c=w.lap_overview
 with patch('control_evo_compare.os.startfile') as opened:
  c['buttons']['best-many'].invoke();c['buttons']['compare'].invoke();pump(.8);assert opened.call_count==1 and app.lap_curve_jobs==0
 item=last_multi(app);assert item and item['count']==6 and app.lap_pair_context==ab
 page=Path(item['page']);before=(page.read_bytes(),page.stat().st_mtime_ns);w.destroy()
 app.show_page(0);pump(.2);app.show_page(1);pump(.6);action=next(a for a in app.review_menu.actions if a.key=='multi-reopen');assert action.enabled()
 app.tree.selection_set(app.tree.get_children());selected=app.tree.selection()
 with patch('evo_laps.index',side_effect=AssertionError('Reopen must not scan laps')),patch('evo_comparison.export_many',side_effect=AssertionError('Reopen must not regenerate')),patch('control_evo_compare.os.startfile') as opened:
  app.lap_curve_jobs=1;app.review_menu.invoke('multi-reopen');assert opened.call_count==1 and app.lap_curve_jobs==1;app.lap_curve_jobs=0
  assert app.tree.selection()==selected and app.lap_pair_context==ab
 window=app.library([app.data_path/'Logs/evo']);pump(.6);view=window.library;ops=view.operations
 app.set_theme('light');app.toggle_language();pump(.3);window.geometry('1000x740');pump(.1)
 action=next(a for a in ops.menu.actions if a.key=='multi-reopen');assert action.visible() and action.enabled()
 with patch('evo_laps.index',side_effect=AssertionError('Do not scan')),patch('evo_comparison.export_many',side_effect=AssertionError('Do not regenerate')),patch('control_evo_compare.os.startfile') as opened:
  ops.menu.toggle();pump(.15);ops.menu.hover('multi-reopen');pump(.1)
  assert ops.menu.popup.winfo_rootx()+ops.menu.popup.winfo_width()<=window.winfo_rootx()+window.winfo_width()+1
  ops.menu.invoke('multi-reopen');assert opened.call_count==1 and app.lap_pair_context==ab
 assert (page.read_bytes(),page.stat().st_mtime_ns)==before
 moved=page.with_suffix('.old.html');page.rename(moved);assert not action.enabled()
 with patch('control_evo_compare.os.startfile') as opened:assert not open_multi(app);opened.assert_not_called();assert 'moved' in app.status.get()
 moved.rename(page);window.destroy();assert not errors,errors;app.request_close();pump(.2)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=7);before={p:p.read_bytes() for p in (folder/'session.json',folder/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
