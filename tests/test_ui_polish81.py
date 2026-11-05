"""Accordion openings, window and tooltip fades, and no loader flash for ordinary page switches."""
import os,time,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


def wait(root,condition,seconds=2):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


@unittest.skipUnless(os.name=='nt','Native Tk')
class Motion(unittest.TestCase):
    def root(self):
        import tkinter as tk
        root=tk.Tk();root.geometry('500x400+40+40');self.addCleanup(root.destroy);root.update();return root

    def panel(self,root,rows=4):
        import tkinter as tk
        frame=tk.Frame(root)
        for i in range(rows):tk.Label(frame,text=f'row {i}',height=1).pack(fill='x',pady=2)
        return frame

    @patch('control_motion.system_motion',return_value=True)
    def test_expand_grows_from_its_clip_and_restores_natural_geometry(self,_motion):
        from control_motion import expand
        root=self.root();frame=self.panel(root);root._motion_keyboard_until=0
        self.assertTrue(expand(frame,lambda:frame.pack(fill='x')))
        self.assertEqual(frame.winfo_manager(),'pack');self.assertIsNotNone(frame._expand_propagate);self.assertFalse(frame.pack_propagate())
        heights=[]
        self.assertTrue(wait(root,lambda:(heights.append(frame.winfo_height()),frame._expand_propagate is None)[1]))
        self.assertTrue(frame.pack_propagate());self.assertEqual(heights,sorted(heights));root.update()
        self.assertEqual(frame.winfo_height(),frame.winfo_reqheight())
        frame.pack_forget();root.update();self.assertTrue(expand(frame,lambda:frame.pack(fill='x')));root.update()
        frame.pack_forget()  # closed part-way: the next frame hands geometry back
        self.assertTrue(wait(root,lambda:frame._expand_propagate is None,1));self.assertTrue(frame.pack_propagate())

    @patch('control_motion.system_motion',return_value=True)
    def test_keyboard_reduced_motion_and_tall_panels_open_at_once(self,_motion):
        from control_motion import expand
        root=self.root();frame=self.panel(root);root._motion_keyboard_until=time.perf_counter()+5
        self.assertFalse(expand(frame,lambda:frame.pack(fill='x')));self.assertIsNone(getattr(frame,'_expand_propagate',None));frame.pack_forget()
        root._motion_keyboard_until=0;tall=self.panel(root,40)
        self.assertFalse(expand(tall,lambda:tall.pack(fill='x'),limit=100));self.assertTrue(tall.pack_propagate())
        with patch('control_motion.system_motion',return_value=False):
            other=self.panel(root);self.assertFalse(expand(other,lambda:other.pack(fill='x')));self.assertEqual(other.winfo_manager(),'pack')

    @patch('control_motion.system_motion',return_value=True)
    def test_windows_fade_in_once_mapped_and_reduced_motion_appears_at_once(self,_motion):
        import tkinter as tk
        from control_motion import fade_in
        root=self.root();root._motion_keyboard_until=0;window=tk.Toplevel(root)
        self.assertIsNotNone(fade_in(window));self.assertEqual(float(window.attributes('-alpha')),0.)
        self.assertTrue(wait(root,lambda:float(window.attributes('-alpha'))==1.))
        with patch('control_motion.system_motion',return_value=False):
            other=tk.Toplevel(root);self.assertIsNone(fade_in(other));self.assertEqual(float(other.attributes('-alpha')),1.)

    @patch('control_motion.system_motion',return_value=True)
    def test_first_tooltip_fades_and_warm_neighbours_appear_at_once(self,_motion):
        import tkinter as tk,control_tooltip
        from control_tooltip import Tooltip
        root=self.root();root._motion_keyboard_until=0;label=tk.Label(root,text='hint');label.pack();root.update()
        control_tooltip._warm_until=0.;tip=Tooltip(label);self.addCleanup(tip.hide);shows=[];original=label.after
        def after(ms,callback=None,*args):shows.append(callback);return original(ms,callback,*args)
        label.after=after
        tip.request('a','first',0,0);label.after_cancel(tip.pending);shows[-1]()
        self.assertLess(float(tip.window.attributes('-alpha')),.5);self.assertTrue(wait(root,lambda:float(tip.window.attributes('-alpha'))==1.))
        tip.hide();tip.request('b','second',0,0);label.after_cancel(tip.pending);shows[-1]()
        self.assertEqual(float(tip.window.attributes('-alpha')),1.)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_page_hint_waits_long_enough_not_to_flash_on_ordinary_switches(self):
        app,root,errors=self.app();surface=app.shell.surface;delays=[];original=surface.cover.after
        def after(ms,callback=None,*args):delays.append(ms);return original(ms,callback,*args)
        surface.cover.after=after;app.request_page(1);self.settle(app,lambda:bool(app.tree))
        self.assertIn(350,delays);self.assertFalse(surface.hint.winfo_ismapped());self.assertFalse(errors)

    @patch('control_motion.system_motion',return_value=True)
    def test_review_filters_open_with_motion_and_close_instantly(self,_motion):
        app,root,errors=self.app(True);app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        f=app.review_filters;app.root._motion_keyboard_until=0
        f.toggle_filters();self.assertEqual(f.winfo_manager(),'pack');self.assertIsNotNone(f._expand_propagate)
        self.assertTrue(wait(app.root,lambda:f._expand_propagate is None));self.pump(app,.05)
        self.assertEqual(f.winfo_height(),f.winfo_reqheight())
        f.toggle_filters();self.assertFalse(f.winfo_manager())
        app.root._motion_keyboard_until=time.perf_counter()+5;f.toggle_filters();self.assertIsNone(f._expand_propagate);self.assertFalse(errors)

    @patch('control_motion.system_motion',return_value=True)
    def test_parameter_save_bar_rises_and_tool_windows_fade_in(self,_motion):
        app,root,errors=self.app();app.request_page(2);self.settle(app,lambda:'sampling' in getattr(app,'form_panels',{}))
        app.root._motion_keyboard_until=0;bar=app.form_bar;field=app.pages.pages[2].forms['sampling']['fixed_hz'];field.set('240' if field.get()!='240' else '120')
        # Busy runners may finish the drawer inside one update: assert the animated path, then the settled geometry.
        self.assertTrue(wait(app.root,lambda:bar.packed));self.assertTrue(hasattr(bar.frame,'_expand_motion'))
        self.assertTrue(wait(app.root,lambda:bar.frame._expand_propagate is None));self.pump(app,.05);self.assertEqual(bar.frame.winfo_height(),bar.frame.winfo_reqheight())
        bar.select('sampling');bar.discard();self.assertFalse(bar.packed);self.assertFalse(bar.frame.winfo_manager())
        from control_shortcuts import show
        app.root._motion_keyboard_until=0;show(app);window=app.shortcut_window
        self.assertLess(float(window.attributes('-alpha')),1.);self.assertTrue(wait(app.root,lambda:float(window.attributes('-alpha'))==1.))
        self.assertFalse(errors)
