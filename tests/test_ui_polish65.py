"""Data selection, immediate-save recovery, search and read-only native import workflows."""
import json,os,sys,tempfile,unittest,csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests import test_ui_efficiency as helpers


class Rules(unittest.TestCase):
    def test_archive_and_recording_updates_preserve_unknown_fields_and_reject_corrupt_files(self):
        import archive_preferences,recording_policy
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            root=Path(temp)
            for name,save in [('archive_settings.json',lambda:archive_preferences.save(root,'7z',False)),('recording_settings.json',lambda:recording_policy.save(root,True))]:
                p=root/name;p.write_text(json.dumps({'custom':{'keep':17}}));save();self.assertEqual(json.loads(p.read_text())['custom'],{'keep':17})
                for invalid in ('[]','not json'):
                    p.write_text(invalid)
                    with self.assertRaises(ValueError):save()
                    self.assertEqual(p.read_text(),invalid)
    def test_native_import_multiple_files_partial_report_retry_never_reimports_success(self):
        import telemetry_import as native
        from tests.test_laplab import fixture
        import control_transfers
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            root=Path(temp);one=root/'one.duckdb';two=root/'two.duckdb';fixture(one);fixture(two,explicit=True)
            before={p:(native.fingerprint(p),p.stat().st_mtime_ns) for p in (one,two)};app=SimpleNamespace(root=None,data_path=root/'output',refresh=Mock())
            real=native.import_recording
            with patch('control_transfers.filedialog.askopenfilenames',return_value=(str(one),str(two),str(one))),patch('control_transfers.start') as start,patch.object(native,'driver',lambda _:__import__('_duckdb')),patch.object(native,'import_recording',wraps=real) as imported,patch('session_reports.make_report',side_effect=[{'state':'partial','steps':{'analysis':{'state':'ready'},'images':{'state':'error','error':'fixture report failure'}}},{'state':'ready','steps':{}},{'state':'ready','steps':{}}]):
                control_transfers.import_native(app);self.assertEqual(start.call_args.args[2],[str(one),str(two)]);operation=start.call_args.args[3]
                first=operation(str(one));self.assertTrue(first['errors']);second=operation(str(two));self.assertFalse(second['errors']);retry=operation(str(one));self.assertFalse(retry['errors']);self.assertEqual(imported.call_count,2)
                for result in (first,second):
                    with (Path(result['path'])/'inputs.csv').open(encoding='utf-8-sig',newline='') as stream:self.assertEqual(sum(1 for _ in csv.DictReader(stream)),3501)
            self.assertEqual({p:(native.fingerprint(p),p.stat().st_mtime_ns) for p in (one,two)},before)
    def test_native_cancel_and_busy_do_not_create_jobs_or_open_more_dialogs(self):
        import control_transfers
        app=SimpleNamespace(root=None)
        with patch('control_transfers.available',return_value=False),patch('control_transfers.filedialog.askopenfilenames') as dialog,patch('control_transfers.start') as start:control_transfers.import_native(app);dialog.assert_not_called();start.assert_not_called()
        with patch('control_transfers.filedialog.askopenfilenames',return_value=()),patch('control_transfers.start') as start:control_transfers.import_native(app);start.assert_not_called()


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def data(self,app,section='packages'):
        app.show_page(3);self.pump(app,.35);app.data_tasks.select(section);self.pump(app,.1);return app.data_browser
    def test_storage_failure_restores_values_keeps_file_and_retry_preserves_unknown_data(self):
        app,root,errors=self.app();p=root/'storage_settings.json';p.write_text(json.dumps(dict(auto_compress=False,columnar=True,cache_limit_mb=777,custom={'keep':3})))
        self.data(app,'storage');before=p.read_bytes();app.storage_auto.set(True)
        with patch('storage.atomic_json',side_effect=OSError('fixture denied')):self.assertFalse(app.storage_save.submit())
        self.assertFalse(app.storage_auto.get());self.assertEqual(p.read_bytes(),before);self.assertIn('fixture denied',app.status.get());self.assertTrue(app.storage_save.retry_button.winfo_manager())
        self.assertTrue(app.storage_save.retry());v=json.loads(p.read_text());self.assertTrue(v['auto_compress']);self.assertEqual(v['cache_limit_mb'],777);self.assertEqual(v['custom'],{'keep':3});self.assertIsNone(app.storage_save.pending);self.assertFalse(errors)
    def test_corrupt_storage_file_is_preserved_and_new_edit_supersedes_failed_draft(self):
        app,root,errors=self.app();p=root/'storage_settings.json';p.write_text('{broken');self.data(app,'storage');old=app.storage_auto.get();app.storage_auto.set(not old)
        self.assertFalse(app.storage_save.submit());self.assertEqual(app.storage_auto.get(),old);self.assertEqual(p.read_text(),'{broken')
        p.write_text(json.dumps(dict(auto_compress=old,columnar=True,cache_limit_mb=512)));app.cache_limit.set('1024');self.assertTrue(app.storage_save.submit());self.assertIsNone(app.storage_save.pending);self.assertEqual(json.loads(p.read_text())['auto_compress'],old);self.assertEqual(json.loads(p.read_text())['cache_limit_mb'],1024);self.assertFalse(errors)
    def test_archive_failure_rolls_back_format_and_can_retry(self):
        app,root,errors=self.app();self.data(app);app.archive_format.set('7z')
        with patch('archive_preferences.atomic_json',side_effect=OSError('fixture failure')):self.assertFalse(app.archive_save.submit())
        self.assertEqual(app.archive_format.get(),'ZIP');self.assertFalse((root/'archive_settings.json').exists());self.assertTrue(app.archive_save.retry());self.assertEqual(json.loads((root/'archive_settings.json').read_text())['format'],'7z');self.assertFalse(errors)
    def test_retry_merges_only_failed_fields_into_newer_external_settings(self):
        app,root,errors=self.app();p=root/'storage_settings.json';p.write_text(json.dumps(dict(auto_compress=False,columnar=True,cache_limit_mb=777)))
        self.data(app,'storage');app.storage_auto.set(True)
        with patch('storage.atomic_json',side_effect=OSError('fixture denied')):self.assertFalse(app.storage_save.submit())
        p.write_text(json.dumps(dict(auto_compress=False,columnar=False,cache_limit_mb=1234,custom='external')))
        self.assertTrue(app.storage_save.retry());value=json.loads(p.read_text());self.assertTrue(value['auto_compress']);self.assertFalse(value['columnar']);self.assertEqual(value['cache_limit_mb'],1234);self.assertEqual(value['custom'],'external');self.assertEqual(app.cache_limit.get(),'1234');self.assertFalse(errors)
    def test_native_batch_window_retries_only_failed_reports(self):
        import control_transfers
        app,root,errors=self.app();paths=[root/'one.duckdb',root/'two.duckdb']
        for p in paths:p.write_bytes(b'fixture')
        def imported(source,destination):
            folder=destination/Path(source).stem;folder.mkdir(exist_ok=True);return folder
        with patch('control_transfers.filedialog.askopenfilenames',return_value=tuple(map(str,paths))),patch('telemetry_import.import_recording',side_effect=imported) as imports,patch('session_reports.make_report',side_effect=[{'state':'ready'},{'state':'partial','steps':{'images':{'state':'error','error':'fixture'}}},{'state':'ready'}]):
            control_transfers.import_native(app);job=app.batch_job
            for _ in range(50):
                self.pump(app,.1)
                if not job.busy:break
            self.assertFalse(job.busy);self.assertEqual(job.states,['已完成','部分失败']);self.assertTrue(job.retry_button.enabled);job.retry_button.command()
            for _ in range(50):
                self.pump(app,.1)
                if not job.busy:break
            self.assertFalse(job.busy);self.assertEqual(job.states,['已完成','已完成']);self.assertEqual(imports.call_count,2)
        self.assertFalse(errors)
    def test_same_selection_table_search_and_scroll_move_between_packages_and_storage(self):
        app,root,errors=self.app(True);browser=self.data(app);table=app.tree;ids=table.get_children()[:2];table.selection_set(ids);table.set_offset(50);app.search.set('');offset=table.offset
        with patch.object(app,'refresh') as refresh:
            from track_names import display
            app.data_tasks.select('storage');self.pump(app,.1);self.assertIs(app.tree,table);self.assertEqual(table.selection(),ids);self.assertEqual(table.offset,offset);self.assertIn(app.items[int(ids[0])]['vehicle'],browser.summary.get());self.assertIn(display(app.items[int(ids[0])]['track']),browser.summary.get());refresh.assert_not_called()
        app.data_tasks.select('packages');self.assertIs(app.tree,table);self.assertEqual(table.selection(),ids);self.assertFalse(errors)
    def test_storage_picker_is_inline_and_preserves_selection_when_hidden(self):
        app,root,errors=self.app(True);b=self.data(app,'storage');self.assertEqual(app.data_section,'storage');self.assertTrue(b.table.winfo_ismapped())
        chosen=b.table.get_children()[0];b.table.selection_set((chosen,));b.toggle_picker();self.pump(app,.05);self.assertEqual(app.data_section,'storage');self.assertFalse(b.table.winfo_ismapped());self.assertEqual(b.table.selection(),(chosen,));self.assertTrue(b.toolbar['csv'].enabled)
        b.toggle_picker();self.pump(app,.05);self.assertTrue(b.table.winfo_ismapped());self.assertFalse(errors)
    def test_empty_selection_disables_export_and_all_clear_actions_remain_available(self):
        app,root,errors=self.app(True);b=self.data(app);self.assertFalse(b.toolbar['export'].enabled);self.assertTrue(b.toolbar['import'].enabled)
        b.menu.invoke('all');self.assertEqual(len(b.table.selection()),len(b.table.rows));self.assertTrue(b.toolbar['export'].enabled);b.menu.invoke('clear');self.assertFalse(b.toolbar['export'].enabled);self.assertFalse(errors)
    def test_filters_keep_query_and_selection_context_across_task_changes(self):
        app,root,errors=self.app(True);b=self.data(app);b.toggle_filters();app.search.set('Fuji');self.pump(app,.15);selected=b.table.get_children()[0];b.table.selection_set((selected,));query=app.search.get()
        app.data_tasks.select('storage');self.assertEqual(app.search.get(),query);self.assertEqual(b.table.selection(),(selected,));self.assertTrue(b.filters.winfo_manager());self.assertFalse(errors)
    def test_minimum_packages_have_rows_and_fixed_actions_while_scrolling(self):
        app,root,errors=self.app(True);b=self.data(app);self.pump(app,.1)
        visible=(app.scroll.winfo_rooty()+app.scroll.winfo_height()-b.table.viewport.winfo_rooty())/b.table.rowheight;self.assertGreaterEqual(visible,2)
        y=b.toolbar['import'].winfo_rooty();app.scroll.yview_moveto(.4);self.pump(app,.05);self.assertEqual(b.toolbar['import'].winfo_rooty(),y);self.assertFalse(errors)
        app.root.geometry('1420x960');self.pump(app,.15);self.assertGreaterEqual(b.table.viewport.winfo_height()/b.table.rowheight,8);self.assertFalse(errors)
    def test_non_edit_keys_do_not_rebuild_review_and_rapid_edits_are_coalesced(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.4);field=app.search_target;field.entry.focus_force();self.pump(app,.05)
        with patch.object(app.tree,'replace',wraps=app.tree.replace) as replaced:
            for key in ('Left','Right','Home'):field.entry.event_generate('<KeyRelease>',keysym=key)
            self.pump(app,.1);self.assertEqual(replaced.call_count,0)
            for query in ('F','Fu','Fuj','Fuji'):app.search.set(query)
            self.pump(app,.15);self.assertEqual(replaced.call_count,1);field.clear();self.assertEqual(replaced.call_count,2);self.pump(app,.15);self.assertEqual(replaced.call_count,2)
        self.assertFalse(errors)
    def test_search_return_flushes_last_edit_and_destroy_cancels_pending_command(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.4);field=app.search_target;app.search.set('Fuji');field.flush();self.assertTrue(app.tree.rows)
        self.assertTrue(all('Fuji' in row[4] or '富士' in row[4] for row in app.tree.rows.values()))
        app.search.set('pending');app.show_page(0);self.pump(app,.15);self.assertIsNone(field.pending);self.assertFalse(errors)
    def test_settings_search_restores_matches_and_draft_on_return(self):
        app,root,errors=self.app();app.show_page(2);self.pump(app,.2);form=app.pages.pages[2].forms['sampling'];form['fixed_hz'].set('240');search=app.settings_search;search.variable.set('胎压');self.pump(app,.3);count=len(search.entries);self.assertGreater(count,0)
        app.show_page(0);app.show_page(2);self.pump(app,.2);current=app.settings_search;self.assertEqual(current.variable.get(),'胎压');self.assertEqual(len(current.entries),count);self.assertTrue(current.results.winfo_manager());self.assertEqual(form['fixed_hz'].get(),'240');self.assertFalse(errors)
    def test_chosen_search_result_stays_collapsed_until_ctrl_f(self):
        app,root,errors=self.app();app.show_page(2);self.pump(app,.2);s=app.settings_search;s.variable.set('fixed_hz');s.open_first();self.assertFalse(s.results.winfo_manager());app.show_page(0);app.show_page(2);self.pump(app,.1);s=app.settings_search;self.assertFalse(s.results.winfo_manager());app.focus_search();self.assertTrue(s.results.winfo_manager());self.assertFalse(errors)
    def test_settings_query_survives_leaving_before_debounce_finishes(self):
        app,root,errors=self.app();app.show_page(2);self.pump(app,.2);app.settings_search.variable.set('胎压');app.show_page(0);app.show_page(2);self.pump(app,.25)
        self.assertEqual(app.settings_search.variable.get(),'胎压');self.assertTrue(app.settings_search.entries);self.assertTrue(app.settings_search.results.winfo_manager());self.assertFalse(errors)
    def test_sampling_intro_has_saved_values_and_diagnostics_keep_expanded_state(self):
        app,root,errors=self.app();app.show_page(2);self.pump(app,.2);self.assertIn('120',app.sampling_summary.cget('text'));self.assertFalse(app.sampling_details.body.winfo_manager());app.sampling_details.set_open(True);app.show_page(0);app.show_page(2);self.pump(app,.1);self.assertTrue(app.sampling_details.body.winfo_manager())
        with patch('control_settings.ROOT',root):app.update_module('sampling',{'fixed_hz':240})
        self.assertIn('240',app.sampling_summary.cget('text'));self.assertFalse(errors)
    def test_practice_write_failure_does_not_flip_effective_recording_policy(self):
        app,root,errors=self.app();app.show_page(2);self.pump(app,.2);app.practice_recording.set(True)
        with patch('recording_policy.atomic_json',side_effect=OSError('fixture denied')):self.assertFalse(app.practice_save.submit())
        self.assertFalse(app.practice_recording.get());self.assertFalse((root/'recording_settings.json').exists());self.assertTrue(app.practice_save.retry());self.assertTrue(json.loads((root/'recording_settings.json').read_text())['practice_enabled']);self.assertFalse(errors)
    def test_phase_labels_are_translated_without_rewriting_source_metadata(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.4);before=[(e['folder'],Path(e['folder'],'session.json').read_bytes()) for e in app.items];original=[e['session_type'] for e in app.items]
        self.assertIn('正赛',[row[1] for row in app.tree.rows.values()]);app.toggle_language();self.pump(app,.2);self.assertIn('Race',[row[1] for row in app.tree.rows.values()]);self.assertEqual([e['session_type'] for e in app.items],original);self.assertEqual([(name,Path(name,'session.json').read_bytes()) for name,_ in before],before);self.assertFalse(errors)
    def test_language_and_theme_keep_storage_selection_and_retry_feedback(self):
        app,root,errors=self.app(True);b=self.data(app,'storage');chosen=b.table.get_children()[0];b.table.selection_set((chosen,));app.storage_auto.set(not app.storage_auto.get())
        with patch('storage.atomic_json',side_effect=OSError('fixture denied')):app.storage_save.submit()
        app.set_theme('light');app.toggle_language();self.pump(app,.3);b=app.data_browser;self.assertEqual(len(b.table.selection()),1);self.assertTrue(b.selected());self.assertIsNotNone(app.storage_save.pending);self.assertTrue(app.storage_save.retry_button.winfo_manager());self.assertIn('fixture denied',app.storage_save.message.get());self.assertFalse(errors)
