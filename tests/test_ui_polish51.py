"""Behavioral checks for draft safety, visual edits and persistent table context."""
import json,os,unittest
from types import SimpleNamespace
from unittest.mock import patch
from tests import test_hud_workflow_ui as workflows


class PresentationRules(unittest.TestCase):
    def test_recorded_combinations_and_real_screen_clamping(self):
        from shortcut_keys import captured
        from control_layout_preview import move_panel
        self.assertEqual(captured('F9',5),'Ctrl+Shift+F9')
        self.assertEqual(captured('a',0x20004),'Ctrl+Alt+A')
        self.assertIsNone(captured('Control_L',4))
        with self.assertRaises(ValueError):captured('F12',4)
        panel=dict(width=400,height=200)
        self.assertEqual(move_panel(panel,-1883,13,[(-1920,0,1920,1080),(0,0,2560,1440)],True),(-1880,10))
        x,y=move_panel(panel,-300,1600,[(-1920,0,1920,1080),(0,0,2560,1440)])
        self.assertTrue(any(sx<=x<=sx+sw-400 and sy<=y<=sy+sh-200 for sx,sy,sw,sh in [(-1920,0,1920,1080),(0,0,2560,1440)]))
    def test_capture_releases_and_restores_without_persisting_or_dispatching(self):
        from shortcut_service import ShortcutService
        from shortcut_keys import DEFAULTS
        service=ShortcutService.__new__(ShortcutService);calls=[];service.capture_owner=None;service.settings=dict(enabled=True,bindings=DEFAULTS);service.message='';service.closed=False
        service.native=SimpleNamespace(configure=lambda mapping,done:(calls.append(mapping),done(dict(ok=True))))
        service.show=lambda:self.fail('capture must not invoke actions');owner=object();ready=[]
        service.begin_capture(owner,ready.append);service.invoke('center');service.end_capture(owner)
        self.assertEqual(ready,[True]);self.assertEqual(calls,[{},DEFAULTS]);self.assertIsNone(service.capture_owner)
        warnings=[];service.notify=warnings.append;service.capture_owner=owner
        service.native.configure=lambda mapping,done:done(dict(ok=False,action='visibility'))
        service.end_capture(owner);self.assertIsNone(service.capture_owner);self.assertIn(DEFAULTS['visibility'],warnings[-1])


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class PolishUITests(unittest.TestCase):
    app=workflows.WorkflowUITests.app;pump=workflows.WorkflowUITests.pump
    def test_dirty_switch_cancel_and_close_reopen_preserve_even_invalid_fields(self):
        from control_layouts import show
        from hud_layouts import LayoutStore,defaults
        app,root,errors=self.app();store=LayoutStore(root);store.save('A',defaults(),defaults());other=defaults();other['panels']['main']['x']=500;store.save('B',other,defaults())
        window=show(app);self.pump(app);window.layout_name.set('Draft');window.layout_fields['x'].set('237')
        with patch('control_confirm.draft_choice',return_value='cancel'):window.layout_select.choose(0)
        self.assertEqual(window.layout_fields['x'].get(),'237');self.assertTrue(window.layout_dirty());self.assertEqual(store.current()['panels']['main']['x'],500)
        window.layout_fields['width'].set('bad')
        with patch('control_confirm.draft_choice',return_value='keep'):window.layout_close()
        window=show(app);self.pump(app);self.assertEqual(window.layout_name.get(),'Draft');self.assertEqual(window.layout_fields['width'].get(),'bad');self.assertTrue(window.layout_dirty());self.assertFalse(errors)
        window.layout_fields['width'].set('640')
        with patch('control_confirm.draft_choice',return_value='save'):window.layout_select.choose(0)
        self.assertEqual(store.load()['profiles']['Draft']['panels']['main']['x'],237);self.assertEqual(window.layout_name.get(),'A');self.assertFalse(window.layout_dirty())
    def test_canvas_drag_resize_and_keyboard_only_change_draft(self):
        from control_layouts import show
        app,root,errors=self.app();window=show(app);self.pump(app);window.layout_fields['x'].set('250');window.layout_fields['y'].set('250');self.pump(app,.1)
        preview=window.layout_preview;before=dict(window.layout_state['draft']['panels']['main']);preview.nudge(SimpleNamespace(keysym='Right',state=1));self.assertEqual(float(window.layout_fields['x'].get()),260)
        preview.paint();box=preview.boxes['main'];x=(box[0]+box[2])/2;y=(box[1]+box[3])/2
        preview.press(SimpleNamespace(x=x,y=y));preview.motion(SimpleNamespace(x=x+20,y=y+5));preview.drag=None
        self.assertNotEqual(float(window.layout_fields['x'].get()),260);preview.paint();box=preview.boxes['main'];old=float(window.layout_fields['width'].get())
        preview.press(SimpleNamespace(x=box[2]-1,y=box[3]-1));preview.motion(SimpleNamespace(x=box[2]+15,y=box[3]+10));preview.drag=None
        self.assertGreater(float(window.layout_fields['width'].get()),old);self.assertFalse((root/'hud_layouts.json').exists());self.assertTrue(window.layout_dirty());self.assertFalse(errors)
    def test_idle_summary_and_explicit_display_choices_match_next_start(self):
        from hud_layouts import LayoutStore,defaults
        app,root,errors=self.app();snapshot=defaults();snapshot.update(mode='curves',window='20');snapshot['panels']['weather']['visible']=True;LayoutStore(root).save('Race',snapshot,defaults())
        app.refresh_run_configuration();self.assertEqual(app.mode_label.get(),'纯净 · 仅曲线');self.assertEqual(app.window.get(),'20');self.assertIn('Race',app.run_layout_summary.cget('text'))
        with patch('hud_layouts.LayoutStore.load',side_effect=AssertionError('unchanged idle refresh must use cached presentation')):app.refresh_run_configuration()
        app.set_hud('mode','controls');app.set_hud('window','5')
        with patch('control_settings.ROOT',root):app.set_panel_visibility('endurance','weather',False)
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.make_report'):
            app.start(True);self.pump(app,.2);self.assertEqual(app.hud.hud_mode.get(),'controls');self.assertEqual(app.hud.window.get(),'5');self.assertFalse(app.hud.layout_visibility['weather'])
            self.assertEqual(LayoutStore(root).load()['profiles']['Race']['mode'],'curves');self.assertFalse(errors)
    def test_recording_combinations_duplicate_feedback_and_focus_cancel(self):
        from control_shortcuts import show
        app,root,errors=self.app();window=show(app);self.pump(app);before=dict(app.shortcuts.settings['bindings']);window.shortcut_record('visibility');self.pump(app,.05)
        self.assertIsNotNone(app.shortcuts.capture_owner);window.shortcut_key(SimpleNamespace(keysym='F9',state=5));self.assertIsNone(app.shortcuts.capture_owner)
        self.assertEqual(window.shortcut_fields['visibility'].get(),'Ctrl+Shift+F9');self.assertEqual(app.shortcuts.settings['bindings'],before)
        window.shortcut_fields['lock'].set('Ctrl+Shift+F9');self.assertIn('相同快捷键',window.shortcut_hints['lock'].get());window.shortcut_save();self.assertFalse((root/'hotkey_settings.json').exists())
        window.shortcut_record('visibility');window.destroy();self.assertIsNone(app.shortcuts.capture_owner);self.assertFalse(errors)
    def test_table_preferences_keep_selection_scroll_and_restore_on_reentry(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.5);table=app.tree;chosen=table.get_children()[0];table.selection_set((chosen,));table.scroller.move(40);self.pump(app,.1)
        offset=table.offset;window=table.show_columns();window.column_visible['car'].set(False);window.column_save();self.pump(app,.1)
        self.assertNotIn('car',table.displaycolumns);self.assertEqual(table.selection(),(chosen,));self.assertEqual(table.offset,offset)
        table.widths['date']=233*table.s;table.remember_columns();table.xview('moveto',.7);fixed={k:x for k,x,pinned in table.positions() if pinned};self.assertAlmostEqual(fixed['date'],table.gutter)
        for value in window.column_visible.values():value.set(False)
        window.column_save();self.assertIn('至少保留一列',window.column_status.get());self.assertTrue(table.displaycolumns)
        app.show_page(0);self.pump(app,.1);app.show_page(1);self.pump(app,.5)
        self.assertNotIn('car',app.tree.displaycolumns);self.assertAlmostEqual(app.tree.widths['date']/app.tree.s,233);self.assertEqual(app.tree.selection(),(chosen,));self.assertFalse(errors)
    def test_short_sort_labels_keep_stored_values_and_full_popup_text(self):
        app,root,errors=self.app(True);app.show_page(1);self.pump(app,.4);filters=app.review_filters;choice=filters.choices['sort']
        full=next(label for label,index in filters.lookup['sort'].items() if index==11);choice.variable.set(full);choice.event_generate('<<ComboboxSelected>>');self.pump(app,.1)
        self.assertEqual(filters.state['sort'],11);self.assertEqual(choice.display(full),full);self.assertIn(full,choice.compact_labels);self.assertLess(len(choice.compact_labels[full]),len(full));self.assertFalse(errors)
        app.toggle_language();self.pump(app,.3);choice=app.review_filters.choices['sort']
        for value in choice.values:
            import i18n
            label=i18n.tr(choice.compact_labels[value]);self.assertLessEqual(choice.font.measure(label),choice.winfo_width()-66*choice.s,label)
    def test_theme_and_language_rebuild_remove_old_toolbar_callbacks(self):
        app,root,errors=self.app(True)
        for theme in ('light','dark'):
            app.show_page(1);self.pump(app,.2);app.set_theme(theme);self.pump(app,.15)
            app.show_page(0);self.pump(app,.1);app.show_page(1);self.pump(app,.2)
        app.toggle_language();self.pump(app,.3)
        top=app.tree.viewport.winfo_rooty()-app.scroll.winfo_rooty()
        self.assertGreaterEqual((app.scroll.winfo_height()-top)/app.tree.rowheight,2);self.assertFalse(errors)
