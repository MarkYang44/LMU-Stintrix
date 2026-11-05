"""Centred action rows, quiet unavailable deletes, readable recent sessions and fewer repeated controls."""
import json,os,tempfile,time,unittest
from pathlib import Path
from tests import test_ui_polish69 as helpers

ROOT=Path(__file__).resolve().parents[1]


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


def centre(widget):return widget.winfo_rooty()+widget.winfo_height()/2


class Text(unittest.TestCase):
    def test_recent_summary_localizes_circuit_and_formats_finish_time(self):
        import i18n
        from recent_session import summary
        meta=dict(track='Circuit de Spa-Francorchamps',vehicle='Porsche 911 GT3 R LMGT3',ended_utc='2026-10-08T14:09:30.512+02:00')
        try:
            self.assertEqual(summary(meta),'斯帕-弗朗科尔尚赛道 · Porsche 911 GT3 R LMGT3 · 2026-10-08 12:09 UTC')
            i18n.set_language('en');self.assertEqual(summary(meta),'Circuit de Spa-Francorchamps · Porsche 911 GT3 R LMGT3 · 2026-10-08 12:09 UTC')
        finally:i18n.set_language('zh')
        self.assertEqual(summary(dict(track='Fuji Speedway',started_utc='2026-10-01T20:00:00Z')),'富士赛车场 · 2026-10-01 20:00 UTC')
        self.assertEqual(summary(dict(track='Fuji Speedway',ended_utc='2026-10-01 21:30:00')),'富士赛车场 · 2026-10-01 21:30 UTC')
        self.assertEqual(summary(dict(track='Unknown Ring',ended_utc='not a time')),'Unknown Ring · not a time')

    def test_recent_state_follows_interface_language_without_rewriting_session(self):
        import i18n
        from recent_session import RecentSession
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            root=Path(temp);folder=root/'Logs'/'race';folder.mkdir(parents=True)
            source=folder/'session.json';source.write_text(json.dumps(dict(status='complete',track='Fuji Speedway',vehicle='BMW M4 LMGT3',ended_utc='2026-10-01T12:00:00+00:00')),encoding='utf-8')
            (root/'recent_session.json').write_text(json.dumps(dict(version=1,folder='Logs/race')),encoding='utf-8');before=source.read_bytes()
            tracker=RecentSession(root)
            try:
                self.assertEqual(tracker.state()['text'],'富士赛车场 · BMW M4 LMGT3 · 2026-10-01 12:00 UTC')
                i18n.set_language('en');self.assertEqual(tracker.state()['text'],'Fuji Speedway · BMW M4 LMGT3 · 2026-10-01 12:00 UTC')
            finally:i18n.set_language('zh')
            self.assertEqual(source.read_bytes(),before)

    def test_report_theme_presses_like_native_buttons_and_reduces_motion_gently(self):
        source=(ROOT/'src'/'interface_theme.js').read_text(encoding='utf-8')
        self.assertIn('transform:translateY(1px) scale(.97)',source);self.assertIn('@media(hover:hover) and (pointer:fine)',source)
        self.assertIn('transform .16s cubic-bezier(.23,1,.32,1)',source);self.assertNotIn('transition:background .15s',source)
        reduced=source[source.index('@media(prefers-reduced-motion:reduce)'):]
        self.assertIn('sl-fade',reduced);self.assertIn('background-color,border-color',reduced);self.assertNotIn('animation:none',reduced)


@unittest.skipUnless(os.name=='nt','Native Tk')
class Widgets(unittest.TestCase):
    def root(self):
        import tkinter as tk
        root=tk.Tk();root.geometry('600x300+40+40');self.addCleanup(root.destroy);return root

    def test_flow_rows_share_a_centre_line_and_wrap_at_natural_width(self):
        import tkinter as tk
        from control_flow import install
        root=self.root();row=tk.Frame(root);row.pack(fill='x');install(row)
        tall=tk.Frame(row,width=120,height=46);short=tk.Label(row,text='1 / 2');wide=tk.Frame(row,width=900,height=30)
        for _ in range(5):root.update()
        self.assertEqual(tall.winfo_y(),0);self.assertAlmostEqual(centre(short),centre(tall),delta=1)
        self.assertGreater(wide.winfo_y(),tall.winfo_height());self.assertEqual(wide.winfo_width(),row.winfo_width())
        self.assertEqual(row.winfo_height(),wide.winfo_y()+wide.winfo_height())

    def test_adjacent_hints_skip_the_initial_delay_only_after_one_was_read(self):
        import tkinter as tk,control_tooltip
        from control_tooltip import Tooltip
        root=self.root();label=tk.Label(root,text='hint');label.pack();root.update()
        control_tooltip._warm_until=0.;tip=Tooltip(label);self.addCleanup(tip.hide);delays=[];shows=[];original=label.after
        def after(ms,callback=None,*args):delays.append(ms);shows.append(callback);return original(ms,callback,*args)
        label.after=after
        # Hints cancelled before they appeared never shorten the next delay.
        tip.request('a','first',0,0);tip.hide();tip.request('b','second',0,0)
        self.assertEqual(delays,[control_tooltip.DELAY_MS]*2)
        label.after_cancel(tip.pending);shows[-1]()
        self.assertIsNotNone(tip.window);tip.hide();tip.request('c','third',0,0);self.assertEqual(delays[-1],control_tooltip.WARM_DELAY_MS)
        tip.hide();control_tooltip._warm_until=time.perf_counter()-1;tip.request('d','fourth',0,0);self.assertEqual(delays[-1],control_tooltip.DELAY_MS)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_delete_stays_quiet_until_a_record_is_selected(self):
        from control_theme import T
        app,root,errors=self.app(True);app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        delete=app.review_actions['delete'];self.assertFalse(delete.enabled)
        self.assertEqual(delete.itemcget(delete.caption,'fill'),T.MUTED);self.assertEqual(delete.itemcget(delete.surface,'outline'),T.EDGE)
        app.tree.selection_set((app.tree.get_children()[0],));app.update_selection_count();self.pump(app,.05)
        self.assertTrue(delete.enabled);self.assertEqual(delete.itemcget(delete.caption,'fill'),T.RED);self.assertFalse(errors)

    def test_guide_search_hints_describe_what_each_view_matches(self):
        app,root,errors=self.app();app.request_page(4);self.settle(app)
        self.assertEqual(app.guide_page.search_field.placeholder_label.cget('text'),'搜索赛道或地区')
        app.request_page(5);self.settle(app);self.assertEqual(app.guide_page.search_field.placeholder_label.cget('text'),'搜索车型、品牌或组别')
        app.toggle_language();self.settle(app,lambda:app.guide_page is not None)
        self.assertEqual(app.guide_page.search_field.placeholder_label.cget('text'),'Search car, brand or class');self.assertFalse(errors)

    def test_sampling_modes_lead_and_each_inactive_group_is_explained_once(self):
        app,root,errors=self.app();app.request_page(2);self.settle(app,lambda:'sampling' in getattr(app,'form_panels',{}))
        body=app.form_panels['sampling'];fields=body.form_feedback.fields;forms=app.pages.pages[2].forms['sampling']
        self.assertLess(fields['mode'][0].winfo_rooty(),fields['draw_mode'][0].winfo_rooty());self.assertLess(fields['draw_mode'][0].winfo_rooty(),fields['fixed_hz'][0].winfo_rooty())
        notes=lambda:[w for w in body.winfo_children() if w.winfo_class()=='Label' and w.winfo_manager() and '生效' in w.cget('text')]
        forms['mode'].set('fixed');forms['draw_mode'].set('sync');self.pump(app,.05)
        shown=notes();self.assertEqual([w.cget('text') for w in shown],['以下 5 项仅动态采样时生效','仅手动刷新时生效'])
        self.assertLess(fields['fixed_hz'][0].winfo_rooty(),shown[0].winfo_rooty());self.assertLess(shown[0].winfo_rooty(),fields['min_hz'][0].winfo_rooty())
        self.assertLess(fields['brake_pct'][0].winfo_rooty(),shown[1].winfo_rooty());self.assertLess(shown[1].winfo_rooty(),fields['draw_hz'][0].winfo_rooty())
        forms['mode'].set('dynamic');forms['draw_mode'].set('manual');self.pump(app,.05)
        self.assertEqual([w.cget('text') for w in notes()],['仅固定采样时生效']);self.assertFalse(errors)

    def test_record_details_keep_navigation_and_menu_without_repeating_toolbar_actions(self):
        app,root,errors=self.app(True);app.request_page(6)
        loaded=lambda:getattr(app,'record_loaders',{}).get('best') is not None and app.record_loaders['best'].page is not None and app.record_loaders['best'].page.fixed
        self.settle(app,loaded);p=app.record_loaders['best'].page
        self.assertFalse(p.detail_actions.winfo_manager());self.assertIs(p.buttons['more'].master,p.navigation);self.assertLessEqual({'curve','card','details'},set(p.fixed))
        self.pump(app,.1);label=next(w for w in p.navigation.winfo_children() if w.winfo_class()=='Label')
        self.assertAlmostEqual(centre(label),centre(p.buttons['previous']),delta=1)
        p.buttons['more'].invoke();self.pump(app,.1);self.assertIsNotNone(p.menu.popup);p.menu.close();self.assertFalse(errors)

    def test_run_tools_centre_the_silent_switch_on_the_button_row(self):
        from control_widgets import Switch
        app,root,errors=self.app();self.pump(app,.1)
        switch=next(w for w in walk(app.content) if isinstance(w,Switch) and w.text=='静默记录 · 隐藏全部 HUD')
        layout=next(w for w in walk(app.content) if getattr(w,'label',None)=='HUD 布局')
        self.assertAlmostEqual(centre(switch),centre(layout),delta=1);self.assertFalse(errors)

    def test_numbered_pages_open_from_ctrl_digits_without_motion(self):
        app,root,errors=self.app();app.root.focus_force();self.pump(app,.05);nav=app.shell.navigation
        app.root.event_generate('<Control-Key-3>');self.assertEqual(nav.selected,2);self.assertFalse(nav.motion.jobs)
        self.settle(app);self.assertEqual(app.page,2)
        app.root.event_generate('<Control-Key-7>');self.settle(app);self.assertEqual(app.page,6);self.assertFalse(errors)
