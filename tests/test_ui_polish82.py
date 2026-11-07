"""Ctrl+K command palette, one start/stop control, a two-line last session and the guide's fixed search."""
import json,os,time,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


def wait(root,condition,seconds=4):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


class Ranking(unittest.TestCase):
    def command(self,key,title,group='操作',hint='',words=()):
        from control_palette import Command
        return Command(key,title,group,lambda:None,hint,'',words)

    def test_prefix_beats_word_start_beats_hints_and_substrings(self):
        from control_palette import rank
        items=[self.command('inside','xhudx'),self.command('hint','其他',hint='HUD 说明'),self.command('word','演示 HUD'),self.command('prefix','HUD 布局')]
        self.assertEqual([c.key for c in rank(items,'hud')],['prefix','word','hint','inside'])
        self.assertEqual([c.key for c in rank(items,'hud 布局')],['prefix'])

    def test_both_languages_match_and_loose_letters_stay_inside_one_word(self):
        from control_palette import rank
        items=[self.command('review','赛事复盘','页面'),self.command('bcn','Barcelona','赛道指南'),self.command('tyre','Tire pressure minimum / kPa','设置')]
        self.assertEqual([c.key for c in rank(items,'session')],['review'])
        self.assertEqual([c.key for c in rank(items,'bcn')],['bcn'])
        self.assertEqual([c.key for c in rank(items,'spa')],[])

    def test_empty_query_leads_with_recent_then_pages_and_actions_only(self):
        from control_palette import rank
        items=[self.command('page:0','运行与 HUD','页面'),self.command('start','启动记录'),self.command('setting:x','燃油余量','设置'),self.command('track:spa','Spa','赛道指南')]
        found=rank(items,'',recent=['setting:x','gone'])
        self.assertEqual([(c.key,c.group) for c in found],[('setting:x','最近使用'),('page:0','页面'),('start','操作')])

    def test_search_hand_offs_follow_every_match_and_never_rank(self):
        from control_palette import rank
        items=[self.command('page:1','赛事复盘','页面'),self.command('search:reviews','在赛事复盘中搜索','搜索')]
        self.assertEqual([c.key for c in rank(items,'复盘')],['page:1','search:reviews'])
        self.assertEqual([c.key for c in rank(items,'zzzz')],['search:reviews'])


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_ctrl_k_opens_at_once_filters_as_you_type_and_enter_navigates(self):
        app,root,errors=self.app();self.settle(app);p=app.palette
        app.root.event_generate('<Control-k>');self.assertTrue(p.opened);self.assertIs(p.frame.master,app.root)
        self.assertEqual({c.group for _,_,c in p.rows},{'页面','操作'});self.assertEqual(p.rows[0][2].key,'page:0')
        p.query.set('图鉴');self.assertEqual(p.rows[0][2].key,'page:5');self.assertEqual(p.rows[0][2].shortcut,'Ctrl+6')
        p.move(1);self.assertEqual(p.index,1);p.move(-5);self.assertEqual(p.index,0)
        p.choose(keyboard=True);self.assertFalse(p.opened);self.settle(app,lambda:app.page==5)
        self.assertEqual(app._palette_recent[0],'page:5');p.open();self.assertEqual((p.rows[0][2].key,p.rows[0][2].group),('page:5','最近使用'))
        p.toggle();self.assertFalse(p.opened);self.assertFalse(errors)

    def test_escape_restores_focus_and_outside_clicks_or_page_switches_close(self):
        app,root,errors=self.app();self.settle(app);p=app.palette;button=app.shell.theme_button
        app.root.focus_force();button.focus_set();self.pump(app,.05)
        p.open();self.pump(app,.02);p.entry.event_generate('<Escape>');self.pump(app,.02)
        self.assertFalse(p.opened);self.assertIs(app.root.focus_get(),button)
        p.open();app.request_page(1);self.assertFalse(p.opened);self.settle(app)
        p.open();self.pump(app,.02);app.shell.title.event_generate('<Button-1>',x=2,y=2);self.pump(app,.02);self.assertFalse(p.opened)
        p.open();self.pump(app,.02);p.entry.event_generate('<Button-1>',x=4,y=4);self.pump(app,.02);self.assertTrue(p.opened);p.close()
        self.assertFalse(errors)

    def test_only_actions_that_apply_now_are_offered(self):
        from control_palette import commands
        app,root,errors=self.app();self.settle(app)
        keys={c.key for c in commands(app)};self.assertTrue({'start','demo','layouts','shortcuts','theme','language'}<=keys);self.assertNotIn('stop',keys)
        with patch.object(app,'active',return_value=True):
            keys={c.key for c in commands(app)};self.assertIn('stop',keys);self.assertIn('diagnostics',keys);self.assertFalse({'start','demo'}&keys)
        self.assertFalse(errors)

    def test_a_setting_opens_from_anywhere_before_its_page_was_built(self):
        app,root,errors=self.app();self.settle(app);p=app.palette
        self.assertFalse(getattr(app,'settings_index',None))
        p.open();p.query.set('燃油余量');self.assertEqual(p.rows[0][2].key,'setting:reserve_l');self.assertEqual(p.rows[0][2].hint,'车辆策略')
        p.choose(keyboard=True);self.settle(app,lambda:app.page==2)
        field=next(e['widget'] for e in app.settings_index if e['key']=='reserve_l')
        self.assertTrue(wait(app.root,lambda:app.root.focus_get() is not None and app.root.focus_get().master is field))
        top=field.winfo_rooty();self.assertGreaterEqual(top,app.scroll.winfo_rooty());self.assertLess(top,app.scroll.winfo_rooty()+app.scroll.winfo_height())
        self.assertFalse(errors)

    def test_guide_entries_open_a_filtered_guide_and_text_continues_as_a_review_search(self):
        app,root,errors=self.app(True);self.settle(app);p=app.palette
        p.open();p.query.set('Bahrain');self.assertEqual(p.rows[0][2].key,'track:bahrain');p.choose(keyboard=True)
        self.settle(app,lambda:app.page==4 and app.guide_page is not None and app.guide_page.card_count>0)
        g=app.guide_page;self.assertEqual(g.state['query'],'Bahrain');self.assertEqual([item['slug'] for item,_ in g.rows],['bahrain'])
        p.open();p.query.set('Fuji');p.index=next(i for i,(_,_,c) in enumerate(p.rows) if c.key=='search:reviews');p.choose(keyboard=True)
        self.settle(app,lambda:app.page==1 and app.tree is not None)
        self.assertTrue(wait(app.root,lambda:app.search.get()=='Fuji' and len(app.tree.get_children())==4));self.assertFalse(errors)

    def test_run_page_shows_one_primary_control_for_the_current_state(self):
        app,root,errors=self.app();self.settle(app);self.pump(app,.1)
        self.assertTrue(app.start_button.winfo_ismapped());self.assertFalse(app.stop_button.winfo_manager());self.assertFalse(app.stop_button.enabled)
        with patch.object(app,'active',return_value=True):
            app.update_toolbar();self.pump(app,.05)
            self.assertTrue(app.stop_button.winfo_ismapped());self.assertTrue(app.stop_button.primary);self.assertFalse(app.start_button.winfo_manager())
        app.update_toolbar();self.pump(app,.05)
        self.assertTrue(app.start_button.winfo_ismapped());self.assertFalse(app.stop_button.winfo_manager());self.assertFalse(errors)

    def test_last_session_reads_as_two_short_lines(self):
        from report_state import remember
        from control_recent_session import update
        app,root,errors=self.app();self.settle(app);folder=root/'Logs'/'done';folder.mkdir(parents=True)
        meta=dict(status='complete',source='LMU',track='Monza',vehicle='McLaren 720S GT3 Evo',ended_utc='2026-10-08T12:09:00Z');(folder/'session.json').write_text(json.dumps(meta))
        app.recent.folder=folder;app.recent.meta=meta;remember(folder,dict(state='building',steps={},updated_utc='one'));update(app);self.pump(app,.15)
        label,buttons=app.recent_widgets;detail=label.recent_detail
        self.assertTrue(label.cget('text').startswith('上一场 · '));self.assertNotIn('…',label.cget('text'))
        self.assertTrue(detail.cget('text').startswith('McLaren 720S GT3 Evo · 2026-10-08 12:09 UTC'));self.assertIn('报告生成中',detail.cget('text'))
        self.assertIn('赛事已保存，报告正在生成',label.recent_full);self.assertLessEqual(label.winfo_reqheight()+detail.winfo_reqheight(),buttons['review'].winfo_height()+4)
        (folder/'review.html').write_text('fixture');remember(folder,dict(state='ready',steps=dict(review=dict(state='ready')),updated_utc='two'));update(app);self.pump(app,.05)
        self.assertNotIn('报告',detail.cget('text'));self.assertTrue(buttons['review'].enabled);self.assertFalse(errors)

    def test_guide_search_is_the_fixed_toolbar_field(self):
        app,root,errors=self.app();app.request_page(4);self.settle(app);g=app.guide_page;host=app.shell.action_host
        labels=[w.label for w in host.winfo_children() if hasattr(w,'label')]
        self.assertIs(g.search_field.master,host);self.assertIs(g.fixed_actions['search'],g.search_field);self.assertNotIn('搜索 / 筛选',labels);self.assertIn('筛选条件',labels)
        self.assertGreater(g.search_field.winfo_width(),g.search_field.winfo_reqwidth())
        self.assertFalse([w for w in g.filter_card.body.winfo_children() if w.winfo_class()=='Frame' and any(getattr(c,'entry',None) for c in w.winfo_children())])
        app.scroll.yview_moveto(.4);self.pump(app,.08);top=g.search_field.winfo_rooty();position=app.scroll.yview()[0]
        app.focus_search();self.pump(app,.05)
        self.assertIs(app.root.focus_get(),g.search_entry);self.assertEqual(g.search_field.winfo_rooty(),top);self.assertAlmostEqual(app.scroll.yview()[0],position,places=3)
        g.variables['query'].set('Bahrain');g.search_field.flush();self.settle(app);self.assertEqual(len(g.rows),1)
        g.variables['group'].set('LMGT3');g.filter_changed();self.settle(app);self.assertEqual(g.filter_button.label,'筛选条件 · 1');self.assertFalse(errors)
