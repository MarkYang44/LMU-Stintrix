"""Unknown participation workflows preserve evidence, selection and known modes."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_ui_efficiency as helpers


class Rules(unittest.TestCase):
    def folder(self,root,name,kind='unknown',status='complete'):
        p=root/'Logs'/name;p.mkdir(parents=True);(p/'session.json').write_text(json.dumps(dict(track='Fuji Speedway',race_mode=kind,status=status)),'utf-8');return p
    def test_mixed_batch_rechecks_manual_automatic_and_raw_evidence(self):
        from race_mode_overrides import save,load
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t:
            root=Path(t);a=self.folder(root,'unknown');b=self.folder(root,'raw','single');c=self.folder(root,'manual');d=self.folder(root,'automatic');e=self.folder(root,'conflict','single')
            save(root,[c],'single');(root/'RaceModes/index.json').write_text(json.dumps(dict(entries={str(d):dict(race_mode='online'),str(e):dict(race_mode='online')})))
            before={p:(p/'session.json').read_bytes() for p in (a,b,c,d,e)}
            with patch('official_results.refresh',side_effect=AssertionError('No automatic refresh during confirmation')):
                self.assertEqual(save(root,[a,b,c,d,e,a],'online',only_unknown=True),2)
            value=load(root)['entries'];self.assertEqual(set(value),{'Logs/unknown','Logs/manual','Logs/conflict'});self.assertEqual(value['Logs/manual']['race_mode'],'single')
            path=root/'RaceModes/overrides.json';stamp=path.stat().st_mtime_ns;data=path.read_bytes();self.assertEqual(save(root,[a,b,c,d,e],'online',only_unknown=True),0);self.assertEqual(path.read_bytes(),data);self.assertEqual(path.stat().st_mtime_ns,stamp)
            for p,raw in before.items():self.assertEqual((p/'session.json').read_bytes(),raw)
    def test_zero_changes_never_creates_or_rewrites_override_file(self):
        from race_mode_overrides import save
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t:
            root=Path(t);p=self.folder(root,'known','online');path=root/'RaceModes/overrides.json'
            self.assertEqual(save(root,[p],'single',only_unknown=True),0);self.assertFalse(path.exists());self.assertEqual(save(root,[p],None),0);self.assertFalse(path.exists())
            self.assertEqual(save(root,[p],'online'),1);before=(path.read_bytes(),path.stat().st_mtime_ns);self.assertEqual(save(root,[p],'online'),0);self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
    def test_stale_unknown_cannot_overwrite_a_new_confirmation(self):
        from race_mode_overrides import save,load
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t:
            root=Path(t);p=self.folder(root,'race');save(root,[p],'single');self.assertEqual(save(root,[p],'online',only_unknown=True),0);self.assertEqual(load(root)['entries']['Logs/race']['race_mode'],'single')
    def test_batch_validation_is_atomic_and_recording_is_not_confirmed(self):
        from race_mode_overrides import save
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as t:
            root=Path(t);a=self.folder(root,'a');b=self.folder(root,'b',status='recording')
            with self.assertRaises(ValueError):save(root,[a,b],'online',only_unknown=True)
            self.assertFalse((root/'RaceModes/overrides.json').exists())
    def test_display_labels_keep_legacy_storage_keys_and_sort_indices(self):
        from race_mode import LABELS
        from event_filters import CHOICES,SORTS
        from control_event_filters import SHORT_SORTS
        self.assertEqual(LABELS['single'],'线下');self.assertEqual(CHOICES['mode'][1]['single'],'线下');self.assertEqual(SORTS[8],'线下优先');self.assertEqual(SHORT_SORTS[8],'线下优先')


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def best(self):
        app,root,errors=self.app(True);app.show_page(6);self.pump(app,.45);p=app.record_loaders['best'].page
        folder=Path(p.selected['folder']);path=folder/'session.json';value=json.loads(path.read_text('utf-8'));value['race_mode']='unknown';path.write_text(json.dumps(value),'utf-8');p.loader.read(True);self.pump(app,.35)
        self.assertEqual(p.selected['race_mode'],'unknown');return app,root,errors,p
    def test_unknown_inline_confirmation_preserves_selection_and_original_file(self):
        app,root,errors,p=self.best();self.assertTrue(p.participation_notice.winfo_ismapped());selected=p.table.selection();path=Path(p.selected['folder'])/'session.json';raw=path.read_bytes()
        self.assertTrue(p.participation_notice.actions[1].invoke());self.pump(app,.35);self.assertEqual(p.selected['race_mode'],'single');self.assertEqual(p.table.selection(),selected);self.assertFalse(p.participation_notice.winfo_manager());self.assertEqual(path.read_bytes(),raw);self.assertFalse(errors)
    def test_inline_save_error_stays_visible_without_changing_classification(self):
        app,root,errors,p=self.best()
        with patch('race_mode_overrides.atomic_json',side_effect=OSError('fixture blocked')):self.assertFalse(p.participation_notice.actions[0].invoke())
        self.assertEqual(p.selected['race_mode'],'unknown');self.assertTrue(p.participation_notice.winfo_ismapped());self.assertIn('fixture blocked',p.status.get());self.assertFalse(errors)
    def test_library_batch_only_changes_unknown_and_retains_current_record_view(self):
        from control_library import show
        from race_mode_overrides import load
        app,root,errors,p=self.best();selected=p.table.selection();window=show(app,root,lambda *_:None,lambda *_:None);self.pump(app,.4);v=window.library
        keys=tuple(v.table.get_children());v.table.selection_set(keys);self.pump(app,.04);before={k:dict(e) for k,e in v.items.items()};editor=v.operations.correct_mode();self.assertTrue(editor.mode_controls['only_unknown'].get());editor.mode_controls['choice'].set('online');self.assertTrue(editor.mode_controls['save']());self.pump(app,.45)
        unknown=[e for e in before.values() if e['race_mode']=='unknown'];self.assertEqual(len(load(root)['entries']),len(unknown));self.assertEqual(p.selected['race_mode'],'online');self.assertEqual(p.table.selection(),selected)
        for key,e in before.items():self.assertEqual(v.items[key]['race_mode'],'online' if e['race_mode']=='unknown' else e['race_mode'])
        self.assertEqual(v.table.selection(),keys);self.assertIn('mode',v.table.displaycolumns);window.destroy();self.assertFalse(errors)
    def test_library_participation_filter_survives_reopen_and_locate(self):
        from control_library import show
        app,root,errors,p=self.best();window=show(app,root,lambda *_:None,lambda *_:None);self.pump(app,.35);v=window.library;v.participation.set('unknown');v.filters_changed();self.assertTrue(v.table.get_children());self.assertTrue(all(v.items[k]['race_mode']=='unknown' for k in v.table.get_children()));v.toggle_facets();v.close()
        window=show(app,root,lambda *_:None,lambda *_:None);self.pump(app,.35);v=window.library;self.assertEqual(v.participation.get(),'unknown');known=next(e['folder'] for e in v.items.values() if e['race_mode']=='single');v.locate([known]);self.assertIn(known,v.table.selection());v.restore_location();self.assertTrue(all(v.items[k]['race_mode']=='unknown' for k in v.table.get_children()));v.reset_filters();self.assertEqual(len(v.table.get_children()),8);window.destroy();self.assertFalse(errors)
    def test_dialog_selection_is_bound_and_can_explicitly_replace_known_batch(self):
        from control_race_mode import show
        from race_mode_overrides import load
        app,root,errors,p=self.best();entries=[dict(e) for e in p.entries];window=show(app,entries,lambda:p.loader.read(True));controls=window.mode_controls;controls['only_unknown'].set(False);controls['choice'].set('single');bound=controls['folders'];p.table.selection_set(tuple(p.table.get_children())[-1:]);self.assertTrue(controls['save']());self.pump(app,.35)
        self.assertEqual(set(load(root)['entries']),{f.relative_to(root).as_posix() for f in bound});self.assertTrue(all(e['race_mode']=='single' for e in p.entries));self.assertFalse(errors)
    def test_english_small_batch_dialog_and_theme_keep_actions_inside(self):
        from control_race_mode import show
        from control_video_widgets import Action
        app,root,errors,p=self.best();window=show(app,[dict(e) for e in p.entries],lambda:p.loader.read(True));controls=window.mode_controls;controls['choice'].set('single');app.set_theme('light');app.toggle_language();window.geometry('500x340');self.pump(app,.25)
        def walk(w):
            yield w
            for child in w.winfo_children():yield from walk(child)
        actions=[w for w in walk(window) if isinstance(w,Action)];self.assertEqual(len(actions),6)
        for button in actions:
            self.assertGreaterEqual(button.winfo_rooty(),window.winfo_rooty());self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),window.winfo_rooty()+window.winfo_height());self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),window.winfo_rootx()+window.winfo_width())
        import tkinter as tk
        for label in (w for w in walk(window) if isinstance(w,tk.Label) and w.winfo_ismapped()):self.assertGreaterEqual(label.winfo_height(),label.winfo_reqheight(),label.cget('text'))
        self.assertEqual(controls['strip'].buttons['single'].cget('text'),'Offline');self.assertTrue(controls['strip'].buttons['single'].selected);window.destroy();self.assertFalse(errors)
    def test_review_menu_opens_selection_bound_batch_editor(self):
        app,root,errors,p=self.best();app.show_page(1);self.pump(app,.4);app.tree.selection_set(app.tree.get_children()[:2]);app.update_selection_count();action=next(a for a in app.review_menu.actions if a.key=='mode');self.assertTrue(action.enabled());action.command();window=app.participation_editor;self.assertEqual(len(window.mode_controls['folders']),2);window.destroy();self.assertFalse(errors)
