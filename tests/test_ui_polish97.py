"""Tool windows share one anatomy: Lap A / Lap B and batch tasks use the shared
window shell (heading, content, footer state on the left and actions on the
right, Esc), and no tool window floats above other applications."""
import os,unittest
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
from tests import test_ui_polish69 as helpers

ROOT=Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name=='nt','Native Tk')
class Footer(unittest.TestCase):
    def test_footer_hides_actions_that_do_not_apply_and_closes_the_gap(self):
        from control_window import window as sheet
        root=tk.Tk();root.geometry('300x200+40+40');self.addCleanup(root.destroy)
        win=sheet(root,'Stintrix · 示例','说明');first=win.add_action('第一项',lambda:None,True,110);second=win.add_action('第二项',lambda:None,False,110)
        win.geometry('640x300');root.update();win.update()
        self.assertEqual(win.footer.ordered(),[first,second])
        win.footer.show(first,False);win.update()
        self.assertEqual(win.footer.ordered(),[second]);self.assertFalse(first.winfo_ismapped());self.assertTrue(second.winfo_ismapped())
        win.footer.show(first,True);win.update()
        self.assertEqual(win.footer.ordered(),[first,second]);self.assertTrue(first.winfo_ismapped())

    def test_generic_tool_panel_is_not_always_on_top(self):
        import management
        root=tk.Tk();root.withdraw();self.addCleanup(root.destroy)
        window=management.panel(SimpleNamespace(root=root),'Stintrix · 示例',400,300)
        self.assertFalse(window.attributes('-topmost'))
        source=(ROOT/'src/management.py').read_text(encoding='utf-8')
        self.assertNotIn("attributes('-topmost',True)",source);self.assertNotIn('theme_use',source)


class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump

    def test_lap_pair_uses_the_shared_window_and_esc_closes_it(self):
        from control_lap_pair import show
        app,root,errors=self.app()
        window=show(app,app.data_path);self.pump(app,.3);c=window.pair_controls
        self.assertIsNotNone(window.header);self.assertEqual(window.header.title.cget('text'),'圈 A / 圈 B 对比')
        # The compare action is the footer's primary; the state line shares the footer.
        self.assertIn(c['compare'],window.footer.buttons);self.assertTrue(c['compare'].primary);self.assertIn(c['reopen'],window.footer.buttons)
        self.assertIs(c['status'],window.status);self.assertIs(c['footer'],window.footer)
        self.assertFalse(window.attributes('-topmost'));self.assertEqual(str(window.transient() or ''),'')
        # Esc and the close box share the shell's close path.
        self.assertTrue(window.bind('<Escape>'));window.request_close();self.pump(app,.2);self.assertFalse(window.winfo_exists())
        self.assertFalse(errors)

    def test_batch_tasks_use_the_shared_window_and_keep_running_when_closed(self):
        import control_batch,time
        app,root,errors=self.app()
        job=control_batch.start(app,'示例批量任务',['第一项','第二项'],lambda value:(time.sleep(.05),{})[1]);w=job.window
        self.assertIsNotNone(w.header);self.assertEqual(w.header.title.cget('text'),'示例批量任务')
        # Progress is the footer's state line; the task's actions sit on its right.
        self.assertIs(job.text,w.status)
        for button in (job.stop_button,job.retry_button,job.resume_button,job.copy_button):self.assertIn(button,w.footer.buttons)
        self.assertTrue(w.bind('<Escape>'));w.request_close();self.pump(app,.05);self.assertEqual(w.state(),'withdrawn')
        deadline=time.monotonic()+5
        while job.busy and time.monotonic()<deadline:self.pump(app,.05)
        self.assertEqual(job.states,['已完成','已完成']);self.assertIn('2/2',w.status.get())
        control_batch.show(app);self.pump(app,.05);self.assertEqual(w.state(),'normal')
        self.assertFalse(errors)
