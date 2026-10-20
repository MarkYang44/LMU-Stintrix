"""Regressions for preserved drafts, real PTS sampling and recent results."""
import json,os,shutil,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from video_results import header,inventory,write_summary


def result():
    return dict(format='stintrix.video-curves',version=1,video_file='clip.mp4',identity=dict(track='Monza',track_layout='Full'),
                quality=dict(actual_sample_hz=30,requested_sample_hz=30),created_utc='20261020T120000Z',rows=[dict(lap_time_s=0,throttle=0)])


class ResultTests(unittest.TestCase):
    def test_old_header_never_scans_large_sample_array(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as folder:
            path=Path(folder)/'curve.json';prefix=json.dumps({k:v for k,v in result().items() if k!='rows'})[:-1]
            path.write_text(prefix+',"rows":['+'0,'*1000000+'0]}',encoding='utf-8')
            value=header(path);self.assertEqual(value['video_file'],'clip.mp4');self.assertNotIn('rows',value)
            # If the body were parsed, invalid JSON here would fail. Header-only
            # discovery deliberately stops before it; opening the data still validates it.
            path.write_text(prefix+',"rows":[not parsed',encoding='utf-8');self.assertEqual(header(path)['identity']['track'],'Monza')
    def test_catalog_is_read_only_and_skips_invalid_results(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            root=Path(tmp);folder=root/'VideoCurves'/'20261020T120000Z-id';folder.mkdir(parents=True)
            (folder/'curve.json').write_text(json.dumps(result()),encoding='utf-8');(folder/'report.html').write_text('report')
            before=(folder/'curve.json').read_bytes();rows=inventory(root)
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['reports'],{'raw':str(folder/'report.html')})
            self.assertEqual((folder/'curve.json').read_bytes(),before);self.assertEqual(len(list(folder.iterdir())),2)
            write_summary(folder,result());self.assertNotIn('rows',json.loads((folder/'video_result_summary.json').read_text()))
            (folder/'report_120hz.html').write_text('smooth');self.assertIn('smooth',inventory(root)[0]['reports'])
            pending=root/'VideoCurves'/'pending-still-writing';pending.mkdir();(pending/'curve.json').write_text(json.dumps(result()));(pending/'report.html').write_text('not yet published');self.assertEqual(len(inventory(root)),1)
            broken=root/'VideoCurves'/'zz-invalid';broken.mkdir();(broken/'curve.json').write_text('{}');self.assertEqual(len(inventory(root)),1)
    def test_oversized_header_is_rejected_without_reading_whole_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            path=Path(tmp)/'curve.json';path.write_text('{"video_file":"'+'x'*200000+'"}',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'结果头过大'):header(path)

    def test_catalog_rejects_paths_outside_root(self):
        from video_results import file_in
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            root=Path(tmp);(root/'report.html').write_text('keep');self.assertIsNone(file_in(root,'report.html',root))
    def test_actual_frequency_uses_real_span(self):
        from video_sampling import measured
        q=measured([dict(video_pts_s=t) for t in [10,10.1,10.2]],30)
        self.assertAlmostEqual(q['actual_sample_hz'],10);self.assertEqual(q['requested_sample_hz'],30)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg')
class SamplingTests(unittest.TestCase):
    def clip(self,folder,rate,timebase,select=None):
        target=Path(folder)/'clip.mp4';cmd=['ffmpeg','-v','error','-y','-f','lavfi','-i',f'color=s=64x64:r={rate}:d=2']
        if select:cmd+=['-vf',select,'-fps_mode','passthrough']
        cmd+=['-c:v','libx264','-video_track_timescale',str(timebase),str(target)]
        subprocess.run(cmd,check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));return target
    def test_timebases_cfr_low_fps_and_vfr_keep_only_original_pts(self):
        from video_media import frames
        for rate,timebase,hz,select,expected in [(60,16000,30,None,60),(60,90000,30,None,60),(5,16000,30,None,10),('30000/1001',90000,20,None,40),(60,16000,30,r'select=not(mod(n\,2))+between(n\,61\,90)',None)]:
            with self.subTest(rate=rate,timebase=timebase,select=select),tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
                path=self.clip(tmp,rate,timebase,select);stamps=[t for t,_ in frames(path,0,2,hz,(0,0,40,40))]
                raw=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)]))
                source=[float(f['best_effort_timestamp_time']) for f in raw['frames']]
                self.assertEqual(len(set(stamps)),len(stamps));self.assertTrue(all(any(abs(t-v)<2e-6 for v in source) for t in stamps))
                if expected:self.assertLessEqual(abs(len(stamps)-expected),1)
                self.assertTrue(all(b>a for a,b in zip(stamps,stamps[1:])))


@unittest.skipUnless(os.name=='nt','Native Tk')
class DraftTests(unittest.TestCase):
    def test_language_rebuild_preserves_all_modules_and_inactive_page(self):
        import control_center,i18n,tkinter as tk
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp,patch('control_center.ROOT',Path(tmp)):
            app=control_center.ControlCenter();app.root.withdraw()
            try:
                app.show_page(2);forms=app.pages.pages[2].forms
                values={'sampling':{'fixed_hz':'777','min_hz':'invalid draft','mode':'dynamic'},'vehicle':{'reserve_l':'8.5'},'endurance':{'temp_change_c':'3.25'}}
                for module,fields in values.items():
                    for key,value in fields.items():forms[module][key].set(value)
                app.show_page(0);app.toggle_language();app.toggle_language();app.show_page(2)
                for module,fields in values.items():
                    for key,value in fields.items():self.assertEqual(app.pages.pages[2].forms[module][key].get(),value)
                self.assertFalse((Path(tmp)/'settings.json').exists())
            finally:
                app.close()
                while True:
                    try:
                        if not app.root.winfo_exists():break
                        app.root.update();time.sleep(.01)
                    except tk.TclError:break
                i18n.set_language('zh')
    def test_saving_clears_draft_and_preserves_preferences(self):
        import control_center,control_settings,tkinter as tk
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp,patch('control_center.ROOT',Path(tmp)),patch('control_settings.ROOT',Path(tmp)):
            app=control_center.ControlCenter();app.root.withdraw()
            try:
                app.show_page(2);app.pages.pages[2].forms['sampling']['fixed_hz'].set('777');app.toggle_language();app.show_page(2)
                def descendants(widget):
                    for child in widget.winfo_children():yield child;yield from descendants(child)
                button=next(w for w in descendants(app.pages.pages[2].frame) if getattr(w,'label',None)=='应用并保存')
                button.command();self.assertNotIn('sampling',app.form_drafts)
                self.assertEqual(json.loads((Path(tmp)/'settings.json').read_text())['fixed_hz'],777)
                app.toggle_language();self.assertEqual(float(app.pages.pages[2].forms['sampling']['fixed_hz'].get()),777)
            finally:
                app.close()
                while True:
                    try:
                        if not app.root.winfo_exists():break
                        app.root.update();time.sleep(.01)
                    except tk.TclError:break
                import i18n;i18n.set_language('zh')

    def test_recent_results_open_without_video_and_select_available_reports(self):
        from tests.test_video_motion import VideoMotionTests
        from control_video_results import show
        fixtures=VideoMotionTests();fixtures.addCleanup=self.addCleanup
        app,window,w,errors=fixtures.window()
        folder=w.root/'VideoCurves'/'20261020T120000Z-id';folder.mkdir(parents=True)
        (folder/'curve.json').write_text(json.dumps(result()));(folder/'report.html').write_text('raw');(folder/'report_120hz.html').write_text('smooth')
        recent=show(app,w.root);fixtures.pump(app,.4)
        self.assertEqual(len(recent.results_state['items']),1);self.assertTrue(recent.results_buttons['raw'].enabled);self.assertTrue(recent.results_buttons['smooth'].enabled)
        with patch('control_video_results.os.startfile') as open_file:
            recent.results_buttons['smooth'].command();self.assertTrue(open_file.call_args.args[0].endswith('report_120hz.html'))
        self.assertIsNone(w.media);self.assertFalse(errors)
