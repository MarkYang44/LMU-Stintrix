"""Full-library preservation, stable identities and shared auxiliary workflows."""
import json,os,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace,MethodType
from unittest.mock import Mock,patch
from tests import test_ui_efficiency as helpers
from tests import test_ui_polish67 as videos


class Rules(unittest.TestCase):
    def test_legacy_note_save_refuses_truncation_corruption_and_keeps_unknowns(self):
        from library import save_note
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as temp:
            root=Path(temp);(root/'Logs/a').mkdir(parents=True);path=root/'library_notes.json';original={'Logs/a':dict(text='old',favorite=True,tags=['keep'],custom=17),'other':dict(text='other')};path.write_text(json.dumps(original))
            before=path.read_bytes()
            with self.assertRaises(ValueError):save_note(root,'Logs/a','测'*2001)
            self.assertEqual(path.read_bytes(),before);save_note(root,'Logs/a','测'*2000,True);value=json.loads(path.read_text('utf-8'));self.assertEqual(len(value['Logs/a']['text']),2000);self.assertEqual(value['Logs/a']['custom'],17);self.assertEqual(value['other'],original['other']);self.assertTrue(value['Logs/a']['favorite'])
            for malformed in ('broken','[]','{"Logs/a": []}'):
                path.write_text(malformed)
                with self.assertRaises(ValueError):save_note(root,'Logs/a','new')
                self.assertEqual(path.read_text(),malformed)
    def test_linked_hud_and_center_share_one_running_batch_without_duplicates(self):
        from control_batch import jobs,running
        job=SimpleNamespace(window=Mock(),busy=True);job.window.winfo_exists.return_value=True;center=SimpleNamespace(batch_jobs=[job]);hud=SimpleNamespace(batch_jobs=[job],control_center=center);center.hud=hud
        self.assertEqual(jobs(center),[job]);self.assertEqual(jobs(hud),[job]);self.assertIs(running(center),running(hud))
        del hud.control_center;hud.batch_jobs=[];hud.on_menu=MethodType(lambda _:None,center);self.assertIs(running(hud),job)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def library(self,extra=0):
        import management
        app,root,errors=self.app(True)
        for i in range(extra):
            folder=root/'Logs'/f'extra-{i:02}';folder.mkdir(parents=True);(folder/'session.json').write_text(json.dumps(dict(status='complete',session=10,track='Monza',vehicle='BMW',started_utc=f'2026-10-01T12:{i:02}:00Z')))
        w=management.show_library(app,root,Mock(),Mock());w.geometry('1060x700');self.pump(app,.35);return app,root,errors,w.library
    def choose(self,v,count=1):
        keys=v.table.get_children()[:count];v.table.selection_set(keys);self.pump(v.owner,.04);return keys
    def test_main_entry_reuses_one_reader_and_resolves_main_row_identity(self):
        import control_library
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.35);app.tree.selection_set((app.tree.get_children()[-1],));folder=app.selection(None)[0]['folder']
        with patch('control_library.inventory',wraps=control_library.inventory) as read:
            w=app.library();self.pump(app,.35);self.assertIs(app.library(),w);self.pump(app,.1);self.assertEqual(read.call_count,1);self.assertEqual(w.library.table.selection(),(str(Path(folder).resolve()),))
            table=w.library.table;index=table.order.index(str(Path(folder).resolve()));self.assertLessEqual((index+1)*table.rowheight,table.offset+table.viewport.winfo_height()+1)
        self.assertFalse(errors)
    def test_refresh_search_and_reopen_keep_selection_widths_filters_and_position(self):
        import management
        app,root,errors,v=self.library(18);v.query.set('');v.table.selection_set((v.table.order[12],));self.pump(app,.04);chosen=v.table.selection();v.table.scroller.move(160);v.table.xoffset=37;v.table.widths['vehicle']=233.125;v.table.schedule();self.pump(app,.04);offset=v.table.offset
        v.refresh();self.pump(app,.3);self.assertEqual(v.table.selection(),chosen);self.assertAlmostEqual(v.table.offset,offset);v.close();w=management.show_library(app,root,Mock(),Mock());self.pump(app,.3);new=w.library
        self.assertEqual(new.table.selection(),chosen);self.assertAlmostEqual(new.table.offset,offset);self.assertEqual(new.table.widths['vehicle'],233.125);self.assertEqual(new.view.get(),'all');self.assertFalse(errors)
    def test_search_merges_input_clear_restores_selection_and_shortcuts_work(self):
        app,root,errors,v=self.library();chosen=self.choose(v)
        with patch.object(v.table,'replace',wraps=v.table.replace) as replaced:
            for text in ('m','mi','mis','miss','missi','missing'):v.query.set(text)
            self.pump(app,.13);self.assertEqual(replaced.call_count,1);self.assertEqual(v.table.selection(),());v.search.clear();self.assertEqual(v.table.selection(),chosen)
        v.window.focus_force();v.window.event_generate('<Control-f>');self.pump(app,.04);self.assertIs(v.window.focus_get(),v.search.entry)
        with patch.object(v,'refresh',wraps=v.refresh) as refreshed:v.window.event_generate('<F5>');self.pump(app,.3);self.assertEqual(refreshed.call_count,1)
        self.assertFalse(errors)
    def test_locate_temporarily_reveals_target_and_returns_to_original_view(self):
        app,root,errors,v=self.library();v.query.set('Fuji');self.pump(app,.12);chosen=self.choose(v);target=next(item['folder'] for item in v.items.values() if 'Spa' in item['track']);v.locate((target,));self.pump(app,.06)
        self.assertEqual(v.query.get(),'Fuji');self.assertEqual(v.table.selection(),(str(Path(target).resolve()),));self.assertTrue(v.location.winfo_manager());v.restore_location();self.pump(app,.04);self.assertEqual(v.table.selection(),chosen);self.assertFalse(v.targets)
        v.locate((target,));v.query.set('Spa');self.pump(app,.12);self.assertFalse(v.targets);self.assertFalse(v.location.winfo_manager());self.assertFalse(errors)
    def test_refresh_requests_are_bounded_and_closed_callbacks_are_ignored(self):
        import control_library
        app,root,errors,v=self.library();gate=threading.Event();entered=threading.Event();calls=[];reader=control_library.inventory
        def read(path):calls.append(path);entered.set();gate.wait(3);return reader(path)
        try:
            with patch('control_library.inventory',side_effect=read):
                v.refresh();self.assertTrue(entered.wait(1))
                for _ in range(5):v.refresh()
                self.pump(app,.03);self.assertEqual(len(calls),1);gate.set();self.pump(app,.4);self.assertEqual(len(calls),2)
            gate.clear();entered.clear()
            with patch('control_library.inventory',side_effect=read):v.refresh();self.assertTrue(entered.wait(1));v.query.set('pending');v.close();gate.set();self.pump(app,.25)
        finally:gate.set()
        self.assertFalse(errors)
    def test_protected_editor_keeps_draft_across_selection_manager_close_and_reopen(self):
        app,root,errors,v=self.library();chosen=self.choose(v);w=v.operations.note();edit=w.note_controls;edit['text'].insert('1.0','unsaved\nsecond line');v.table.selection_set((v.table.order[-1],));self.pump(app,.05);self.assertEqual(edit['text'].get('1.0','end-1c'),'unsaved\nsecond line');v.table.selection_set(chosen);self.pump(app,.05);self.assertIs(v.operations.note(),w);v.close()
        with patch('control_confirm.ask',return_value='cancel'),patch.object(app,'close') as closed:app.request_close();closed.assert_not_called()
        with patch('control_confirm.ask',return_value='keep'):edit['close']()
        self.assertTrue(app.note_drafts);self.assertFalse(errors)
    def test_editor_rejects_2001_characters_then_saves_all_fields_and_other_records(self):
        app,root,errors,v=self.library();chosen=self.choose(v);key=str(Path(chosen[0]).relative_to(root));path=root/'library_notes.json';path.write_text(json.dumps({key:dict(text='old',custom=99),'other':dict(text='preserve')}));w=v.operations.note();edit=w.note_controls;edit['text'].delete('1.0','end');edit['text'].insert('1.0','测'*2001);before=path.read_bytes();self.assertFalse(edit['save']());self.assertEqual(path.read_bytes(),before)
        edit['text'].delete('1.0','end');edit['text'].insert('1.0','line one\nline two');edit['favorite'].set(True);edit['tags'].set('one,two');self.assertTrue(edit['save']());value=json.loads(path.read_text());self.assertEqual(value[key]['text'],'line one\nline two');self.assertEqual(value[key]['custom'],99);self.assertEqual(value[key]['tags'],['one','two']);self.assertEqual(value['other']['text'],'preserve');self.pump(app,.3);self.assertFalse(errors)
    def test_corrupt_notes_are_never_overwritten_from_library_editor(self):
        app,root,errors,v=self.library();self.choose(v);path=root/'library_notes.json';path.write_bytes(b'{broken original');self.assertIsNone(v.operations.note());self.assertEqual(path.read_bytes(),b'{broken original');self.assertIn('原文件已保留',v.status.get());self.assertFalse(errors)
    def test_portable_note_key_and_archive_note_fields_are_retained(self):
        app,root,errors,v=self.library();folder=Path(self.choose(v)[0]);relative=folder.relative_to(root);path=root/'library_notes.json';old=dict(text='portable\nnotes',tags=['keep'],favorite=True,custom={'exact':17});path.write_text(json.dumps({relative.as_posix():old}));w=v.operations.note();self.assertEqual(w.note_controls['text'].get('1.0','end-1c'),old['text']);self.assertTrue(w.note_controls['save']());value=json.loads(path.read_text('utf-8'));self.assertEqual(list(value),[relative.as_posix()]);self.assertEqual(value[relative.as_posix()]['custom'],old['custom']);self.pump(app,.3)
        path.unlink();archive=folder/'_archive_note.json';archive.write_text(json.dumps(old));before=archive.read_bytes();w=v.operations.note();self.assertEqual(w.note_controls['text'].get('1.0','end-1c'),old['text']);self.assertTrue(w.note_controls['save']());self.assertEqual(archive.read_bytes(),before);self.assertEqual(json.loads(path.read_text('utf-8'))[str(relative)]['custom'],old['custom']);self.assertFalse(errors)
    def test_existing_images_use_viewer_without_generation_and_force_is_explicit(self):
        from PIL import Image
        app,root,errors,v=self.library();folder=Path(self.choose(v)[0]);Image.new('RGB',(640,320),'#242424').save(folder/'圈速单.png')
        with patch('race_report.generate') as generated:w=v.operations.image('圈速单.png');self.pump(app,.35);generated.assert_not_called();self.assertIsNotNone(app.report_image_viewer.viewport.image)
        with patch('control_report_images.generate') as generated:v.operations.regenerate();generated.assert_called_once_with(v.app,str(folder),True)
        self.assertFalse(errors)
    def test_menu_retains_legacy_operations_and_rechecks_invalid_selection(self):
        app,root,errors,v=self.library();ops=v.operations;keys={a.key for a in ops.menu.actions};self.assertTrue({'same','compare','reference','analyze','images','compress','recover','export','import','options','progress'}<=keys);self.assertFalse(v.buttons['note'].enabled);self.assertFalse(v.buttons['laps'].enabled)
        self.choose(v,7);self.assertFalse(next(a for a in ops.menu.actions if a.key=='compare').enabled());self.choose(v);self.assertTrue(v.buttons['note'].enabled);self.assertTrue(next(a for a in ops.menu.actions if a.key=='same').enabled());self.assertFalse(errors)
    def test_compare_keeps_six_records_and_reads_settings_on_gui_thread(self):
        app,root,errors,v=self.library();self.choose(v,6);ops=v.operations
        for item in v.selected_items():item['fastest_file']='fastest.json'
        with patch('json_store.load',return_value=dict(payload='unaltered')) as loaded,patch('laps.write_compare') as written,patch('control_library_actions.os.startfile') as opened:ops.compare();self.pump(app,.35);self.assertEqual(loaded.call_count,6);self.assertEqual(len(written.call_args.args[2]),6);opened.assert_called_once()
        self.assertFalse(errors)
    def test_archive_options_snapshot_verify_and_format_before_worker(self):
        app,root,errors,v=self.library();self.choose(v);ops=v.operations;ops.format.set('7z');ops.verify.set(True)
        with patch('control_library_actions.filedialog.askdirectory',return_value=str(root/'exports')),patch('control_batch.start') as start,patch('session_archive.export_session') as export:ops.export();worker=start.call_args.args[3];ops.format.set('ZIP');worker('Logs/a');self.assertEqual(export.call_args.kwargs['format'],'7z')
        with patch('control_library_actions.filedialog.askopenfilenames',return_value=['one.zip']),patch('control_batch.start') as start,patch('session_archive.import_session') as imported:ops.import_packages();worker=start.call_args.args[3];ops.verify.set(False);worker('one.zip');self.assertTrue(imported.call_args.kwargs['verify'])
        self.assertFalse(errors)
    def test_format_save_failure_rolls_back_and_preserves_corrupt_original(self):
        app,root,errors,v=self.library();ops=v.operations;path=root/'archive_settings.json';path.write_text('corrupt');ops.format.set('7z');self.assertFalse(ops.preference.submit());self.assertEqual(path.read_text(),'corrupt');self.assertEqual(ops.format.get(),'ZIP');self.assertFalse(errors)
    def test_compress_recover_and_same_session_keep_backend_arguments(self):
        app,root,errors,v=self.library();folder=self.choose(v)[0];ops=v.operations
        with patch('storage.compress_session',return_value=dict(compressed_bytes=42)) as compress:ops.compress();self.pump(app,.3);compress.assert_called_once_with(folder)
        with patch('storage.recover_session',return_value=Path(folder)) as recover:ops.recover();self.pump(app,.3);recover.assert_called_once_with(folder,root);ops.make_report.assert_called_once_with(Path(folder))
        self.choose(v)
        with patch('management.show_lap_selection') as same:ops.same();same.assert_called_once_with(v.app,root,folder)
        self.assertFalse(errors)
    def test_closing_manager_does_not_cancel_accepted_background_write(self):
        app,root,errors,v=self.library();gate=threading.Event();entered=threading.Event();out=root/'accepted.txt'
        def write():entered.set();gate.wait(3);out.write_text('complete');return out
        try:v.operations.background(write,Mock());self.assertTrue(entered.wait(1));v.close();gate.set();self.pump(app,.3);self.assertEqual(out.read_text(),'complete')
        finally:gate.set()
        self.assertFalse(errors)
    def test_language_and_theme_keep_filters_selection_and_original_precision(self):
        from track_names import display
        app,root,errors,v=self.library();chosen=self.choose(v);track=v.selected_items()[0]['track'];v.track.set(track);v.filters_changed();v.table.widths['best']=123.125;app.set_theme('light');v.operations.menu.open();app.toggle_language();self.pump(app,.15);self.assertEqual(v.table.selection(),chosen);self.assertEqual(v.track.get(),track);self.assertEqual(v.table.widths['best'],123.125);self.assertEqual(v.table.labels['track'],'Circuit');self.assertEqual(v.table.rows[chosen[0]][4],'Race');self.assertEqual(v.facet_boxes['track'].display(track),display(track));self.assertIsNone(v.operations.menu.popup);self.assertFalse(errors)
    def test_viewer_generation_callback_survives_manager_close(self):
        from PIL import Image
        from control_report_images import generate
        app,root,errors,v=self.library();folder=Path(self.choose(v)[0]);Image.new('RGB',(640,320)).save(folder/'圈速单.png');v.operations.image('圈速单.png');self.pump(app,.3);v.close()
        with patch('race_report.generate',return_value={}):generate(v.app,folder,True);self.pump(app,.4)
        self.assertIsNotNone(app.report_image_viewer.viewport.image);self.assertFalse(errors)
    def test_video_empty_state_and_clear_action_match_result_search(self):
        from control_video_results import show
        app,root,errors=self.app();videos.video(root,'one');w=show(app,root);self.pump(app,.3);w.results_search.set('missing');self.pump(app,.12);self.assertEqual(w.results_table.empty_label.cget('text'),'没有匹配的结果');w.results_table.empty_button.invoke();self.assertEqual(w.results_search.get(),'');self.assertEqual(len(w.results_table.rows),1);self.assertFalse(errors)
    def test_batch_empty_failed_filter_returns_to_all_and_clear_search_is_immediate(self):
        from control_batch import start
        app,root,errors=self.app();job=start(app,'赛事包导出任务',['one.zip'],lambda _:dict(errors=[]));self.pump(app,.3);job.view.set('failed');job.render();self.assertEqual(job.table.empty_label.cget('text'),'没有失败项');job.table.empty_button.invoke();self.assertEqual(job.view.get(),'all');self.assertEqual(len(job.table.rows),1)
        job.query.set('missing');self.pump(app,.12);self.assertEqual(job.table.empty_label.cget('text'),'没有匹配的任务');job.table.empty_button.invoke();self.assertEqual(job.query.get(),'');self.assertFalse(errors)
    def test_hud_note_cancel_close_keeps_sampler_running(self):
        import management
        app,root,errors=self.app(True)
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.make_report'):
            app.start(True);self.pump(app,.2);hud=app.hud;v=management.show_library(hud,root,Mock(),Mock()).library;self.pump(app,.3);self.choose(v);note=v.operations.note();note.note_controls['text'].insert('1.0','draft');before=hud.engine.recorder.samples
            with patch('control_confirm.ask',return_value='cancel'):app.stop_hud()
            self.pump(app,.15);self.assertFalse(hud.closing);self.assertGreater(hud.engine.recorder.samples,before);self.assertIn('继续记录',app.status.get());note.destroy();hud.close();self.pump(app,.4)
        self.assertFalse(errors)
    def test_starting_hud_and_its_menu_reuse_existing_center_manager(self):
        app,root,errors,v=self.library();window=v.window
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.make_report'):
            app.start(True);self.pump(app,.2);self.assertIs(app.library(),window);self.assertIs(app.hud.show_library(),window);app.hud.close();self.pump(app,.3);self.assertTrue(window.winfo_exists())
        self.assertFalse(errors)
    def test_center_library_locks_reference_on_current_live_hud(self):
        app,root,errors,v=self.library();self.choose(v);item=v.selected_items()[0];item['fastest_file']='fixture.json';fake=SimpleNamespace(path='fixture',info={'number':3})
        hud=SimpleNamespace(closing=False,root=app.root,engine=SimpleNamespace(lock=threading.Lock(),reference=None,aligner=None),reference_kind=app.reference_kind,reference_settings={},reference_locked=app.reference_locked,reference_on=app.reference_on,reference_auto=app.reference_auto,apply_reference=Mock())
        previous=app.hud;app.root.after_cancel(app.job);app.hud=hud
        try:
            with patch('reference.ReferenceLap.load',return_value=fake):
                v.operations.reference();self.pump(app,.1)
                for done,result,error in app.tasks.completions():done(result,error)
                self.assertIs(hud.engine.reference,fake);hud.apply_reference.assert_called_once()
        finally:app.hud=previous;app.job=app.root.after(100,app.tick)
        self.assertFalse(errors)
