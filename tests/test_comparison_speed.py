"""Comparison reuse, source invalidation, and bounded shared scan behavior."""
import json,os,shutil,tempfile,threading,unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from tests import test_selected_laps as fixtures
ROOT=fixtures.ROOT


class Data(unittest.TestCase):
    def test_one_source_scan_and_cached_page_invalidate_on_source_assets_and_missing_output(self):
        import laps
        from lap_comparison import export_pair
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            root=Path(tmp);f=fixtures.SelectedLapTests().session(root);assets=root/'assets';assets.mkdir()
            for p in (ROOT/'src').glob('*.js'):shutil.copy2(p,assets/p.name)
            (assets/'tracks').mkdir();shutil.copy2(ROOT/'src/tracks/catalog.json',assets/'tracks/catalog.json')
            shutil.copy2(ROOT/'src/compare.html',assets/'compare.html');template=assets/'compare.html';selection=[(f,4),(f,1)]
            with patch('laps.extract_best',wraps=laps.extract_best) as read:
                result=export_pair(root,selection,template);self.assertEqual(read.call_count,1)
                stamp=Path(result['comparison']).stat().st_mtime_ns;self.assertEqual(export_pair(root,selection,template),result);self.assertEqual(read.call_count,1);self.assertEqual(Path(result['comparison']).stat().st_mtime_ns,stamp)
                path=f/'inputs.csv';s=path.stat();os.utime(path,ns=(s.st_atime_ns,s.st_mtime_ns+2000000));export_pair(root,selection,template);self.assertEqual(read.call_count,2)
                with (assets/'interface_theme.js').open('a') as stream:stream.write('\n')
                export_pair(root,selection,template);self.assertEqual(read.call_count,2)
                Path(result['comparison']).unlink();export_pair(root,selection,template);self.assertEqual(read.call_count,2)
            value=json.loads((f/'session.json').read_text());value['status']='recording';(f/'session.json').write_text(json.dumps(value))
            with self.assertRaises(ValueError):export_pair(root,selection,template)

    def test_parallel_inventory_read_is_shared_and_returned_rows_are_independent(self):
        from comparison_cache import scan
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            entered=threading.Event();gate=threading.Event();calls=[]
            def read():calls.append(1);entered.set();self.assertTrue(gate.wait(3));return dict(laps=[dict(number=1,time_s=100.123456789)])
            with ThreadPoolExecutor(2) as pool:
                a=pool.submit(scan,tmp,read);self.assertTrue(entered.wait(1));b=pool.submit(scan,tmp,read);gate.set();first=a.result(3);second=b.result(3)
            self.assertEqual(len(calls),1);first['laps'][0]['time_s']=0;self.assertEqual(second['laps'][0]['time_s'],100.123456789)

    def test_packed_file_change_invalidates_scan_even_when_logical_csv_stamp_is_unchanged(self):
        import laps
        from column_store import convert
        from telemetry_file import Path as ReadPath
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            f=fixtures.SelectedLapTests().session(tmp);convert(f/'inputs.csv',replace=True);p=f/'inputs.csv.stc';old=ReadPath(f/'inputs.csv').stat().st_mtime_ns
            with patch('laps.extract_best',wraps=laps.extract_best) as read:
                first=laps.complete_laps(f);laps.complete_laps(f);self.assertEqual(read.call_count,1)
                s=p.stat();os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns+2000000));self.assertEqual(ReadPath(f/'inputs.csv').stat().st_mtime_ns,old)
                self.assertEqual(laps.complete_laps(f),first);self.assertEqual(read.call_count,2)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    from tests import test_ui_efficiency as helpers
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def test_track_first_selection_clears_other_track_and_ignores_obsolete_scan(self):
        from control_lap_pair import show
        from tests.test_ui_polish57 import records,LAPS
        app,root,errors=self.app();items=records(root);items[-1]['track']='Fuji Speedway';jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            window=show(app,root);c=window.pair_controls;jobs.pop(0)[1](items,None)
            self.assertFalse(c['track'].get());self.assertFalse(jobs);self.assertEqual(c['event_boxes']['A'].state,'disabled')
            c['track'].set('monza');c['choose_track']();self.assertEqual(len(c['event_boxes']['A'].values),2);self.assertFalse(jobs)
            c['events']['A'].set(c['event_boxes']['A'].values[0]);c['scan']('A');old=jobs.pop(0)
            c['track'].set('fuji speedway');c['choose_track']();self.assertEqual(len(c['event_boxes']['A'].values),1);old[1](dict(laps=LAPS,session=items[0]),None)
            self.assertFalse(c['state']['laps']['A']);self.assertEqual(c['events']['A'].get(),'');self.assertFalse(c['compare'].enabled)
            for key in ('A','B'):
                c['events'][key].set(c['event_boxes'][key].values[0]);c['scan'](key);jobs.pop(0)[1](dict(laps=LAPS,session=items[-1]),None)
        app.set_theme('light');app.toggle_language();window.geometry('860x680');self.pump(app,.2)
        self.assertEqual(c['track_box'].display(''),'Choose circuit')
        self.assertIn('Fuji Speedway',c['events']['A'].get());self.assertEqual(c['track'].get(),'fuji speedway');self.assertEqual([c['state']['laps'][k][c['numbers'][k].get()] for k in ('A','B')],[1,2])
        self.assertLessEqual(c['track_box'].winfo_rootx()+c['track_box'].winfo_width(),window.winfo_rootx()+window.winfo_width());self.assertFalse(errors)
