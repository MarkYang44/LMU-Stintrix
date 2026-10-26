"""User-workflow regressions for compact layouts and retained context."""
import json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class OptionTests(unittest.TestCase):
    def test_options_preserve_profiles_and_unknown_settings(self):
        from video_preferences import options,save_options
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            path=Path(tmp)/'video_preferences.json';path.write_text(json.dumps(dict(profiles=[{'keep':1}],custom={'keep':2})))
            save_options(tmp,30,True,'ffmpeg tools');self.assertEqual(options(tmp),dict(hz=30,smooth_120hz=True,ffmpeg_dir='ffmpeg tools'))
            saved=json.loads(path.read_text());self.assertEqual(saved['profiles'],[{'keep':1}]);self.assertEqual(saved['custom'],{'keep':2})


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class EfficiencyTests(unittest.TestCase):
    def pump(self,app,seconds=.25):
        end=time.monotonic()+seconds
        while time.monotonic()<end:app.root.update();time.sleep(.005)
    def app(self,fixtures=False):
        from control_center import ControlCenter
        temp=tempfile.TemporaryDirectory(dir=ROOT/'_local');self.addCleanup(temp.cleanup);root=Path(temp.name)
        if fixtures:
            from tools.capture_readme import sessions
            sessions(root)
        guard=patch('control_center.ROOT',root);guard.start();self.addCleanup(guard.stop)
        repair=patch('control_center.ControlCenter.repair_windows_entry');repair.start();self.addCleanup(repair.stop)
        app=ControlCenter();app.root.geometry('1060x700');errors=[];app.root.report_callback_exception=lambda *args:errors.append(args)
        def close():
            import tkinter as tk
            app.close()
            while True:
                try:
                    if not app.root.winfo_exists():break
                    app.root.update();time.sleep(.005)
                except tk.TclError:break
        self.addCleanup(close);self.pump(app);return app,root,errors
    def test_query_selection_scroll_and_advanced_filters_survive_page_changes(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.5)
        app.search.set('Fuji');app.populate();chosen=app.tree.get_children()[0];app.tree.selection_set((chosen,));app.review_filters.toggle()
        app.scroll.yview_moveto(.3);self.pump(app,.1);position=app.scroll.yview()[0]
        app.show_page(0);self.pump(app,.1);app.show_page(1);self.pump(app,.5)
        self.assertEqual(app.search.get(),'Fuji');self.assertEqual(app.tree.selection(),(chosen,));self.assertTrue(app.review_filters.advanced.winfo_manager())
        self.assertAlmostEqual(app.scroll.yview()[0],position,places=2);self.assertFalse(errors)
    def test_small_window_has_real_rows_and_fixed_actions(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.5)
        top=app.tree.viewport.winfo_rooty()-app.scroll.winfo_rooty();visible=(app.scroll.winfo_height()-top)/app.tree.rowheight
        self.assertGreaterEqual(visible,2);toolbar_y=app.shell.action_host.winfo_rooty();app.scroll.yview_moveto(.5);self.pump(app,.1)
        self.assertEqual(app.shell.action_host.winfo_rooty(),toolbar_y);self.assertFalse(app.review_actions['open'].enabled)
        app.tree.selection_set((app.tree.get_children()[0],));app.update_selection_count();self.assertTrue(app.review_actions['open'].enabled);self.assertFalse(errors)
    def test_personal_record_query_survives_leaving_page(self):
        from control_event_filters import EventControls
        app,root,errors=self.app(True);app.show_page(6);self.pump(app,.6)
        def walk(w):
            for child in w.winfo_children():yield child;yield from walk(child)
        controls=next(w for w in walk(app.content) if isinstance(w,EventControls))
        controls.query.set('Spa');self.pump(app,.1);app.show_page(0);app.show_page(6);self.pump(app,.5)
        controls=next(w for w in walk(app.content) if isinstance(w,EventControls));self.assertEqual(controls.query.get(),'Spa');self.assertFalse(errors)

    def test_data_tasks_preserve_hidden_and_unsaved_fields(self):
        app,root,errors=self.app();app.show_page(3);self.pump(app)
        tasks=app.data_tasks;tasks.select('renderer');app.renderer_path.set('draft renderer.exe');tasks.select('packages');tasks.select('renderer')
        self.assertEqual(app.renderer_path.get(),'draft renderer.exe')
        app.show_page(0);app.show_page(3);self.pump(app);self.assertEqual(app.data_tasks.current,'renderer');self.assertEqual(app.renderer_path.get(),'draft renderer.exe');self.assertFalse(errors)
    def test_setting_labels_keep_raw_values_and_live_actions_disable(self):
        from control_fields import Select
        app,root,errors=self.app();self.assertFalse(app.stop_button.enabled);self.assertFalse(any(b.enabled for b in app.live_actions))
        app.show_page(2);self.pump(app)
        def walk(w):
            for child in w.winfo_children():yield child;yield from walk(child)
        select=next(w for w in walk(app.pages.active.frame) if isinstance(w,Select) and w.labels.get('fixed')=='固定频率')
        self.assertEqual(select.display('fixed'),'固定频率');select.variable.set('dynamic');self.assertEqual(select.variable.get(),'dynamic');self.assertFalse(errors)
    def test_video_options_restore_without_skipping_geometry_checks(self):
        from control_video import show
        app,root,errors=self.app();w=show(app,root).video_wizard
        self.assertFalse((root/'video_preferences.json').exists());w.hz.set('30');w.smooth_120hz.set(True);w.fields['ffmpeg'].set('remembered tools');w.close()
        w=show(app,root).video_wizard;self.pump(app)
        self.assertEqual(w.hz.get(),'30');self.assertTrue(w.smooth_120hz.get());self.assertEqual(w.fields['ffmpeg'].get(),'remembered tools');self.assertEqual(w.geometry,{});self.assertIsNone(w.media);self.assertFalse(errors)
    def test_recent_search_and_refresh_keep_stable_result_selection(self):
        from control_video_results import show
        app,root,errors=self.app()
        for index,track in enumerate(['Monza','Fuji Speedway']):
            folder=root/'VideoCurves'/f'20261021T12000{index}Z-test';folder.mkdir(parents=True)
            value=dict(format='stintrix.video-curves',version=1,identity=dict(track=track),video_file=track+'.mp4',quality={},rows=[])
            (folder/'curve.json').write_text(json.dumps(value));(folder/'report.html').write_text('report')
        window=show(app,root);self.pump(app,.5);table=window.results_table;chosen=table.get_children()[-1];table.selection_set((chosen,));self.pump(app,.05)
        window.refresh_results();self.pump(app,.3);self.assertEqual(table.selection(),(chosen,))
        window.results_search.set('Fuji');self.pump(app,.12);self.assertEqual(len(table.get_children()),1);self.assertIn('Fuji',table.rows[table.get_children()[0]][1]);self.assertFalse(errors)
