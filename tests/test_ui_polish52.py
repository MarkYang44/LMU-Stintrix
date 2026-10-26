"""Native workflows for explicit choices, draft boundaries and discoverability."""
import os,unittest,json
from types import SimpleNamespace
from unittest.mock import patch
from tests import test_ui_efficiency as helpers


class Rules(unittest.TestCase):
    def test_validation_keeps_ranges_and_identifies_cross_field_errors(self):
        import sampling,vehiclelab,endurance
        from preference_error import PreferenceError
        self.assertEqual(sampling.validate_settings(dict(min_hz=300,max_hz=400))['min_hz'],300)
        for validate,value,fields in [(sampling.validate_settings,dict(fixed_hz='nan'),('fixed_hz',)),(sampling.validate_settings,dict(min_hz=500,max_hz=300),('min_hz','max_hz')),(vehiclelab.profile,dict(pressure_min=210,pressure_max=200),('pressure_min','pressure_max')),(endurance.settings,dict(pace_window=1.5),('pace_window',))]:
            with self.assertRaises(PreferenceError) as caught:validate(value)
            self.assertIsInstance(caught.exception,ValueError);self.assertEqual(caught.exception.fields,fields)
    def test_search_matches_raw_and_bilingual_labels(self):
        from control_settings_search import matches
        entries=[dict(key='draw_hz',label='手动 HUD 刷新 / Hz',section='输入采样'),dict(key='pressure_min',label='胎压下限 / kPa',section='车辆策略')]
        self.assertEqual(matches(entries,'draw_hz'),entries[:1]);self.assertEqual(matches(entries,'胎压'),entries[1:]);self.assertEqual(matches(entries,''),[])


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class PolishUITests(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def test_explicit_exit_choices_and_modal_leave_recording_continuous(self):
        from control_confirm import draft_choice
        app,root,errors=self.app();seen=[]
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.make_report'):
            app.start(True);self.pump(app,.3);engine=app.hud.engine;recorder=engine.recorder;before=recorder.samples
            def choose():
                window=app.root._stintrix_confirm;seen.extend((k,b.label) for k,b in window.confirm_buttons.items());window.confirm_buttons['cancel'].invoke()
            app.root.after(180,choose);self.assertEqual(draft_choice(app.root,closing=True,exiting=True),'cancel')
            self.assertEqual({key for key,_ in seen},{'save','discard','cancel'});self.assertTrue(all(label not in ('是','否','Yes','No') for _,label in seen));self.assertIs(app.hud.engine,engine);self.assertIs(engine.recorder,recorder);self.assertGreater(recorder.samples,before);self.assertFalse(errors)
    def test_shortcut_keep_reopen_cancel_and_save_close(self):
        from control_shortcuts import show
        app,root,errors=self.app();window=show(app);self.pump(app,.1);window.shortcut_fields['visibility'].set('Ctrl+Alt+G');window.shortcut_enabled.set(False)
        with patch('control_confirm.draft_choice',return_value='cancel'):window.shortcut_close()
        self.assertTrue(window.winfo_exists())
        with patch('control_confirm.draft_choice',return_value='keep'):window.shortcut_close()
        self.assertFalse((root/'hotkey_settings.json').exists());window=show(app);self.pump(app,.1);self.assertEqual(window.shortcut_fields['visibility'].get(),'Ctrl+Alt+G');self.assertFalse(window.shortcut_enabled.get());self.assertTrue(window.shortcut_dirty())
        with patch('control_confirm.draft_choice',return_value='save'):window.shortcut_close()
        self.pump(app,.1);self.assertFalse(window.winfo_exists());self.assertFalse(json.loads((root/'hotkey_settings.json').read_text())['enabled']);self.assertIsNone(app.shortcut_draft);self.assertFalse(errors)
    def test_async_shortcut_save_failure_and_new_edits_keep_window_open(self):
        from control_shortcuts import show
        app,root,errors=self.app();window=show(app);window.shortcut_fields['visibility'].set('Ctrl+Alt+G');callbacks=[];submitted=[]
        def configure(settings,done):submitted.append(settings);callbacks.append(done)
        with patch.object(app.shortcuts,'configure',side_effect=configure),patch('control_confirm.draft_choice',return_value='save'):
            window.shortcut_close();callbacks.pop()(False,'occupied');self.assertTrue(window.winfo_exists());self.assertTrue(window.shortcut_dirty())
            window.shortcut_close();window.shortcut_fields['visibility'].set('Ctrl+Alt+H');app.shortcuts.settings.update(submitted[-1]);callbacks.pop()(True,'saved')
        self.assertTrue(window.winfo_exists());self.assertTrue(window.shortcut_dirty());self.assertFalse(errors)
    def test_columns_disable_pin_keep_on_page_change_and_defaults_are_drafts(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.4);table=app.tree;window=table.show_columns();self.pump(app,.1)
        original=table.displaycolumns.copy();was=window.column_frozen['date'].get();window.column_visible['date'].set(False);self.assertFalse(window.column_pins['date'].enabled);window.column_pins['date'].toggle();self.assertEqual(window.column_frozen['date'].get(),was)
        self.assertEqual(table.displaycolumns,original);self.assertFalse((root/'table_views.json').exists())
        app.show_page(0);self.pump(app,.1);app.show_page(1);self.pump(app,.4);window=app.tree.show_columns();self.assertFalse(window.column_visible['date'].get());self.assertTrue(window.column_dirty())
        with patch('control_confirm.draft_choice',return_value='discard'):window.column_reset()
        self.assertFalse((root/'table_views.json').exists());self.assertTrue(window.column_dirty())
        with patch('control_confirm.draft_choice',return_value='save'):window.column_close()
        self.assertTrue((root/'table_views.json').exists());self.assertFalse(errors)
    def test_retained_closed_draft_blocks_exit_without_explicit_discard(self):
        from control_shortcuts import show
        app,root,errors=self.app();window=show(app);window.shortcut_fields['visibility'].set('Ctrl+Alt+G')
        with patch('control_confirm.draft_choice',return_value='keep'):window.shortcut_close()
        with patch.object(app,'close') as closing,patch('control_confirm.ask',return_value='cancel'):app.request_close();closing.assert_not_called()
        with patch.object(app,'close') as closing,patch('control_confirm.ask',return_value='discard'):app.request_close();closing.assert_called_once()
        self.assertIsNone(app.shortcut_draft);self.assertFalse(errors)
    def test_inline_errors_mark_focus_and_prevent_config_writes(self):
        from control_layouts import show
        app,root,errors=self.app();window=show(app);window.layout_name.set('Test');window.layout_fields['opacity'].set('1');window.layout_save();self.pump(app,.1)
        field,_,hint=window.layout_errors.fields['opacity'];self.assertTrue(field.error);self.assertIn('20',hint.cget('text'));self.assertFalse((root/'hud_layouts.json').exists())
        window.layout_fields['opacity'].set('60');self.assertFalse(field.error);window.destroy();app.show_page(2);self.pump(app,.4)
        body=next(body for title,body in app.settings_anchors if title=='输入采样');variables=app.pages.pages[2].forms['sampling'];variables['min_hz'].set('500');variables['max_hz'].set('300');body.form_save();self.pump(app,.1)
        feedback=body.form_feedback;self.assertTrue(feedback.fields['min_hz'][0].error);self.assertTrue(feedback.fields['max_hz'][0].error);self.assertFalse((root/'settings.json').exists());self.assertFalse(errors)
    def test_settings_search_locates_fields_and_opens_threshold_editor(self):
        app,root,errors=self.app();app.show_page(2);self.pump(app,.4);search=app.settings_search;search.variable.set('draw_hz');search.open_first();self.pump(app,.1)
        entry=next(e for e in app.settings_index if e['key']=='draw_hz');self.assertIs(app.root.focus_get(),entry['widget'].entry);self.assertFalse((root/'settings.json').exists())
        search.variable.set('胎压');search.update();self.assertEqual(len(search.entries),2);search.jump(search.entries[0]);self.pump(app,.1)
        window=app.profile_dialog;self.assertIs(window.focus_get(),window.profile_fields['pressure_min'].entry);window.profile_variables['pressure_min'].set('bad');window.profile_save();self.assertTrue(window.profile_fields['pressure_min'].error);self.assertFalse((root/'vehicle_settings.json').exists());self.assertFalse(errors)
    def test_full_cell_tooltip_copy_and_lifetime_do_not_mutate_selection(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.4);table=app.tree;iid=table.get_children()[0];table.selection_set((iid,));table.cursor=iid;table.focus_column='track';value=dict(zip(table.columns,table.rows[iid]))['track'];table.widths['track']=65*table.s;table.layout()
        table.stretch.discard('track');table.layout();self.pump(app,.1)
        x=next(x for key,x,_ in table.positions() if key=='track');event=SimpleNamespace(x=x+14,y=table.rowheight/2,x_root=app.root.winfo_rootx()+300,y_root=app.root.winfo_rooty()+400)
        table.hover(event);self.pump(app,.55);self.assertIsNotNone(table.tooltip.window)
        with patch.object(table,'clipboard_clear') as clear,patch.object(table,'clipboard_append') as append:
            table.copy_cell();append.assert_called_with(str(value));table.copy_rows();self.assertIn(str(value),append.call_args.args[0]);self.assertEqual(clear.call_count,2)
        self.assertEqual(table.selection(),(iid,));table.yview('moveto',.2);self.assertIsNone(table.tooltip.window);table.hover(event);app.show_page(0);self.pump(app,.5);self.assertIsNone(table.tooltip.pending);self.assertFalse(errors)
    def test_copy_menu_is_contextual_and_long_menu_still_reaches_last_action(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.4);menu=app.review_menu;menu.open();self.pump(app,.1)
        self.assertNotIn('copy-cell',menu.positions);menu.close();app.tree.selection_set((app.tree.get_children()[0],));menu.open();self.pump(app,.1);self.assertIn('copy-cell',menu.positions)
        menu.key(SimpleNamespace(keysym='End',state=0));self.pump(app,.1);self.assertEqual(menu.active,'delete');top,bottom=menu.positions['delete'];self.assertGreaterEqual(menu.canvas.canvasy(0)+menu.canvas.winfo_height()+1,bottom);self.assertFalse(errors)
    def test_preview_zoom_pan_focus_and_fit_never_apply_a_layout(self):
        from control_layouts import show
        app,root,errors=self.app();window=show(app);self.pump(app,.2);preview=window.layout_preview;before=window.layout_state['draft'].copy();old=preview.ratio;pointer=(200,100);ox,oy=preview.origin;world=((pointer[0]-ox)/old,(pointer[1]-oy)/old)
        preview.zoom_at(2,*pointer);self.assertAlmostEqual(preview.ratio,old*2);ox,oy=preview.origin;self.assertAlmostEqual(ox+world[0]*preview.ratio,pointer[0]);self.assertAlmostEqual(oy+world[1]*preview.ratio,pointer[1])
        preview.start_pan(SimpleNamespace(x=20,y=30));preview.move_pan(SimpleNamespace(x=80,y=90));preview.end_drag();self.assertNotEqual(preview.pan,[0,0]);preview.fit_selected();self.assertIsNotNone(preview.focus_rect);preview.fit_all();self.assertIsNone(preview.focus_rect);self.assertEqual(preview.zoom,1);self.assertFalse(window.layout_dirty());self.assertFalse((root/'hud_layouts.json').exists());self.assertFalse(errors)
    def test_home_controls_fit_with_recent_session_in_both_languages(self):
        from control_fields import Select
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.5);app.show_page(0);self.pump(app,.2)
        def walk(parent):
            for widget in parent.winfo_children():yield widget;yield from walk(widget)
        for _ in range(2):
            bottom=app.scroll.winfo_rooty()+app.scroll.winfo_height();controls=[w for w in walk(app.content) if isinstance(w,Select) and w.variable in (app.mode_label,app.channel,app.window)]
            self.assertEqual(len(controls),3)
            for widget in controls:self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),bottom)
            self.assertTrue(app.recent_widgets[0].recent_full);app.toggle_language();self.pump(app,.3)
        self.assertFalse(errors)
