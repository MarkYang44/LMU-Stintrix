"""Explicit participation corrections and focused, context-preserving record UX."""
import json,os,shutil,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_ui_efficiency as helpers


class Rules(unittest.TestCase):
    def folder(self,root,key='Logs/a',**extra):
        folder=root/key;folder.mkdir(parents=True);(folder/'session.json').write_text(json.dumps(dict(status='complete',track='Fuji Speedway',vehicle='Car',custom=17,**extra)),'utf-8');return folder
    def test_confirmation_only_changes_selected_effective_mode_and_is_reversible(self):
        from race_mode_overrides import save
        from race_mode import annotate,overlay
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t:
            root=Path(t);a=self.folder(root);b=self.folder(root,'Logs/b',race_mode='single');original=(a/'session.json').read_bytes()
            save(root,[a],'online');self.assertEqual(annotate({},a,overlay(root))['race_mode'],'online');self.assertTrue(annotate({},a,overlay(root))['race_mode_manual']);self.assertEqual(annotate({'race_mode':'single'},b,overlay(root))['race_mode'],'single')
            self.assertEqual((a/'session.json').read_bytes(),original);save(root,[a],None);self.assertNotIn('race_mode',annotate({},a,overlay(root)));self.assertEqual((a/'session.json').read_bytes(),original)
    def test_automatic_rebuild_conflict_and_moved_root_never_erase_user_choice(self):
        from race_mode_overrides import save,apply
        from race_mode import annotate,build,overlay
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t:
            root=Path(t);a=self.folder(root);save(root,[a],'online');build(root,[],[]);self.assertEqual(annotate({'race_mode':'single'},a,overlay(root))['race_mode'],'online')
            moved=root/'relocated';shutil.copytree(root/'Logs',moved/'Logs');shutil.copytree(root/'RaceModes',moved/'RaceModes');self.assertEqual(annotate({},moved/'Logs/a',apply(moved,{}))['race_mode'],'online')
            (root/'RaceModes/index.json').write_text('[]');self.assertEqual(annotate({},a,overlay(root))['race_mode'],'online')
    def test_bad_override_file_is_retained_and_atomic_batch_rejects_invalid_targets(self):
        from race_mode_overrides import save
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t:
            root=Path(t);a=self.folder(root);bad=self.folder(root,'Logs/recording',status_override=True);(bad/'session.json').write_text('{"status":"recording"}');p=root/'RaceModes/overrides.json';p.parent.mkdir()
            for value in ('broken','[]','{}','{"version":true,"entries":{}}','{"version":1,"entries":{"Logs/a/.":{"race_mode":"online"}}}','{"version":1,"entries":{"../outside":{"race_mode":"online"}}}'):
                p.write_text(value)
                with self.assertRaises(ValueError):save(root,[a],'online')
                self.assertEqual(p.read_text(),value)
            p.unlink()
            for folders in ([a,bad],[a,root.parent/'outside']):
                with self.assertRaises(ValueError):save(root,folders,'online')
                self.assertFalse(p.exists())
    def test_saved_portable_key_unknown_fields_and_concurrent_updates_are_preserved(self):
        from race_mode_overrides import save,load
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t:
            root=Path(t);a=self.folder(root);b=self.folder(root,'Logs/b');p=root/'RaceModes/overrides.json';p.parent.mkdir();p.write_text(json.dumps(dict(version=1,custom=99,entries={'Logs\\a':dict(race_mode='single',extra={'keep':17})})))
            errors=[]
            def work(folder):
                try:save(root,[folder],'online')
                except Exception as error:errors.append(error)
            threads=[threading.Thread(target=work,args=(folder,)) for folder in (a,b)]
            for thread in threads:thread.start()
            for thread in threads:thread.join(3);self.assertFalse(thread.is_alive())
            value=load(root);self.assertEqual(value['custom'],99);self.assertEqual(value['entries']['Logs\\a']['extra'],{'keep':17});self.assertEqual(len(value['entries']),2);self.assertFalse(errors)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def best(self):
        app,root,errors=self.app(True);app.show_page(6);self.pump(app,.45);page=app.record_loaders['best'].page;self.assertIsNotNone(page.selected);return app,root,errors,page
    def test_search_placeholder_is_not_data_and_rapid_edits_rebuild_once(self):
        app,root,errors,p=self.best();field=p.search_field;self.assertEqual(p.query.get(),'');self.assertTrue(field.placeholder_label.winfo_ismapped())
        with patch.object(p.table,'replace',wraps=p.table.replace) as changed:
            for value in ('F','Fu','Fuj','Fuji','Fuji '):p.query.set(value)
            self.pump(app,.13);self.assertEqual(changed.call_count,1)
        self.assertFalse(field.placeholder_label.winfo_ismapped());field.clear();self.assertEqual(p.query.get(),'');self.assertFalse(errors)
    def test_pending_search_survives_leaving_before_debounce_and_closed_timer_is_released(self):
        app,root,errors,p=self.best();p.query.set('Fuji');self.assertIsNotNone(p.search_field.pending);old=p.view_layout;app.show_page(0);app.show_page(6);self.pump(app,.4);new=app.record_loaders['best'].page
        self.assertEqual(new.query.get(),'Fuji');self.assertTrue(old.closed);self.assertIsNone(old.job);self.assertIsNone(p.search_field.pending);self.assertFalse(errors)
    def test_empty_search_clear_keeps_filters_and_empty_filter_reset_is_direct(self):
        app,root,errors,p=self.best();p.modes.state['mode']='unknown';p.query.set('unmatched search');self.pump(app,.14);self.assertFalse(p.rows);p.table.empty_button.invoke();self.assertEqual(p.query.get(),'');self.assertEqual(p.modes.state['mode'],'unknown')
        p.modes.state['track']='not a circuit';p.populate_best();self.assertEqual(p.table.empty_button.label,'重置筛选');p.table.empty_button.invoke();self.assertEqual(p.modes.state['track'],'');self.assertTrue(p.rows);self.assertFalse(errors)
    def test_list_uses_extra_height_and_details_return_keep_selection(self):
        app,root,errors,p=self.best();app.root.geometry('1240x920');self.pump(app,.15);large=p.table.viewport.winfo_height();chosen=p.table.selection();p.fixed['details'].invoke();self.pump(app,.08);self.assertGreater(app.scroll.canvasy(0),0);p.buttons['list'].invoke();self.pump(app,.04);self.assertEqual(p.table.selection(),chosen)
        app.root.geometry('1060x700');self.pump(app,.1);small=p.table.viewport.winfo_height();self.assertGreater(large,small);self.assertGreaterEqual(small/p.table.rowheight,4-.01);self.assertEqual(p.table.selection(),chosen);self.assertFalse(errors)
    def test_mode_editor_updates_only_its_bound_session_then_restores_automatic(self):
        app,root,errors,p=self.best();folder=Path(p.selected['folder']);original=p.selected['race_mode'];before=(folder/'session.json').read_bytes();selected=p.table.selection();window=p.correct_mode();controls=window.mode_controls;controls['choice'].set('online');self.assertTrue(controls['save']());self.pump(app,.35)
        p=app.record_loaders['best'].page;self.assertEqual(p.table.selection(),selected);self.assertEqual(p.selected['race_mode'],'online');self.assertIn('人工确认',p.date_label.cget('text'));self.assertEqual((folder/'session.json').read_bytes(),before)
        window=p.correct_mode();window.mode_controls['choice'].set('auto');self.assertTrue(window.mode_controls['save']());self.pump(app,.3);self.assertEqual(p.selected['race_mode'],original);self.assertEqual((folder/'session.json').read_bytes(),before);self.assertFalse(errors)
    def test_editor_save_failure_stays_open_and_corrupt_original_is_never_overwritten(self):
        app,root,errors,p=self.best();window=p.correct_mode();controls=window.mode_controls;controls['choice'].set('online')
        with patch('race_mode_overrides.atomic_json',side_effect=OSError('fixture denied')):self.assertFalse(controls['save']())
        self.assertTrue(window.winfo_exists());self.assertIn('fixture denied',controls['message'].get())
        with patch('race_mode_overrides.atomic_json',side_effect=OSError()):self.assertFalse(controls['save']())
        self.assertEqual(controls['message'].get(),'OSError');path=root/'RaceModes/overrides.json';path.write_text('corrupt');before=path.read_bytes();self.assertFalse(controls['save']());self.assertEqual(path.read_bytes(),before);window.destroy();self.assertFalse(errors)
    def test_theme_language_and_mode_editor_preserve_raw_choice_and_filter_context(self):
        app,root,errors,p=self.best();p.query.set('Fuji');self.pump(app,.14);window=p.correct_mode();window.mode_controls['choice'].set('single');app.set_theme('light');app.toggle_language();self.pump(app,.2)
        self.assertEqual(window.mode_controls['choice'].get(),'single');self.assertIn('User confirmation',window.mode_controls['message'].get());new=app.record_loaders['best'].page;self.assertEqual(new.query.get(),'Fuji');self.assertEqual(new.search_field.placeholder_label.cget('text'),'Search circuit, car or date');self.assertTrue(window.mode_controls['save']());self.pump(app,.3);self.assertEqual(new.selected['race_mode'],'single');self.assertTrue(new.selected['session']['race_mode_manual']);self.assertFalse(errors)
    def test_small_english_editor_keeps_all_actions_inside_the_window(self):
        from control_video_widgets import Action
        app,root,errors,p=self.best();app.toggle_language();self.pump(app,.3);p=app.record_loaders['best'].page;window=p.correct_mode();window.geometry('500x310');self.pump(app,.15)
        def walk(w):
            yield w
            for child in w.winfo_children():yield from walk(child)
        actions=[w for w in walk(window.mode_controls['footer']) if isinstance(w,Action)];self.assertEqual(len(actions),3)
        for b in actions:self.assertLessEqual(b.winfo_rooty()+b.winfo_height(),window.winfo_rooty()+window.winfo_height());self.assertLessEqual(b.winfo_rootx()+b.winfo_width(),window.winfo_rootx()+window.winfo_width())
        self.assertEqual(actions[-1].cget('text'),'Cancel');window.destroy();self.assertFalse(errors)
    def test_class_column_scales_with_the_actual_font_at_125_percent(self):
        import tkinter as tk
        from control_center import ControlCenter
        from tools.capture_readme import sessions
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t,patch('control_center.ROOT',Path(t)),patch('control_center.ControlCenter.repair_windows_entry'):
            sessions(Path(t));window=tk.Tk();window.tk.call('tk','scaling',120/72);app=ControlCenter(window)
            try:
                app.show_page(6);self.pump(app,.4);p=app.record_loaders['best'].page
                self.assertGreaterEqual(p.table.actual['class'],p.table.font.measure('LMGT3')+28*p.table.s)
            finally:
                app.close()
                while app.pages.owner is not None:app.root.update()
