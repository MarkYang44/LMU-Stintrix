"""Editorial guide cards, folded review filters, one settings save surface and calmer toolbars."""
import os,time,unittest
from tests import test_ui_polish69 as helpers


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_wide_guide_cards_place_photo_beside_notes_and_share_one_action_row(self):
        from guide_cards import Split,Sources,Picture
        app,root,errors=self.app();app.root.geometry('1500x900');app.request_page(4);self.settle(app);self.pump(app,.2)
        card=app.guide_page.results.winfo_children()[0];body=card.body
        split=next(w for w in walk(body) if isinstance(w,Split));self.assertTrue(split.wide)
        self.assertLessEqual(split.media.winfo_rootx()+split.media.winfo_width(),split.info.winfo_rootx());self.assertEqual(split.media.winfo_rooty(),split.info.winfo_rooty())
        self.assertTrue(any(isinstance(w,Picture) for w in walk(split.media)))
        sources=next(w for w in body.pack_slaves() if isinstance(w,Sources));row=sources.heading.master
        labels=[getattr(w,'label','') for w in row.winfo_children()]
        self.assertTrue(labels[0].endswith('收藏'));self.assertTrue(labels[1].startswith('车型建议'));self.assertTrue(labels[-1].startswith('来源链接'))
        picks=row.winfo_children()[1];picks.invoke();self.pump(app,.1);self.assertTrue(picks.label.endswith('▾'));self.assertTrue(picks.selected)
        sources.toggle();self.pump(app,.05);slaves=body.pack_slaves();holder=next(w for w in slaves if w.winfo_class()=='Frame' and w not in (split,sources))
        self.assertLess(slaves.index(holder),slaves.index(sources));self.assertTrue(sources.heading.selected)
        picks.invoke();sources.toggle();self.pump(app,.05);self.assertTrue(picks.label.endswith('▸'));self.assertFalse(picks.selected);self.assertFalse(holder.winfo_manager());self.assertFalse(errors)

    def test_split_stacks_below_its_threshold_and_returns_beside_when_wide(self):
        import tkinter as tk
        from guide_cards import Split
        root=tk.Tk();self.addCleanup(root.destroy);root.geometry('600x400+40+40');host=tk.Frame(root,width=600);host.pack(fill='x')
        split=Split(host);tk.Frame(split.media,height=120,width=10).pack(fill='x');tk.Frame(split.info,height=80,width=10).pack(fill='x')
        for _ in range(5):root.update()
        self.assertFalse(split.wide);self.assertGreater(split.info.winfo_y(),split.media.winfo_y());self.assertEqual(split.info.winfo_width(),split.winfo_width())
        root.geometry('1200x400');[root.update() for _ in range(5)]
        self.assertTrue(split.wide);self.assertEqual(split.info.winfo_y(),split.media.winfo_y());self.assertLess(split.media.winfo_width(),split.info.winfo_width())

    def test_review_rows_lead_while_filters_fold_into_a_counted_toggle_and_chips(self):
        app,root,errors=self.app(True);app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        f=app.review_filters;button=f.disclosure;row=app.search_target.master
        self.assertFalse(f.winfo_manager());self.assertEqual(button.label,'筛选条件');self.assertFalse(button.selected)
        line=app.selection_line;self.assertLess(line.winfo_rooty()-(row.winfo_rooty()+row.winfo_height()),40);self.assertLess(app.tree.winfo_rooty()-(line.winfo_rooty()+line.winfo_height()),20)
        f.toggle_filters();self.pump(app,.05);self.assertTrue(f.winfo_ismapped());self.assertTrue(button.selected);self.assertLess(f.winfo_rooty(),app.tree.winfo_rooty())
        track=next(v for v in f.lookup['track'].values() if v);f.state.update(track=track);f.update_options(f.items);f.callback()
        f.toggle_filters();self.pump(app,.05);self.assertEqual(button.label,'筛选条件 · 1');self.assertFalse(button.selected)
        self.assertTrue(f.chips.winfo_ismapped());self.assertLess(f.chips.winfo_rooty(),app.tree.winfo_rooty());self.assertEqual(len(app.tree.get_children()),4)
        next(w for w in f.chip_widgets if w.label=='清除条件').invoke();self.pump(app,.05)
        self.assertEqual(button.label,'筛选条件');self.assertFalse(f.chips.winfo_manager());self.assertEqual(len(app.tree.get_children()),8)
        app.request_page(0);self.settle(app);app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        self.assertFalse(app.review_filters.winfo_manager());self.assertFalse(errors)

    def test_parameter_cards_have_one_save_surface_and_a_quiet_header_status(self):
        from control_theme import T
        app,root,errors=self.app();app.request_page(2);self.settle(app,lambda:'sampling' in getattr(app,'form_panels',{}))
        self.assertFalse([w for w in walk(app.pages.pages[2].frame) if getattr(w,'label',None)=='应用并保存'])
        body=app.form_panels['sampling'];status=body.form_status;forms=app.pages.pages[2].forms['sampling'];bar=app.form_bar
        def settled(color):
            # Busy CI runners can stretch or finish the 160 ms fade inside one
            # update; assert the logical state, then wait for motion to end.
            self.assertEqual(status.state[1],color);deadline=time.monotonic()+3
            while status.motion.jobs and time.monotonic()<deadline:app.root.update();time.sleep(.005)
            self.assertFalse(status.motion.jobs);return status.label.cget('fg')
        self.assertFalse(status.label.winfo_manager());self.assertFalse(bar.packed)
        forms['fixed_hz'].set('240');self.pump(app,.05)
        self.assertEqual(status.label.winfo_manager(),'place');self.assertIn('1',status.label.cget('text'));self.assertEqual(settled(T.ACCENT),T.ACCENT)
        self.assertAlmostEqual(status.label.winfo_rooty()+status.label.winfo_height()/2,body.heading.winfo_rooty()+body.heading.winfo_height()/2,delta=2)
        self.assertTrue(bar.packed);self.assertTrue(bar.save.enabled)
        forms['min_hz'].set('500');forms['max_hz'].set('300');self.assertFalse(body.form_validate(True));self.assertEqual(settled(T.RED),T.RED)
        body.form_reset();self.pump(app,.05);self.assertFalse(status.label.winfo_manager());self.assertFalse(bar.packed);self.assertFalse(errors)

    def test_record_tabs_use_selected_state_and_fixed_bar_keeps_frequent_actions(self):
        app,root,errors=self.app(True);app.request_page(6)
        loaded=lambda:getattr(app,'record_loaders',{}).get('best') is not None and app.record_loaders['best'].page is not None and app.record_loaders['best'].page.fixed
        self.settle(app,loaded);p=app.record_loaders['best'].page;tabs=app.personal_record_tabs
        self.assertTrue(tabs['best'].selected);self.assertFalse(tabs['best'].primary);self.assertTrue(p.fixed['curve'].primary)
        self.assertEqual(set(p.fixed),{'curve','training','card','details'});self.assertTrue(any(a.key=='mode' for a in p.menu.actions));self.assertFalse(errors)

    def test_start_menu_entry_lives_in_settings_and_rail_keeps_only_privacy_promise(self):
        from control_sections import Disclosure
        app,root,errors=self.app();self.pump(app,.1)
        # A one-time system setup belongs with the other app-wide preferences.
        self.assertFalse([w for w in walk(app.content) if isinstance(w,Disclosure) and w.key=='windows-entry'])
        app.request_page(2);self.settle(app,lambda:'start_menu' in getattr(app,'app_preference_controls',{}))
        controls=app.app_preference_controls;self.assertEqual(app.settings_anchors[-1][0],'界面与系统')
        self.assertEqual((controls['start_menu'].label,controls['remove_start_menu'].label),('添加 / 更新','移除入口'))
        self.assertTrue(controls['shortcuts'].winfo_exists())
        self.assertEqual([w.cget('text') for w in app.shell.footer.winfo_children() if w.winfo_class()=='Label'],['●  LOCAL & PRIVATE']);self.assertFalse(errors)

    def test_data_selection_orders_filters_before_refresh_like_other_lists(self):
        app,root,errors=self.app(True);app.request_page(3);self.settle(app);app.data_tasks.select('packages')
        self.settle(app,lambda:getattr(app,'data_browser',None) is not None and app.data_browser.alive())
        labels=[getattr(w,'label',None) for w in app.search_target.master.pack_slaves()]
        self.assertLess(labels.index('筛选条件'),labels.index('刷新记录'));self.assertFalse(errors)
