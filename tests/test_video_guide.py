"""First-use navigation, recoverable mistakes and the actual extraction workflow."""
import copy
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class VideoGuideTests(unittest.TestCase):
    def window(self):
        from control_center import ControlCenter
        from control_video import show
        temp=tempfile.TemporaryDirectory(dir=ROOT/'_local');self.addCleanup(temp.cleanup)
        guard=patch('control_center.ROOT',Path(temp.name));guard.start();self.addCleanup(guard.stop)
        repair=patch.object(ControlCenter,'repair_windows_entry');repair.start();self.addCleanup(repair.stop)
        app=ControlCenter();self.addCleanup(app.close);window=show(app,Path(temp.name));errors=[]
        app.root.report_callback_exception=lambda *args:errors.append(args)
        self.pump(app);return app,window,window.video_wizard,errors,Path(temp.name)

    def pump(self,app,condition=None,seconds=15):
        until=time.monotonic()+seconds
        if condition is None:
            for _ in range(10):app.root.update();time.sleep(.01)
            return
        while time.monotonic()<until:
            app.root.update();time.sleep(.005)
            if condition():return
        self.fail('Guided workflow did not settle')

    def test_first_page_routes_to_missing_input_and_empty_layout_is_editable(self):
        app,window,w,errors,_=self.window()
        self.assertTrue(w.manual_body.winfo_manager())
        with patch.object(w,'choose') as choose:w.primary_action();choose.assert_called_once_with('video','video')
        w.tabs.select(2);self.pump(app);self.assertIn('修正',w.start.cget('text'))
        with patch.object(w,'choose') as choose:w.primary_action();choose.assert_called_once()
        self.pump(app);self.assertEqual(w.tabs.current,0);self.assertFalse(errors)
        self.assertIsNone(w.guide_job);self.assertIsNone(w.poll_job)

    @unittest.skipUnless(shutil.which('ffmpeg'),'Local video fixture')
    def test_novice_three_steps_click_calibrate_review_and_extract(self):
        from tests.test_video_analysis import fixture
        app,window,w,errors,folder=self.window();config=fixture(folder,3)
        with patch('control_video.filedialog.askopenfilename',return_value=config['video']):w.primary_action()
        self.pump(app,lambda:not w.busy);self.assertIsNotNone(w.image,w.status.get())
        for key,value in dict(track='Test circuit',layout='Full',length='300').items():w.fields[key].set(value)
        self.pump(app);w.primary_action();self.pump(app);self.assertEqual(w.tabs.current,1)
        self.assertEqual(w.range_issue()[0],'confirm')
        w.range_confirmed.set(True);w.thickness.set('8');self.pump(app)
        self.assertIn('1/3',w.guide_heading.get())
        def event(point):
            sx,sy=w.factors();return SimpleNamespace(x=round(point[0]*sx),y=round(point[1]*sy))
        for target in ('throttle','brake'):
            self.assertEqual(w.target.get(),target)
            for i,point in enumerate(config[target]['points']):
                w.press(event(point));self.pump(app)
                if i==0:self.assertIn('0%',w.guide_detail.get())
                if i==1:self.assertIn('100%',w.guide_detail.get())
        self.assertEqual(w.target.get(),'anchor');self.assertIn('KPH',w.guide_detail.get())
        box=config['anchor'];w.press(event(box[:2]));w.release(event(box[2:]));self.pump(app)
        self.assertIsNone(w.calibration_issue());w.primary_action();self.pump(app)
        self.assertEqual(w.tabs.current,2);self.assertEqual(w.start.cget('text'),'开始提取')
        self.assertFalse(w.advanced_body.winfo_manager());self.assertTrue(all('✓' in v.get() for v in w.review_values))
        w.primary_action();self.pump(app,lambda:not w.busy)
        self.assertIsNotNone(w.result,w.status.get());self.assertTrue(Path(w.result['report']).is_file())
        self.assertEqual(w.open.cget('state'),'normal');self.assertIn('报告已保存',w.result_note.get())
        self.assertFalse((folder/'Logs').exists());self.assertFalse(errors,errors)
        w.fields['end'].set('2.9');self.pump(app);self.assertFalse(w.range_confirmed.get())
        self.assertIn('修正',w.start.cget('text'));w.primary_action();self.assertEqual(w.tabs.current,1)
        self.assertEqual(len(w.geometry),3)

    def test_invalid_arc_stays_in_place_and_can_be_undone_without_losing_other_items(self):
        from PIL import Image
        app,window,w,errors,_=self.window();w.tabs.select(1);self.pump(app)
        w.media=dict(path='fixture.mp4',width=640,height=360,duration=30);w.image=Image.new('RGB',(640,360))
        w.geometry['anchor']=[10,10,50,40];w.zoom.set(1);w.preview_fit=False
        for point in ((100,100),(130,100),(105,100)):w.press(SimpleNamespace(x=point[0],y=point[1]))
        self.pump(app);self.assertEqual(w.target.get(),'throttle');self.assertIsNotNone(w.calibration_issue())
        w.undo_calibration();self.pump(app);self.assertEqual(len(w.clicks),2);self.assertEqual(w.geometry['anchor'],[10,10,50,40])
        before=copy.deepcopy(w.clicks);w.go_issue(('throttle',1,'继续标定'));self.assertEqual(w.clicks,before)
        self.assertFalse(errors,errors)

    def test_optional_sync_help_and_language_changes_keep_drafts(self):
        from control_video import MODES
        import i18n
        app,window,w,errors,_=self.window();w.marks.insert('1.0','T1 = 0:23.450')
        self.assertIsNone(w.mode_issue());w.mode.set(list(MODES)[2]);w.mode_changed();self.pump(app)
        self.assertEqual(w.mode_issue()[0],'telemetry');w.fields['telemetry'].set('same.lap.json')
        self.assertEqual(w.mode_issue()[0],'sync');w.sync.insert('1.0','0 = 0\n20 = 20');self.assertIsNone(w.mode_issue())
        w.show_help();self.pump(app);self.assertTrue(w.help_window.winfo_exists())
        w.show_help();w.help_window.destroy();w.mode.set(list(MODES)[0]);w.mode_changed();w.tabs.select(0)
        try:
            app.toggle_language();self.pump(app)
            self.assertEqual(w.start.cget('text'),'Next: lap and HUD setup')
            self.assertEqual(w.marks.get('1.0','end').strip(),'T1 = 0:23.450')
        finally:i18n.set_language('zh')
        self.assertFalse(errors,errors);self.assertIsNone(w.guide_job)
