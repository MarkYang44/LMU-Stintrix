"""Atomic native page commits, interrupted handoffs and fixed library navigation."""
import os,time,unittest
from unittest.mock import patch
from tests import test_ui_efficiency as helpers


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def settle(self,app,condition=lambda:True):
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            app.root.update();time.sleep(.003)
            if condition() and app.pages.pending is None and app.pages.active.complete and not app.shell.covering:return
        self.fail('Native page did not settle')
    def test_every_commit_has_actions_layout_and_complete_guide_before_reveal(self):
        app,root,errors=self.app(True);shell=app.shell;original=shell.reveal_page;commits=[]
        def reveal(*args):
            guide=app.guide_page
            commits.append((app.page,len(shell.action_host.winfo_children()),guide.card_count if guide else None,bool(guide and guide.card_job),app.scroll.coords(app.content_item)))
            return original(*args)
        with patch.object(shell,'reveal_page',side_effect=reveal):
            for index in (1,4,5,2,0,2):app.request_page(index);self.settle(app)
        self.assertEqual([r[0] for r in commits],[1,4,5,2,0,2])
        for index,actions,cards,pending,coords in commits:
            if index!=0:self.assertGreater(actions,0)
            if index in (4,5):self.assertEqual(cards,3);self.assertFalse(pending)
            self.assertEqual(coords,[0,0]);self.assertNotIn('page',shell.motion.jobs)
        self.assertFalse(errors)
    def test_cover_is_a_native_sibling_over_actions_and_document_and_resizes(self):
        app,root,errors=self.app();app.request_page(2);app.root.update_idletasks();s=app.shell
        self.assertTrue(s.covering);self.assertIs(s.surface.cover.master,s.stage);self.assertIs(s.action_host.master,s.stage)
        self.assertIs(s.scroll.master.master,s.stage);self.assertTrue(s.surface.cover.winfo_ismapped())
        app.root.geometry('1160x760');app.root.update_idletasks();self.assertEqual(s.surface.cover.winfo_width(),s.stage.winfo_width());self.assertEqual(s.surface.cover.winfo_height(),s.stage.winfo_height())
        self.settle(app);self.assertFalse(s.surface.cover.winfo_manager());self.assertIsNone(s.surface.job);self.assertFalse(errors)
    def test_obsolete_surface_token_cannot_reveal_new_page(self):
        app,root,errors=self.app();s=app.shell;old=s.cover_page();latest=s.cover_page()
        self.assertFalse(s.reveal_page(old));self.assertTrue(s.covering);self.assertTrue(s.surface.cover.winfo_ismapped())
        self.assertTrue(s.reveal_page(latest));self.assertFalse(s.covering);self.assertIsNone(s.surface.job);self.assertFalse(errors)
    def test_obsolete_readiness_callback_cannot_commit_or_replace_new_page(self):
        app,root,errors=self.app();held=[]
        def build():held.append(app.pages.hold());app.label(app.content,'fixture').pack()
        with patch.object(app,'tracks_page',side_effect=build):app.show_page(4,progressive=True)
        self.assertTrue(app.shell.covering);self.assertFalse(app.pages.active.complete);app.request_page(0);self.settle(app)
        with patch.object(app.shell,'reveal_page',wraps=app.shell.reveal_page) as revealed:held[0]();held[0]();revealed.assert_not_called()
        self.assertEqual(app.page,0);self.assertFalse(app.shell.covering);self.assertFalse(errors)
    def test_sync_failure_has_retry_and_navigation_remains_usable(self):
        app,root,errors=self.app()
        with patch.object(app,'data_page',side_effect=OSError('fixture unavailable')):app.show_page(3)
        self.assertFalse(app.shell.covering);self.assertIn('fixture unavailable',app.status.get());retry=next(c for c in self.walk(app.content) if getattr(c,'label',None)=='重试当前页面')
        retry.invoke();self.settle(app);self.assertTrue(hasattr(app,'data_tasks'));app.request_page(0);self.settle(app);self.assertFalse(errors)
    def test_generator_failure_clears_pending_work_and_empty_exception_keeps_type(self):
        app,root,errors=self.app()
        def broken():yield;raise RuntimeError()
        with patch.object(app,'settings_page',side_effect=broken):app.show_page(2,progressive=True);self.settle(app)
        self.assertIsNone(app.pages.job);self.assertIsNone(app.pages.generator);self.assertIn('RuntimeError',app.status.get());self.assertNotIn(2,app.pages.pages)
        app.request_page(2);self.settle(app);self.assertIn('sampling',app.pages.active.forms);self.assertFalse(errors)
    def test_async_guide_failure_is_recoverable_without_stuck_cover(self):
        app,root,errors=self.app()
        with patch('guide_cards.Cards.track',side_effect=ValueError('fixture card')):app.request_page(4);self.settle(app)
        self.assertIn('fixture card',app.status.get());self.assertFalse(app.shell.covering)
        app.show_page(4,progressive=True);self.settle(app);self.assertEqual(app.guide_page.card_count,3);self.assertFalse(errors)
    def test_internal_guide_failure_uses_latest_handoff_and_can_retry(self):
        app,root,errors=self.app();app.request_page(4);self.settle(app)
        with patch('guide_cards.Cards.track',side_effect=OSError('fixture pagination')):app.guide_page.turn(1);self.settle(app)
        self.assertIn('fixture pagination',app.status.get());self.assertFalse(app.shell.covering);app.request_page(4);self.settle(app);self.assertEqual(app.guide_page.card_count,3);self.assertFalse(errors)
    def test_failed_cached_resume_preserves_unsaved_parameter_draft_for_retry(self):
        app,root,errors=self.app();app.show_page(2);page=app.pages.active;page.forms['sampling']['fixed_hz'].set('731.125');app.show_page(0)
        page.sync.insert(0,lambda:(_ for _ in ()).throw(OSError('fixture external read')));app.request_page(2);self.settle(app)
        self.assertTrue(app.pages.active.failed);self.assertEqual(app.form_drafts['sampling']['fixed_hz'],'731.125')
        app.request_page(2);self.settle(app);self.assertEqual(app.pages.active.forms['sampling']['fixed_hz'].get(),'731.125');self.assertFalse(errors)
    def test_rapid_card_pagination_waits_for_final_cards_and_restores_top(self):
        app,root,errors=self.app();app.request_page(4);self.settle(app);g=app.guide_page;commits=[];original=app.shell.reveal_page
        def reveal(*args):commits.append((g.state['page'],g.card_count,g.card_job));return original(*args)
        app.scroll.yview_moveto(1)
        with patch.object(app.shell,'reveal_page',side_effect=reveal):
            for delta in (1,1,-1,1):g.turn(delta)
            self.assertTrue(app.shell.covering);self.settle(app)
        self.assertEqual(commits,[(2,3,None)]);self.assertEqual(app.scroll.canvasy(0),0);self.assertFalse(errors)
    def test_fixed_guide_actions_stay_visible_and_return_to_search_without_losing_selection(self):
        app,root,errors=self.app();app.request_page(4);self.settle(app);g=app.guide_page
        g.select(next(iter(g.library.recommendations)));chosen=list(g.state['comparison']);buttons=g.fixed_actions;top=buttons['search'].winfo_rooty();app.scroll.yview_moveto(.7);self.pump(app,.08)
        self.assertEqual(buttons['search'].winfo_rooty(),top);buttons['search'].invoke();self.assertIs(app.root.focus_get(),g.search_entry);self.assertEqual(g.state['comparison'],chosen)
        app.install_toolbar();g.turn(1);self.settle(app);self.assertTrue(all(button.winfo_exists() for pair in g.pagers for button in pair));self.assertFalse(errors)
    def test_data_section_handoff_keeps_table_identity_drafts_and_commits_after_restore(self):
        app,root,errors=self.app(True);app.show_page(3);self.pump(app,.25);table=app.tree;table.selection_set((table.get_children()[0],));selected=table.selection();app.data_tasks.select('renderer');app.renderer_path.set('draft renderer.exe')
        app.data_tasks.select('storage');self.assertIs(app.tree,table);self.assertEqual(table.selection(),selected);app.data_tasks.select('renderer');self.assertEqual(app.renderer_path.get(),'draft renderer.exe');self.assertFalse(app.shell.covering);self.assertFalse(errors)
    def test_reduced_motion_and_cached_drafts_use_no_page_animation(self):
        app,root,errors=self.app()
        with patch('control_motion.system_motion',return_value=False):
            app.show_page(2);form=app.pages.active.forms['sampling'];form['fixed_hz'].set('731.125');frame=app.content
            app.request_page(0);self.settle(app);app.request_page(2);self.settle(app)
        self.assertIs(app.content,frame);self.assertEqual(form['fixed_hz'].get(),'731.125');self.assertEqual(app.scroll.coords(app.content_item),[0,0]);self.assertFalse(app.shell.motion.jobs);self.assertFalse(errors)
    def test_leave_during_pending_guide_search_does_not_change_new_page(self):
        app,root,errors=self.app();app.request_page(5);self.settle(app);old=app.guide_page;old.variables['query'].set('Ferrari');self.assertIsNotNone(old.job);app.request_page(1);self.settle(app);self.pump(app,.25)
        self.assertTrue(old.closed);self.assertIsNone(old.job);self.assertIsNone(old.card_job);self.assertEqual(app.page,1);self.assertFalse(app.shell.covering);self.assertFalse(errors)
    def test_fixed_compare_action_returns_to_original_library_context(self):
        app,root,errors=self.app();app.request_page(4);self.settle(app);g=app.guide_page
        for key in list(g.library.recommendations)[:2]:g.select(key)
        chosen=list(g.state['comparison']);app.scroll.yview_moveto(.18);self.pump(app,.04);position=app.scroll.yview()[0]
        g.fixed_actions['compare'].invoke();self.settle(app);self.assertEqual(g.state['mode'],'compare');self.assertEqual(g.fixed_actions['compare'].label,'返回资料列表')
        g.fixed_actions['compare'].invoke();self.settle(app);self.assertEqual(g.state['mode'],'browse');self.assertEqual(g.state['comparison'],chosen);self.assertAlmostEqual(app.scroll.yview()[0],position,places=2);self.assertFalse(errors)
    def test_long_prepare_shows_hint_and_close_releases_pending_native_surface(self):
        app,root,errors=self.app();held=[]
        with patch.object(app,'tracks_page',side_effect=lambda:held.append(app.pages.hold())):app.show_page(4,progressive=True)
        surface=app.shell.surface;self.pump(app,.18);self.assertTrue(surface.hint.winfo_ismapped());app.close();app.close=lambda:None
        self.assertFalse(surface.covering);self.assertIsNone(surface.job);self.assertFalse(errors)
    def test_english_navigation_numbers_never_overlap_full_captions(self):
        from i18n import tr
        app,root,errors=self.app();app.toggle_language();app.root.geometry('1240x850');self.pump(app,.08);nav=app.shell.navigation
        text={nav.itemcget(item,'text'):nav.bbox(item) for item in nav.find_all() if nav.type(item)=='text'}
        for index,name in enumerate(nav.names):
            bounds=text[tr(name)];self.assertLessEqual(bounds[2],nav.winfo_width()+1)
            number=text.get(f'{index+1:02}')
            if number:self.assertGreaterEqual(number[0]-bounds[2],4)
        self.assertFalse(errors)
    def test_guide_layout_is_detached_before_record_toolbar_is_mounted(self):
        app,root,errors=self.app(True);app.request_page(5);self.settle(app);host=app.shell.action_host;old=host.flow_binding
        app.request_page(6);self.settle(app);self.pump(app,.2);self.assertIsNone(host.flow_binding);self.assertNotIn(old,host.bind('<Configure>') or '')
        best=app.record_loaders['best'].page
        for button in best.fixed.values():self.assertGreaterEqual(button.winfo_width(),button.winfo_reqwidth()-1);self.assertGreater(button.winfo_height(),20)
        self.assertFalse(errors)
    def walk(self,w):
        yield w
        for child in w.winfo_children():yield from self.walk(child)
