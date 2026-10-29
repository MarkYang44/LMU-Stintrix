"""Exact lossless wire compatibility and game-scoped full-library workflows."""
import hashlib,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def wire_values():
    return [[b'']*2048,[b'0.0']*2048,[str(i//100).encode() for i in range(2048)],
        [f'{i*.010001:.6f}'.encode() for i in range(2048)],
        [b'a'*n+b'x' for n in (0,1,126,127,128,129,255,256,16383,16384)]*3,
        ['中文,"A"\nB'.encode(),b'\x00',b'-0.000000',b'1.0000000000000002']*512,
        [bytes([i%256])*300+bytes([i//256]) for i in range(2048)]]


class Data(unittest.TestCase):
    def test_encoder_keeps_exact_v2_wire_bytes_and_edge_values(self):
        from column_store import _encode,_decode
        # Golden digests from the previously shipped v2 encoder. No alternative
        # compression, candidate omissions, numeric conversion or tie changes.
        expected=['1c04421d8f2b0848f787a3a4c2b5c444ff5f2e35766ea08cd9acda02c222fc4e',
            '6b4969d2040d2a9f76c5c42b80096e6ef6a789eff17ae6a9867f3d4ba9982eee',
            '1e0825680806518f1f202d98bddc88d7e518b076490b64faf7afc4bc3407fce7',
            '7e5df0befe23d531e0c6c398ccec611300fa214324973c7e0e14986766808f77',
            'ffad0b9eee6ca5528258d9306b9fe13a141c8f6b40c46e69f3ae429b24d558b5',
            '82b312655341f2096b0fb38a0f968db1a4647b4a202bb56a25fc9e5437567500',
            '1456ae822cde0ccb67f4c607a287caa04cb508dc6711645b31b19e654b603e39']
        self.assertEqual(len(expected),len(wire_values()))
        for values,digest in zip(wire_values(),expected):
            encoded=_encode(values)
            self.assertEqual(hashlib.sha256(encoded).hexdigest(),digest)
            self.assertEqual(_decode(encoded,len(values)),values)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_evo_full_library_is_scoped_capability_gated_and_keeps_browsing_context(self):
        script=r'''
import json,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
import control_library
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();assert app.simulator=='ac_evo';app.root.geometry('1200x850')
 app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(seconds=.4):
  end=time.monotonic()+seconds
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(1);app.review_menu.invoke('all');pump(.05)
 with patch('control_library.inventory',wraps=control_library.inventory) as read,patch('evo_laps.scan',side_effect=AssertionError('unexpected full sample scan')):
  app.review_menu.invoke('library');pump(.7);w=app.library();v=w.library
  assert read.call_count==1 and len(v.items)==2 and len(v.table.selection())==2
  assert v.root_path==app.data_path and 'layout' in v.table.columns and 'stable' not in v.table.columns
  assert all('GP'==v.table.rows[k][v.table.columns.index('layout')] for k in v.table.rows)
  actions={a.key:a for a in v.operations.menu.actions}
  assert all(not actions[k].visible() for k in ('reference','analyze','recover'))
  assert all(actions[k].visible() for k in ('compress','export','import','progress'))
  with patch('sessionlab.analyze_session') as analysis,patch('storage.recover_session') as recover,patch('reference.ReferenceLap.load') as ref:
   v.operations.reference();v.operations.analyze();v.operations.recover()
   analysis.assert_not_called();recover.assert_not_called();ref.assert_not_called()
  with patch('control_lap_pair.show') as pair:
   v.operations.menu.invoke('compare');pair.assert_called_once_with(v.app,app.data_path,[e['folder'] for e in v.selected_items()])
   pair.reset_mock();v.table.selection_set(v.table.get_children()[:1]);pump(.05)
   folder=v.selected_items()[0]['folder'];v.operations.same();pair.assert_called_once_with(v.app,app.data_path,[folder])
  with patch('control_library_actions.filedialog.askdirectory',return_value=str(app.data_path/'exports')),patch('control_batch.start') as start,patch('session_archive.export_session') as export:
   v.operations.format.set('7z');v.operations.export();worker=start.call_args.args[3]
   worker(v.selected_items()[0]['key']);assert export.call_args.args[0]==app.data_path and export.call_args.kwargs['format']=='7z'
  note=v.operations.note();c=note.note_controls;c['text'].insert('1.0','kept note');c['favorite'].set(True);assert c['save']();pump(.4)
  v.query.set('GP');v.search.flush();v.track.set('Nurburgring');v.filters_changed();chosen=v.table.selection()
  v.table.widths['layout']=201.125;app.set_theme('light');app.toggle_language();pump(.2)
  assert v.table.selection()==chosen and v.query.get()=='GP' and v.table.widths['layout']==201.125
  assert v.table.labels['layout']=='Layout';v.close();pump(.05)
  w=app.library(initial=[]);pump(.5);v=w.library
  assert v.query.get()=='GP' and v.track.get()=='Nurburgring' and v.table.selection()==chosen
  assert v.table.widths['layout']==201.125
  v.operations.same();pump(.6);pair=app.lap_pair_window.pair_controls
  assert pair['state']['events'][pair['events']['A'].get()]['folder']==folder
  assert pair['state']['laps']['A'];app.lap_pair_window.destroy();w.destroy()
 assert not errors,errors;app.request_close();pump(.2)
print('EVO full library: isolation, capabilities, exact selection, archive routing, notes and context OK')
'''
        from tests.test_evo_records310 import fixture
        from evo_laps import export
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            base=Path(t);game=base/'Simulators/ac_evo';a=fixture(game);b=game/'Logs/another';shutil.copytree(a,b)
            for folder in (a,b):export(folder)
            foreign=game/'Logs/foreign';foreign.mkdir();(foreign/'session.json').write_text('{"simulator_id":"lmu","track":"Foreign"}')
            other=base/'Logs/lmu';other.mkdir(parents=True);(other/'session.json').write_text('{"track":"LMU only"}')
            before={p:p.read_bytes() for folder in (a,b,foreign,other) for p in folder.iterdir() if p.name in ('session.json','inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for path,value in before.items():self.assertEqual(path.read_bytes(),value)
            notes=json.loads((game/'library_notes.json').read_text('utf-8'));self.assertTrue(any(v.get('favorite') and v.get('text')=='kept note' for v in notes.values()))


if __name__=='__main__':unittest.main()
