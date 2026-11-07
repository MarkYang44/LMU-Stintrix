"""Segmented choices, two-column parameter forms and the session selection line."""
import json,os,time,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


def wait(root,condition,seconds=3):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


@unittest.skipUnless(os.name=='nt','Native Tk')
class Control(unittest.TestCase):
    def control(self,**options):
        import tkinter as tk
        from control_widgets import Segmented
        root=tk.Tk();root.geometry('520x120+40+40');self.addCleanup(root.destroy);root._motion_keyboard_until=0
        variable=tk.StringVar(root,value='b');calls=[]
        control=Segmented(root,variable,['a','b','c'],lambda:calls.append(variable.get()),**options);control.pack(fill='x',padx=10,pady=10);root.update()
        return root,variable,control,calls

    @patch('control_motion.system_motion',return_value=True)
    def test_click_selects_once_and_the_marker_slides_only_for_pointer_input(self,_motion):
        root,variable,control,calls=self.control()
        left,right=control.spans[2];control.event_generate('<Button-1>',x=round((left+right)/2),y=10)
        self.assertEqual(variable.get(),'c');self.assertEqual(calls,['c']);self.assertTrue(control.motion.jobs)
        self.assertTrue(wait(root,lambda:not control.motion.jobs));self.assertEqual(control.position,2.)
        control.event_generate('<Button-1>',x=round((left+right)/2),y=10);self.assertEqual(calls,['c'])
        control.focus_force();root.update();control.event_generate('<Home>');self.assertEqual(variable.get(),'a');self.assertFalse(control.motion.jobs);self.assertEqual(control.position,0.)
        control.event_generate('<Right>');control.event_generate('<End>');self.assertEqual(calls,['c','a','b','c'])

    def test_external_values_redraw_without_commands_and_disabled_controls_ignore_input(self):
        root,variable,control,calls=self.control(captions={'a':'Alpha'},titles={'a':'Alpha (full)'})
        variable.set('a');self.assertEqual(control.position,0.);self.assertEqual(calls,[])
        self.assertIn('Alpha',[control.itemcget(i,'text') for i in control.find_all() if control.type(i)=='text'])
        control.set_enabled(False);left,right=control.spans[1];control.event_generate('<Button-1>',x=round((left+right)/2),y=10)
        self.assertEqual(variable.get(),'a');self.assertEqual(calls,[])
        control.destroy();variable.set('c');self.assertFalse(variable.trace_info())


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_run_page_hud_choices_are_one_click_segments(self):
        from control_widgets import Segmented
        app,root,errors=self.app();self.settle(app)
        controls=app.run_choices;self.assertEqual({key:c.variable for key,c in controls.items()},{'mode':app.mode_label,'channel':app.channel,'window':app.window})
        self.assertTrue(all(isinstance(c,Segmented) and c.winfo_ismapped() for c in controls.values()))
        calls=[]
        with patch.object(app,'set_hud',side_effect=lambda *a:calls.append(a)):
            control=controls['mode'];left,right=control.spans[1];control.event_generate('<Button-1>',x=round((left+right)/2),y=10)
            control=controls['window'];left,right=control.spans[2];control.event_generate('<Button-1>',x=round((left+right)/2),y=10)
        self.assertEqual(calls,[('mode','curves'),('window','20')]);self.assertEqual(app.mode_label.get(),'纯净 · 仅曲线')
        app.mode_label.set('标准面板');self.assertEqual(controls['mode'].position,0.);self.assertFalse(errors)

    def test_parameter_forms_use_two_columns_on_wide_cards_and_one_when_narrow(self):
        from control_widgets import Segmented
        app,root,errors=self.app();app.root.geometry('1600x1000');app.request_page(2);self.settle(app,lambda:'sampling' in getattr(app,'form_panels',{}))
        self.pump(app,.1);body=app.form_panels['sampling'];fields=body.form_feedback.fields;forms=app.pages.pages[2].forms['sampling']
        self.assertEqual(body.form_grid.columns,2);self.assertIsInstance(fields['mode'][0],Segmented)
        same=lambda a,b:abs(fields[a][0].winfo_rooty()-fields[b][0].winfo_rooty())<=2
        self.assertTrue(same('mode','draw_mode'));self.assertTrue(same('min_hz','max_hz'));self.assertLess(fields['min_hz'][0].winfo_rootx(),fields['max_hz'][0].winfo_rootx())
        # Every condition group starts its own row, so a note never moves fields between columns.
        self.assertFalse(same('fixed_hz','min_hz'));forms['mode'].set('fixed');self.pump(app,.05);x=fields['min_hz'][0].winfo_rootx()
        forms['mode'].set('dynamic');self.pump(app,.05);self.assertEqual(fields['min_hz'][0].winfo_rootx(),x)
        forms['mode'].set('fixed');self.pump(app,.05);self.assertFalse(app.form_bar.packed)
        control=fields['mode'][0];left,right=control.spans[1];control.event_generate('<Button-1>',x=round((left+right)/2),y=10);self.pump(app,.05)
        self.assertEqual(forms['mode'].get(),'dynamic');self.assertTrue(app.form_bar.packed)
        app.form_panels['sampling'].form_reset();app.root.geometry('1060x700');self.pump(app,.3)
        self.assertEqual(body.form_grid.columns,1);self.assertLess(fields['min_hz'][0].winfo_rooty(),fields['max_hz'][0].winfo_rooty());self.assertFalse(errors)

    def test_selection_line_names_the_session_without_moving_the_rows(self):
        app,root,errors=self.app(True);app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        line=app.selection_line;t=app.tree;top=t.winfo_rooty();height=line.winfo_height()
        self.assertEqual(line.full[0],'');self.assertIn('8',line.full[1]);self.assertLess(line.winfo_rooty(),top)
        t.selection_set((t.get_children()[0],));self.pump(app,.05)
        lead,rest=line.full;self.assertIn('斯帕',lead);self.assertIn('2:26.100',lead);self.assertIn('Porsche',rest);self.assertNotIn('斯帕',rest.split(' · ')[1])
        self.assertEqual((t.winfo_rooty(),line.winfo_height()),(top,height))
        t.selection_set(t.get_children()[:3]);self.pump(app,.05);self.assertEqual(line.full[0],'已选 3 场');self.assertEqual(t.winfo_rooty(),top)
        self.assertNotIn('已选',' '.join(w.cget('text') for w in walk(app.shell.action_host) if w.winfo_class()=='Label'));self.assertFalse(errors)

    def test_archive_format_switches_and_saves_in_one_click(self):
        from control_widgets import Segmented
        app,root,errors=self.app();app.show_page(3);self.pump(app,.35);app.data_tasks.select('packages');self.pump(app,.1)
        control=next(w for w in walk(app.content) if isinstance(w,Segmented) and w.variable is app.archive_format)
        left,right=control.spans[1];control.event_generate('<Button-1>',x=round((left+right)/2),y=10);self.pump(app,.1)
        self.assertEqual(app.archive_format.get(),'7z');self.assertEqual(json.loads((root/'archive_settings.json').read_text())['format'],'7z');self.assertFalse(errors)

    def test_view_switchers_share_one_segmented_bar_apart_from_actions(self):
        from control_video_widgets import Tab,TabBar
        app,root,errors=self.app(True);app.request_page(6);self.settle(app);tabs=app.personal_record_tabs
        self.assertTrue(all(isinstance(t,Tab) for t in tabs.values()));bar=tabs['best'].master.master;self.assertIsInstance(bar,TabBar)
        self.assertTrue(tabs['best'].selected);self.assertEqual(tabs['best'].itemcget(tabs['best'].surface,'state'),'normal')
        others=[t for k,t in tabs.items() if k!='best'];self.assertTrue(all(t.itemcget(t.surface,'state')=='hidden' for t in others))
        self.assertLess(bar.winfo_width(),app.content.winfo_width())
        app.request_page(2);self.settle(app,lambda:'endurance' in getattr(app,'form_panels',{}))
        self.assertTrue(all(isinstance(button,Tab) for button,_ in app.settings_spy.tabs))
        app.request_page(3);self.settle(app);self.assertTrue(all(isinstance(t,Tab) for t in app.data_tasks.buttons.values()));self.assertFalse(errors)

    def test_personal_bests_tag_the_fastest_session_for_each_layout_and_car(self):
        app,root,errors=self.app(True);app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        t=app.tree;lap=t.columns.index('lap');times={iid:t.rows[iid][lap] for iid in t.get_children()}
        self.assertEqual(sorted(times[i] for i in t.marked),['1:42.100','2:26.100'])
        best=next(i for i in t.marked if times[i]=='2:26.100');other=next(i for i in t.get_children() if times[i]=='2:26.400')
        t.selection_set((best,));self.pump(app,.05);self.assertTrue(app.selection_line.full[0].endswith('2:26.100 PB'))
        t.selection_set((other,));self.pump(app,.05);self.assertNotIn('PB',app.selection_line.full[0])
        self.assertIn('PB',[t.viewport.itemcget(i,'text') for i in t.viewport.find_all() if t.viewport.type(i)=='text']);self.assertFalse(errors)
