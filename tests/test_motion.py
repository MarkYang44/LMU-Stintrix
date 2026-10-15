"""Motion continuity, accessibility, cancellation and native frame work."""
import os,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
import control_motion as motion

class MotionTests(unittest.TestCase):
    def test_curves_and_spring_continue_from_live_value_and_velocity(self):
        for curve in motion.CURVES:
            values=[motion.ease(i/100,curve) for i in range(101)];self.assertEqual(values[0],0);self.assertEqual(values[-1],1);self.assertEqual(values,sorted(values))
        x,v=motion.spring_step(0,0,100,.08);self.assertGreater(x,0);self.assertGreater(v,0)
        reversed_x,reversed_v=motion.spring_step(x,v,0,.001)
        self.assertGreater(reversed_x,x);self.assertLess(reversed_v,v)
        for _ in range(150):x,v=motion.spring_step(x,v,100,.016)
        self.assertAlmostEqual(x,100,places=4)

    def test_reduced_motion_keyboard_and_destroy_release_callbacks(self):
        import tkinter as tk
        root=tk.Tk();widget=tk.Canvas(root);widget.pack();root.update();driver=motion.Motion(widget);frames=[]
        try:
            with patch.dict(os.environ,{'LMU_STINTRIX_REDUCED_MOTION':'1'}):
                driver.animate('x',frames.append);self.assertEqual(frames,[1]);self.assertFalse(driver.jobs)
            with patch('control_motion.system_motion',return_value=True):
                motion.keyboard_action(widget,lambda:driver.animate('x',frames.append));self.assertEqual(frames,[1,1]);self.assertFalse(driver.jobs)
                root._motion_keyboard_until=0;driver.animate('x',frames.append);self.assertTrue(driver.jobs)
                widget.destroy();self.assertFalse(driver.jobs);self.assertFalse(driver.tokens)
        finally:root.destroy()

    def test_button_reuses_items_and_scroll_retargets_without_velocity_reset(self):
        import tkinter as tk
        from types import SimpleNamespace
        from control_widgets import Pill
        root=tk.Tk();button=Pill(root,'Test',lambda:None);button.pack();root.update()
        try:
            items=button.find_all()
            with patch('control_motion.system_motion',return_value=True):
                for i in range(50):button.amount=i/50;button.paint()
                self.assertEqual(button.find_all(),items)
                values=[0.];scroll=motion.SmoothScroll(button,lambda:values[0],lambda:500,lambda v:values.__setitem__(0,v))
                scroll.add(200);scroll.last=time.perf_counter()-.05;scroll.frame();velocity=scroll.velocity
                scroll.add(-100);self.assertEqual(scroll.velocity,velocity)
                scroll.move(50);self.assertEqual(values[0],50);self.assertIsNone(scroll.job);scroll.cancel()
        finally:root.destroy()

    def test_retarget_from_inside_paint_does_not_resurrect_old_animation(self):
        import tkinter as tk
        root=tk.Tk();widget=tk.Canvas(root);widget.pack();root.update();driver=motion.Motion(widget);frames=[]
        try:
            with patch('control_motion.system_motion',return_value=True):
                def paint(t):driver.animate('x',lambda value:frames.append(value),0)
                driver.animate('x',paint)
                self.assertEqual(frames,[1]);self.assertFalse(driver.jobs);self.assertFalse(driver.tokens)
        finally:root.destroy()

    def test_real_mouse_switch_animates_reverses_and_cancels_release_outside(self):
        import tkinter as tk
        from control_widgets import Switch
        root=tk.Tk();root.geometry('500x160');variable=tk.BooleanVar(root,value=False);calls=[];switch=Switch(root,'Telemetry',variable,lambda:calls.append(variable.get()));switch.pack(fill='x');root.update()
        def pump(seconds):
            end=time.perf_counter()+seconds
            while time.perf_counter()<end:root.update();time.sleep(.003)
        def click():
            switch.event_generate('<ButtonPress-1>',x=450,y=24);root.update()
            switch.event_generate('<ButtonRelease-1>',x=450,y=24);root.update()
        try:
            with patch('control_motion.system_motion',return_value=True):
                items=switch.find_all();click()
                self.assertTrue(variable.get());self.assertEqual(calls,[True]);self.assertIn('toggle',switch.motion.jobs)
                self.assertLess(switch.value,1);pump(.06);self.assertGreater(switch.value,0);self.assertLess(switch.value,1)
                # update() legitimately advances frames during the second mouse press.
                # Compare adjacent actual paints at retarget, not two wall-clock samples.
                samples=[];original=switch.paint
                def observed():
                    samples.append((variable.get(),switch.value));original()
                with patch.object(switch,'paint',observed):click()
                boundary=next(i for i,v in enumerate(samples) if not v[0])
                self.assertGreater(boundary,0)
                self.assertAlmostEqual(samples[boundary][1],samples[boundary-1][1],delta=.01)
                self.assertGreater(switch.motion.springs['toggle']['velocity'],0)
                self.assertFalse(variable.get());pump(.65);self.assertEqual(switch.value,0);self.assertNotIn('toggle',switch.motion.jobs)
                switch.event_generate('<ButtonPress-1>',x=450,y=24);switch.event_generate('<ButtonRelease-1>',x=-2,y=24);root.update()
                self.assertEqual(calls,[True,False]);self.assertEqual(switch.find_all(),items)
                keyboard_action=motion.keyboard_action
                keyboard_action(switch,switch.toggle);self.assertEqual(switch.value,1);self.assertNotIn('toggle',switch.motion.jobs)
                with patch('control_motion.system_motion',return_value=False):click();self.assertEqual(switch.value,0);self.assertFalse(switch.motion.jobs)
        finally:root.destroy()

if __name__=='__main__':unittest.main()
