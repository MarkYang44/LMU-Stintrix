"""Report opening, async isolation, full resolution and reader interaction regressions."""
import json,os,sys,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests import test_ui_efficiency as helpers
from report_images import ImageLoader,read_image,stamp


def png(path,size=(900,3600),color='#e8ece0'):
    from PIL import Image,ImageDraw
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);image=Image.new('RGB',size,color)
    draw=ImageDraw.Draw(image)
    for y in range(0,size[1],80):draw.text((30,y+20),'Report fixture / '+str(y),fill='#151515');draw.line((20,y,size[0]-20,y),fill='#839126')
    image.putpixel((size[0]-1,size[1]-1),(3,117,249));image.save(path);return image


def wait_image(loader):
    end=time.monotonic()+5
    while time.monotonic()<end:
        image,error=loader.poll()
        if error:raise OSError(error)
        if image is not None:return image
        time.sleep(.005)
    raise AssertionError('image worker timeout')


class Loader(unittest.TestCase):
    def test_cache_stamp_pixel_identity_and_replacement(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            path=Path(tmp)/'one.png';original=png(path,(100,300));loader=ImageLoader();self.addCleanup(loader.close)
            loader.request(path);image=wait_image(loader);self.assertEqual(image.tobytes(),original.tobytes());self.assertIs(loader.request(path),image)
            png(path,(101,301),'#ff0000');self.assertIsNone(loader.request(path));updated=wait_image(loader);self.assertEqual(updated.size,(101,301));self.assertEqual(len(loader.cache),1)
            path.unlink();self.assertEqual(updated.getpixel((0,0)),(255,0,0))
    def test_rapid_requests_only_load_running_and_latest(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            paths=[Path(tmp)/(str(i)+'.png') for i in range(5)]
            for p in paths:png(p,(100,300))
            gate=threading.Event();entered=threading.Event();calls=[];loader=ImageLoader();self.addCleanup(loader.close)
            def read(key):
                calls.append(key[0])
                if len(calls)==1:entered.set();gate.wait(4)
                return read_image(key)
            try:
                with patch('report_images.read_image',side_effect=read):
                    loader.request(paths[0]);self.assertTrue(entered.wait(1))
                    for p in paths[1:]:loader.request(p)
                    gate.set();self.assertIsNotNone(wait_image(loader));self.assertEqual(calls,[str(paths[0].resolve()),str(paths[-1].resolve())]);self.assertLessEqual(len(loader.cache),2)
            finally:gate.set()
    def test_memory_budget_errors_and_close_do_not_restart_worker(self):
        from PIL import Image
        loader=ImageLoader(limit=1000);self.addCleanup(loader.close)
        for i in range(4):loader.remember((str(i),0,0,0),Image.new('RGB',(100,100)))
        self.assertEqual(len(loader.cache),1)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            p=Path(tmp)/'broken.png';p.write_bytes(b'invalid');loader.request(p)
            with self.assertRaises(OSError):wait_image(loader)
            png(p,(50,50));loader.request(p);self.assertEqual(wait_image(loader).size,(50,50));loader.close();self.assertEqual(loader.poll(),(None,None));self.assertFalse(loader.cache)
    def test_image_changing_during_read_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            p=Path(tmp)/'one.png';png(p,(40,80));key=stamp(p)
            with patch('report_images.stamp',return_value=(*key[:2],0,0)):
                with self.assertRaisesRegex(OSError,'更新'):read_image(key)
    @unittest.skipUnless(os.name=='nt','Windows raster')
    def test_explicit_regeneration_bypasses_cache_and_backs_up_old_bytes(self):
        from tests.test_race_images import RaceImageTests,generate
        fixture=RaceImageTests();fixture.setUp();self.addCleanup(fixture.tearDown);folder=fixture.folder();receipt=generate(folder,car_directory=fixture.root/'empty')
        before={name:(folder/name).read_bytes() for name in receipt['files']};raw={name:(folder/name).read_bytes() for name in ('inputs.csv','session.json')}
        from race_model import build_model
        with patch('race_report.build_model',wraps=build_model) as build:generate(folder,car_directory=fixture.root/'empty',force=True);build.assert_called_once()
        backups=list((folder/'_report_history').iterdir());self.assertEqual(len(backups),1)
        for name,data in before.items():self.assertEqual((backups[0]/name).read_bytes(),data)
        for name,data in raw.items():self.assertEqual((folder/name).read_bytes(),data)
        with patch('race_report.pages',side_effect=OSError('render fixture')):
            with self.assertRaises(OSError):generate(folder,car_directory=fixture.root/'empty',force=True)
        for name in ('圈速单.png','比赛日志.png'):self.assertEqual((folder/name).read_bytes(),before[name])
        self.assertEqual(len(list((folder/'_report_history').iterdir())),2)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def reports(self,root,name='one'):
        folder=root/'data/Logs'/name
        png(folder/'圈速单.png');png(folder/'比赛日志.png',(900,6000),'#f0e0e0');return folder
    def viewer(self,app,folder,name='圈速单.png'):
        from control_report_images import show
        w=show(app,folder,name);self.pump(app,.3);return w,w.report_viewer
    def test_existing_files_bypass_generation_and_system_viewer_and_preserve_bytes(self):
        app,root,errors=self.app();f=self.reports(root);before={p:p.read_bytes() for p in f.iterdir()}
        app.with_selection=lambda action:action([dict(folder=str(f))])
        with patch('race_report.generate') as generate,patch('control_report_images.os.startfile') as opened:
            app.report('圈速单.png');self.pump(app,.3);c=app.report_image_viewer;self.assertIsNotNone(c.viewport.photo);self.assertEqual(c.viewport.mode,'width');c.buttons['比赛日志.png'].invoke();self.pump(app,.2);self.assertEqual(c.viewport.image.size,(900,6000));generate.assert_not_called();opened.assert_not_called()
        for path,raw in before.items():self.assertEqual(path.read_bytes(),raw)
        self.assertFalse(errors)
    def test_reading_is_independent_of_busy_report_workers_and_lock(self):
        from reporting import _lock as report_lock
        app,root,errors=self.app();f=self.reports(root);gate=threading.Event();entered=threading.Event()
        def blocking():
            with report_lock:entered.set();gate.wait(4)
        try:
            app.run_background(blocking,lambda *_:None);app.run_background(lambda:gate.wait(4),lambda *_:None);self.assertTrue(entered.wait(1));w,c=self.viewer(app,f);self.assertIsNotNone(c.viewport.photo);self.assertTrue(app.tasks.busy)
        finally:gate.set();self.pump(app,.15)
        self.assertFalse(errors)
    def test_switch_reuses_window_restores_each_pose_and_singleton_reopen_cache(self):
        from control_report_images import show
        app,root,errors=self.app();f=self.reports(root);w,c=self.viewer(app,f);v=c.viewport;v.fit('one');v.pan(dy=-650);self.pump(app,.15);pose=v.snapshot()
        c.switch(1);self.pump(app,.2);v.pan(dy=-1400);self.pump(app,.15);other=v.snapshot();self.assertIs(show(app,f,'圈速单.png'),w);self.pump(app,.15);self.assertEqual(v.snapshot(),pose)
        c.switch(1);self.pump(app,.15);self.assertEqual(v.snapshot(),other);loader=app.report_image_loader;w.destroy()
        with patch('report_images.read_image',side_effect=AssertionError('cached image must not decode again')):w,c=self.viewer(app,f,'比赛日志.png');self.assertIs(app.report_image_loader,loader);self.assertIsNotNone(c.viewport.photo)
        self.assertFalse(errors)
    def test_zoom_is_pointer_anchored_tiles_are_bounded_and_scroll_reaches_both_ends(self):
        app,root,errors=self.app();f=self.reports(root);w,c=self.viewer(app,f);v=c.viewport;v.fit('one');v.zoom(2);v.pan(dx=-300,dy=-1000);self.pump(app,.15);x,y=400,240;before=[(p-o)/v.scale for p,o in zip((x,y),v.offset)]
        v.zoom(1.2,x,y);after=[(p-o)/v.scale for p,o in zip((x,y),v.offset)]
        for a,b in zip(before,after):self.assertAlmostEqual(a,b)
        import math
        # Cropping rounds outwards by at most two source pixels, so the
        # permitted viewport overscan grows with the actual zoom scale.
        v.zoom(6);self.pump(app,.3);overscan=2*math.ceil(v.scale);self.assertLessEqual(v.photo.width(),v.canvas.winfo_width()+overscan);self.assertLessEqual(v.photo.height(),v.canvas.winfo_height()+overscan)
        v.edge(True);self.pump(app,.15);self.assertAlmostEqual(v.vbar.get()[1],1.,places=4);v.edge();self.pump(app,.15);self.assertAlmostEqual(v.vbar.get()[0],0.,places=4)
        self.assertEqual(v.image.getpixel((899,3599)),(3,117,249));self.assertFalse(errors)
    def test_missing_reports_generate_once_and_switch_to_requested_report(self):
        app,root,errors=self.app();folder=root/'data/Logs/missing';folder.mkdir(parents=True);jobs=[]
        def queued(work,done):jobs.append((work,done))
        with patch.object(app,'run_background',side_effect=queued):
            w,c=self.viewer(app,folder);c.switch(1);self.assertEqual(len(jobs),1);self.assertTrue(c.feedback.tasks);png(folder/'比赛日志.png',(900,6000));png(folder/'圈速单.png');jobs[0][1]({},None);self.pump(app,.3)
        self.assertEqual(c.name,'比赛日志.png');self.assertEqual(c.viewport.image.size,(900,6000));self.assertFalse(c.feedback.tasks);self.assertFalse(errors)
    def test_no_completed_lap_does_not_loop_and_generate_failure_is_retryable(self):
        app,root,errors=self.app();f=root/'data/Logs/partial';f.mkdir(parents=True);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            w,c=self.viewer(app,f);png(f/'比赛日志.png');jobs[0][1]({},None);self.pump(app,.2);self.assertIsNone(c.viewport.image);self.assertIn('无完成圈',c.status.get());self.assertEqual(len(jobs),1);c.switch(1);self.pump(app,.2);old=c.viewport.image;c.regenerate();self.assertEqual(len(jobs),2)
            with patch('race_report.generate') as generate:jobs[-1][0]();generate.assert_called_once_with(f,force=True)
            jobs[-1][1](None,OSError('fixture'));self.assertIs(c.viewport.image,old);self.assertTrue(c.buttons['generate'].enabled);self.assertIn('已有文件保留',c.status.get())
        self.assertFalse(errors)
    def test_latest_missing_event_waits_without_queueing_every_intermediate_event(self):
        app,root,errors=self.app();folders=[root/'data/Logs'/str(i) for i in range(3)]
        for folder in folders:folder.mkdir(parents=True)
        jobs=[]
        from control_report_images import show
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            w,c=self.viewer(app,folders[0]);show(app,folders[1],'圈速单.png');show(app,folders[2],'圈速单.png');self.assertEqual(len(jobs),1);jobs[0][1]({},None);self.assertEqual(len(jobs),2)
            with patch('race_report.generate') as generate:jobs[1][0]();generate.assert_called_once_with(folders[2])
            png(folders[2]/'圈速单.png');jobs[1][1]({},None);self.pump(app,.2);self.assertIsNotNone(c.viewport.photo)
        self.assertFalse(errors)
    def test_read_error_reload_and_system_fallback_preserve_current_record(self):
        app,root,errors=self.app();f=self.reports(root);(f/'圈速单.png').write_bytes(b'broken');w,c=self.viewer(app,f);self.assertIsNone(c.viewport.image);self.assertTrue(c.buttons['reload'].enabled);self.assertIn('读取失败',c.status.get())
        png(f/'圈速单.png');c.reread();self.pump(app,.25);self.assertIsNotNone(c.viewport.photo)
        with patch('report_images.read_image',wraps=read_image) as read:c.reread();self.pump(app,.25);self.assertEqual(read.call_count,1)
        with patch('control_report_images.os.startfile',side_effect=OSError('viewer fixture')):c.open_system();self.assertIsNotNone(c.viewport.image);self.assertIn('内置查看器',c.status.get())
        (f/'比赛日志.png').unlink()
        with patch('control_report_images.stamp',side_effect=PermissionError('read fixture')):c.open(f,'比赛日志.png')
        self.assertIsNone(c.viewport.image);self.assertIsNone(c.key);self.assertFalse(errors)
    def test_close_during_read_or_generation_and_shutdown_are_safe(self):
        from control_report_images import show
        app,root,errors=self.app();f=self.reports(root);gate=threading.Event();entered=threading.Event()
        def read(key):entered.set();gate.wait(4);return read_image(key)
        try:
            with patch('report_images.read_image',side_effect=read):
                w=show(app,f,'圈速单.png');self.assertTrue(entered.wait(1));w.destroy();w=show(app,f,'比赛日志.png');gate.set();self.pump(app,.35);self.assertEqual(w.report_viewer.viewport.image.size,(900,6000))
        finally:gate.set()
        w.destroy();jobs=[];missing=root/'data/Logs/missing';missing.mkdir()
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)):w,c=self.viewer(app,missing);w.destroy();jobs[0](None,OSError('closed fixture'))
        loader=app.report_image_loader;app.close();self.assertTrue(loader.closed);self.assertFalse(loader.cache);self.assertFalse(errors)
        # Cleanup helper calls close() again; no-op after an already destroyed root.
        app.close=lambda:None
    def test_language_theme_minimum_window_and_main_selection_survive(self):
        from control_theme import T
        from i18n import tr
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.4);app.search.set('Fuji');app.populate();chosen=app.tree.get_children()[0];app.tree.selection_set((chosen,));f=self.reports(root);w,c=self.viewer(app,f);w.geometry('780x560');c.viewport.pan(dy=-500);self.pump(app,.15);pose=c.viewport.snapshot();app.set_theme('light');app.toggle_language();self.pump(app,.3)
        self.assertEqual(c.viewport.snapshot(),pose);self.assertEqual(c.viewport.canvas.cget('bg'),T.FIELD);self.assertEqual(app.search.get(),'Fuji');self.assertEqual(app.tree.selection(),(chosen,));self.assertGreater(c.viewport.canvas.winfo_height(),120)
        for b in c.buttons.values():
            self.assertGreater(b.winfo_width(),b.font.measure(tr(b.label))+15);self.assertGreaterEqual(b.winfo_rootx(),w.winfo_rootx());self.assertLessEqual(b.winfo_rootx()+b.winfo_width(),w.winfo_rootx()+w.winfo_width()+1);self.assertLess(b.winfo_rooty()+b.winfo_height(),c.viewport.winfo_rooty()+1)
        self.assertIn('Report images',w.title());self.assertFalse(errors)
    def test_recent_and_podium_buttons_use_same_viewer_and_keep_html_action(self):
        from tests.test_podium_records import PodiumTests
        from control_recent_session import update
        from report_state import remember
        from control_widgets import Pill
        app,root,errors=self.app();folder=PodiumTests().session(root,'podium');png(folder/'圈速单.png');png(folder/'比赛日志.png');(folder/'review.html').write_text('fixture')
        app.recent.folder=folder;app.recent.meta=json.loads((folder/'session.json').read_text('utf-8'));remember(folder,dict(state='ready',steps=dict(review=dict(state='ready'),images=dict(state='ready')),updated_utc='fixture'));update(app);self.pump(app,.15)
        with patch('control_report_images.show') as show,patch('control_recent_session.os.startfile') as external:
            app.recent_widgets[1]['laps'].invoke();show.assert_called_once_with(app,folder,'圈速单.png');app.recent_widgets[1]['review'].invoke();external.assert_called_once_with(folder/'review.html')
        def walk(w):
            for child in w.winfo_children():yield child;yield from walk(child)
        app.show_page(6);self.pump(app,.2);next(w for w in walk(app.content) if isinstance(w,Pill) and w.label=='领奖台记录').command();self.pump(app,.5)
        with patch('control_report_images.show') as show:
            next(w for w in walk(app.content) if isinstance(w,Pill) and w.label=='查看圈速单').command();self.assertEqual(show.call_args.args,(app,str(folder),'圈速单.png'))
            next(w for w in walk(app.content) if isinstance(w,Pill) and w.label=='查看比赛日志').command();self.assertEqual(show.call_args.args,(app,str(folder),'比赛日志.png'))
        self.assertFalse(errors)
    def test_shutdown_waits_for_report_write_after_reader_is_closed(self):
        from control_report_images import show
        app,root,errors=self.app();folder=root/'Logs/missing';folder.mkdir(parents=True);gate=threading.Event();entered=threading.Event();finished=threading.Event()
        def render(folder):entered.set();gate.wait(4);png(folder/'比赛日志.png');finished.set()
        try:
            with patch('race_report.generate',side_effect=render):
                w=show(app,folder,'比赛日志.png');self.assertTrue(entered.wait(1));w.destroy();app.close();self.assertTrue(app.tasks.busy);self.assertTrue(app.root.winfo_exists());gate.set()
                end=time.monotonic()+4
                while time.monotonic()<end:
                    try:
                        if not app.root.winfo_exists():break
                        app.root.update();time.sleep(.005)
                    except __import__('tkinter').TclError:break
                self.assertTrue(finished.is_set());self.assertTrue((folder/'比赛日志.png').is_file());self.assertFalse(errors)
        finally:gate.set();app.close=lambda:None
    def test_outside_path_rejected_without_opening_or_generating(self):
        from control_report_images import show
        app,root,errors=self.app()
        for folder,name in [(root,'圈速单.png'),(app.data_path,'圈速单.png'),(root/'data/Logs/one','../private.png')]:
            with self.assertRaises(ValueError):show(app,folder,name)
        self.assertIsNone(getattr(app,'report_image_viewer',None));self.assertFalse(errors)

if __name__=='__main__':unittest.main()
