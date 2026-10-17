"""Native video motion contracts: interruption, exact geometry and zero idle ticks."""
import copy
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class VideoMotionTests(unittest.TestCase):
    def pump(self,app,seconds=.35):
        end=time.monotonic()+seconds
        while time.monotonic()<end:app.root.update();time.sleep(.005)

    def window(self):
        from control_center import ControlCenter
        from control_video import show
        temp=tempfile.TemporaryDirectory(dir=ROOT/'_local');self.addCleanup(temp.cleanup)
        guard=patch('control_center.ROOT',Path(temp.name));guard.start();self.addCleanup(guard.stop)
        app=ControlCenter();self.addCleanup(app.close)
        window=show(app,Path(temp.name));errors=[];app.root.report_callback_exception=lambda *args:errors.append(args)
        return app,window,window.video_wizard,errors

    def test_rapid_steps_retarget_keep_drafts_and_stop_at_latest_page(self):
        with patch('control_motion.system_motion',return_value=True):
            app,window,w,errors=self.window();self.pump(app)
            w.fields['track'].set('draft');w.marks.insert('1.0','T1 = 10')
            for index in (2,0,1,2,0):w.tabs.select(index);self.pump(app,.025)
            self.pump(app)
            self.assertEqual(w.tabs.current,0);self.assertEqual(w.tabs.offset,0)
            self.assertEqual(w.fields['track'].get(),'draft');self.assertEqual(w.marks.get('1.0','end').strip(),'T1 = 10')
            self.assertFalse(w.tabs.motion.jobs);self.assertFalse(w.tabs.indicator.motion.jobs);self.assertFalse(errors)

    def test_keyboard_and_reduced_motion_do_not_schedule_page_motion(self):
        from control_motion import keyboard_action
        with patch('control_motion.system_motion',return_value=True):
            app,window,w,errors=self.window();self.pump(app)
            keyboard_action(w.tabs,lambda:w.tabs.select(2))
            self.assertEqual(w.tabs.offset,0);self.assertFalse(w.tabs.motion.jobs);self.assertFalse(w.tabs.indicator.motion.jobs)
        with patch.dict(os.environ,{'LMU_STINTRIX_REDUCED_MOTION':'1'}):
            w.tabs.select(0);self.assertEqual(w.tabs.offset,0);self.assertFalse(w.tabs.motion.jobs)
            w.bar['value']=70;self.assertEqual(w.bar.value,70);self.assertFalse(w.bar.motion.jobs)
        self.assertFalse(errors)

    def test_progress_never_exceeds_reported_value_or_loops_when_idle(self):
        with patch('control_motion.system_motion',return_value=True):
            app,window,w,errors=self.window();self.pump(app)
            for value in (10,45,80):
                w.bar['value']=value;self.pump(app,.03);self.assertLessEqual(w.bar.value,value)
            self.pump(app);self.assertEqual(w.bar.value,80);self.assertFalse(w.bar.motion.jobs)
            w.bar['value']=0;self.assertEqual(w.bar.value,0)
            self.assertIsNone(w.poll_job);self.assertIsNone(w.feedback.icon.job);self.assertFalse(errors)

    def test_cancel_button_signals_the_current_job_and_disabled_actions_do_not_fire(self):
        from video_media import Cancelled
        app,window,w,errors=self.window();self.pump(app);original=w.cancel;settled=[]
        w.open.action=lambda:settled.append(True);w.open.invoke();self.assertFalse(settled)
        def work():
            w.cancel.wait(3)
            if w.cancel.is_set():raise Cancelled('已取消')
        w.dispatch(work,lambda _:settled.append(True));current=w.cancel
        self.assertIsNot(original,current);w.stop.invoke();self.assertTrue(current.is_set());self.assertFalse(original.is_set())
        self.pump(app);self.assertFalse(w.busy);self.assertFalse(settled);self.assertEqual(w.status.get(),'已取消')
        self.assertIsNone(w.poll_job);self.assertFalse(errors)

    def test_calibration_bitmap_is_reused_and_coordinates_do_not_animate(self):
        from PIL import Image
        app,window,w,errors=self.window();w.tabs.select(1);self.pump(app)
        w.media=dict(width=640,height=360);w.image=Image.new('RGB',(640,360),'#334455');w.redraw();photo=w.photo
        for _ in range(20):w.redraw()
        self.assertIs(w.photo,photo);self.assertEqual(len(w.canvas.find_withtag('bitmap')),1)
        self.assertFalse(w.tabs.motion.jobs);self.assertEqual(w.tabs.offset,0)
        self.assertGreater(w.canvas.winfo_height(),80)
        window.geometry('940x720');self.pump(app)
        self.assertGreater(w.canvas.winfo_height(),140);w.fit_preview()
        self.assertLessEqual(w.photo.height(),w.canvas.winfo_height());self.assertFalse(errors)

    def test_light_theme_and_hidden_advanced_fields_retain_input(self):
        from control_theme import set_mode
        from control_video import MODES
        app,window,w,errors=self.window();self.pump(app)
        w.sync.insert('1.0','10 = 0');w.mode.set(list(MODES)[2]);w.mode_changed();self.pump(app)
        self.assertTrue(w.telemetry_card.winfo_manager())
        w.mode.set(list(MODES)[0]);w.mode_changed();self.assertFalse(w.telemetry_card.winfo_manager())
        self.assertEqual(w.sync.get('1.0','end').strip(),'10 = 0')
        app.set_theme('light');self.pump(app);self.assertEqual(w.fields['start'].get(),'0');self.assertFalse(errors)
        app.set_theme('dark')
        from control_theme import T
        self.assertEqual(w.heading_title.cget('fg'),T.FG)


if __name__=='__main__':unittest.main()
