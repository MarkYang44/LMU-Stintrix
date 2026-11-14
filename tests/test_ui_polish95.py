"""AC EVO galleries browse like the LMU guide; empty lists centre their message."""
import os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_ui_polish69 as helpers

ROOT=Path(__file__).resolve().parents[1]


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


class Terminology(unittest.TestCase):
    def test_one_name_per_concept_in_interface_text(self):
        """赛事包, 赛事记录, 比赛日志 and 完整记录管理: interface text never drifts back."""
        import re
        retired=('比赛包','比赛记录管理','DuckDB 比赛记录','插件目录中的比赛记录','比赛记录已保存')
        found=[]
        for path in sorted((ROOT/'src').glob('*.py')):
            if path.name=='evo_reports.py':continue  # exported report content is left as published
            for literal in re.findall(r"'([^'\n]*)'",path.read_text(encoding='utf-8')):
                if any(term in literal for term in retired) or literal=='赛事日志':found.append((path.name,literal))
        self.assertEqual(found,[])
        import json
        english=json.loads((ROOT/'src/locales/en.json').read_text(encoding='utf-8'))
        for key in ('导出赛事包（可多选）','导入赛事包（可多选）','Stintrix · 完整记录管理','这张图片尚未生成；无完成圈时请切换比赛日志。'):self.assertIn(key,english)
        self.assertEqual(english['比赛日志'],'Race log');self.assertEqual(english['有比赛日志图片'],'Has race log image')

    def test_english_interface_text_uses_sentence_case(self):
        """One capitalization convention in English (Windows sentence case); proper nouns,
        acronyms, page names and the Lap A / Lap B feature keep their capitals."""
        import json,re
        english=json.loads((ROOT/'src/locales/en.json').read_text(encoding='utf-8'))
        proper=set('''HUD HUDs LMU EVO AC CSV XML HTML ZIP PNG SDK RaceCom Windows macOS Mac Apple DuckDB Le Mans Ultimate Stintrix STX Ctrl Enter Esc PB BOP GT3 LMGT3 Hypercar ID UTC MiB Hz OCR POV Studio Vision Launch Services DMG SHA256 NTFS JSON API Generate.exe Cmd Command Shift Alt Tab F1 F2 F5 F10 GTD DOM Start Menu Store Explorer Finder Dock Image Excel Microsoft Google TC ABS ESC Qualify Practice Race Warmup Multiplayer'''.split())
        minor={'and','or','of','to','the','a','an','in','for','on','with','by','per','vs','as','at','from','into'}
        def title_case(value):
            words=re.findall(r"[A-Za-z][A-Za-z'.0-9-]*",value)
            rest=[w for w in words[1:] if w.lower() not in minor and w not in proper and not (len(w)>1 and w.isupper()) and not any(c.isdigit() for c in w) and len(w)>1]
            return len(words)>1 and bool(rest) and all(w[0].isupper() for w in rest)
        allowed={'16:9 · PNG · Full HD','Extract Lap A','Extract Lap B','Go to Run & HUD','Lap A / Lap B','Select Lap A / Lap B','Stintrix · Lap A / Lap B'}
        self.assertEqual(sorted({value for value in english.values() if title_case(value)}-allowed),[])
        # The rail reads as sentence case too, as in Windows Settings.
        for key,value in (('赛事复盘','Session review'),('赛道指南','Circuit guide'),('车型图鉴','Car catalog'),('图像与数据','Reports & data')):self.assertEqual(english[key],value)

    def test_page_subtitles_state_purpose_not_gestures(self):
        """Each list teaches its open gesture in one place (the review selection line, F1)."""
        import control_center
        self.assertFalse([text for text in control_center.SUBTITLES if '双击' in text or 'Enter' in text])
        for name in ('control_podiums.py','control_history.py','evo_control.py'):
            source=(ROOT/'src'/name).read_text(encoding='utf-8')
            self.assertNotIn('双击记录或按 Enter',source,name);self.assertNotIn('双击打开',source,name)

    def test_recording_manager_shows_lap_times_like_the_rest_of_the_app(self):
        from types import SimpleNamespace
        from control_library import Library
        columns=[('date','',1),('track','',1),('vehicle','',1),('best','',1),('stable','',1)]
        item=dict(date='2026-10-08T12:00:00',track='Spa',track_layout='',vehicle='Car',time_s=146.1,session_type='Race',race_mode='unknown',stability_s=.4321,source='Logs',status='complete',note='',traffic=False)
        row=dict(zip([key for key,_,_ in columns],Library.format_entry(SimpleNamespace(columns=columns),item)))
        self.assertEqual(row['best'],'2:26.100');self.assertEqual(row['stable'],'0.432')
        self.assertEqual(dict(zip([key for key,_,_ in columns],Library.format_entry(SimpleNamespace(columns=columns),dict(item,time_s=None))))['best'],'—')


@unittest.skipUnless(os.name=='nt','Native Tk')
class EvoGallery(unittest.TestCase):
    def test_fixed_toolbar_result_line_filters_and_comparison_tray(self):
        script=r'''
import sys,time,traceback,tkinter as tk
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'),patch('evo_art.download',side_effect=AssertionError('No automatic network')):
 app=ControlCenter();app.root.maxsize(4096,4096);app.root.geometry('1060x700+20+20');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(5);pump(.6);g=app.evo_gallery;shell=app.shell;host=shell.action_host
 # Search, filters and paging live in the fixed toolbar, on one line at the minimum width.
 assert g.search.master is host and app.search_target is g.search and g.search.placeholder=='搜索车型或品牌'
 placed=[c for c in host.winfo_children() if c.winfo_manager()]
 assert host.winfo_height()<=max(c.winfo_height() for c in placed)+1,(host.winfo_height(),[c.winfo_height() for c in placed])
 # Notes on cards without artwork wrap instead of being clipped.
 notes=[w for c in g.cards for w in c.winfo_children() if isinstance(w,tk.Label) and w.cget('text').startswith('图片尚未')]
 assert notes and all(float(str(n.cget('wraplength')))>0 for n in notes)
 # Reset shows only while something narrows the catalogue; chips name the active filters.
 assert not g.reset_link.winfo_manager() and not g.filter_panel.winfo_manager()
 g.variables['group'].set('gt3');pump(.2)
 assert g.reset_link.winfo_ismapped() and list(g.filter_chips.buttons)==['group'] and g.filter_button.label.endswith('1')
 g.filter_chips.buttons['group'].invoke();pump(.2);assert g.variables['group'].get()=='' and not g.reset_link.winfo_manager()
 g.filter_button.invoke();pump(.3);assert g.filter_panel.winfo_ismapped() and g.filter_button.selected
 # The comparison tray appears with the first car, stays put while scrolling and toggles.
 assert not shell.tray_host.winfo_manager()
 names=[e['name'] for e in g.visible_entries[:2]]
 g.car_buttons[names[0]].invoke();pump(.1);assert shell.tray_host.winfo_ismapped() and not g.compare_button.enabled
 g.car_buttons[names[1]].invoke();pump(.1);assert g.compare_button.enabled
 top=g.compare_button.winfo_rooty();app.scroll.yview_moveto(.5);pump(.1);assert g.compare_button.winfo_rooty()==top
 g.compare_button.invoke();pump(.6);assert g.state['mode']=='compare' and g.compare_button.label=='返回车型列表'
 assert not any(button.enabled for button in g.toolbar_pager)
 g.compare_button.invoke();pump(.4);assert g.state['mode']=='browse' and g.compare_button.label=='查看车型对比'
 g.clear_button.invoke();pump(.1);assert not shell.tray_host.winfo_manager()
 # Leaving the page retires the tray; the circuits keep their own search wording.
 g.select_car(names[0]);app.show_page(4);pump(.6)
 assert not shell.tray_host.winfo_children()
 g=app.evo_gallery;assert g.search.placeholder=='搜索赛道或布局' and g.filter_button is None
 assert not errors,errors;app.request_close();pump(.1)
print('EVO gallery: fixed toolbar, quiet result line, chips, reset and tray OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as folder:
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=folder,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',LMU_STINTRIX_REDUCED_MOTION='1',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_every_record_view_keeps_its_actions_in_the_fixed_toolbar(self):
        app,root,errors=self.app(True);app.root.geometry('1240x850');app.request_page(6);self.settle(app);self.pump(app,.3)
        host=app.shell.action_host
        for kind in ('best','podium','history','official'):
            if kind!='best':app.personal_record_tabs[kind].invoke();self.settle(app);self.pump(app,.3)
            page=app.record_loaders[kind].page
            self.assertTrue(page.fixed,kind);self.assertTrue(all(b.master is host for b in page.fixed.values()),kind)
            self.assertTrue(next(iter(page.fixed.values())).primary,kind)
            for row in page.action_rows:self.assertFalse(row.winfo_manager(),kind)
            for key,button in page.fixed.items():
                if key in page.buttons:self.assertEqual(button.enabled,page.buttons[key].enabled,(kind,key))
            if kind!='official':
                # The menu ends the row, as on session review.
                more=page.menu.trigger;self.assertIs(more.master,host)
                self.assertAlmostEqual(more.winfo_x()+more.winfo_width(),host.winfo_width(),delta=2)
            if kind=='podium':self.assertFalse(page.buttons['retry'].winfo_manager())
            if kind=='history':
                # One line between search and rows: the filtered count closes the status line.
                self.assertEqual(str(page.count.pack_info()['in']),str(page.feedback))
                self.assertAlmostEqual(page.count.winfo_rooty()+page.count.winfo_height()/2,page.feedback.label.winfo_rooty()+page.feedback.label.winfo_height()/2,delta=2)
        self.assertFalse(errors)

    def test_every_records_list_says_why_it_is_empty_and_offers_the_next_step(self):
        app,root,errors=self.app();app.root.geometry('1240x850');app.request_page(6);self.settle(app);self.pump(app,.4)
        # An empty library points to where its records come from.
        expected={'best':'前往运行与 HUD','podium':'前往运行与 HUD','history':'前往运行与 HUD','official':'同步游戏成绩'}
        for kind in ('best','podium','history','official'):
            if kind!='best':app.personal_record_tabs[kind].invoke();self.settle(app);self.pump(app,.4)
            page=app.record_loaders[kind].page;table=page.table
            self.assertTrue(page.populated,kind);self.assertEqual(table.empty_button.label,expected[kind],kind)
            # A search that finds nothing offers to clear it, keeping the filters.
            page.query.set('no such record');page.search_field.flush();self.pump(app,.15)
            self.assertEqual(table.empty_button.label,'清空搜索',kind);table.empty_button.invoke();self.pump(app,.15)
            self.assertEqual(page.query.get(),'',kind);self.assertEqual(table.empty_button.label,expected[kind],kind)
            if kind=='podium':
                # A placing that hides everything offers a reset back to all placings.
                page.choose_category(1);self.pump(app,.1);self.assertEqual(table.empty_button.label,'重置筛选')
                table.empty_button.invoke();self.pump(app,.15);self.assertEqual(page.state['category'],0);self.assertEqual(table.empty_button.label,expected[kind])
        # The footer speaks for the view on screen.
        self.assertIn('官方赛事',app.status.get());self.assertFalse(errors)

    def test_each_view_fills_at_most_one_primary_action(self):
        from control_widgets import Pill
        app,root,errors=self.app(True);app.root.geometry('1240x850')
        def primaries():
            return [w.label for w in walk(app.shell.stage) if isinstance(w,Pill) and w.primary and getattr(w,'enabled',True) and w.winfo_ismapped()]
        for page in (0,1,2,3,4,5,6):
            app.request_page(page);self.settle(app);self.pump(app,.3);self.assertLessEqual(len(primaries()),1,(page,primaries()))
        for kind in ('podium','history','official'):
            app.personal_record_tabs[kind].invoke();self.settle(app);self.pump(app,.3);self.assertLessEqual(len(primaries()),1,(kind,primaries()))
        # Chosen guide cards show the selected state; the tray keeps the one primary.
        app.request_page(5);self.settle(app);g=app.guide_page
        for key in list(g.library.data['cars'])[:2]:g.select('car:'+key)
        self.pump(app,.2);self.assertEqual(primaries(),['查看对比'])
        chosen=[b for key in g.state['comparison'] for b in g.compare_buttons.get(key,[]) if b.winfo_exists()]
        self.assertTrue(chosen);self.assertTrue(all(b.selected and not b.primary for b in chosen));self.assertFalse(errors)

    def test_review_toolbar_fits_one_line_at_the_minimum_window_in_english(self):
        import i18n
        app,root,errors=self.app(True)
        try:
            app.toggle_language();self.pump(app,.3);app.request_page(1);self.settle(app);self.pump(app,.2);self.assertEqual(i18n.language,'en')
            host=app.shell.action_host;placed=[c for c in host.winfo_children() if c.winfo_manager()]
            # Compact buttons hug their labels; the menu and delete stay on the same line.
            self.assertLessEqual(host.winfo_height(),max(c.winfo_height() for c in placed)+1,[c.winfo_width() for c in placed])
            self.assertEqual(app.review_actions['delete'].cget('text'),'Delete selected');self.assertFalse(errors)
        finally:i18n.set_language('zh')

    def test_delete_key_on_the_session_list_asks_like_the_button(self):
        app,root,errors=self.app(True);app.request_page(1);self.settle(app);self.pump(app,.3)
        table=app.tree;total=len(table.get_children());table.selection_set((table.get_children()[0],));app.update_toolbar()
        # Key events reach the focused list, as when a user presses Delete there.
        app.root.lift();table.viewport.focus_force();self.pump(app,.05)
        with patch('control_danger.confirm',return_value=False) as ask:
            table.viewport.event_generate('<Delete>');self.pump(app,.1)
        self.assertEqual(ask.call_count,1);self.assertEqual(len(table.get_children()),total)
        table.selection_set(());app.update_toolbar()
        with patch('control_danger.confirm',return_value=False) as ask:
            table.viewport.event_generate('<Delete>');self.pump(app,.1)
        self.assertEqual(ask.call_count,0);self.assertFalse(errors)

    def test_empty_list_lowers_its_message_but_keeps_it_in_view(self):
        app,root,errors=self.app();app.root.geometry('1240x900');app.request_page(1);self.settle(app);self.pump(app,.3)
        table=app.tree;self.assertFalse(table.order)
        frame=table.empty_frame;room=table.viewport.winfo_height()
        self.assertGreater(room,frame.winfo_height()*3)
        # Lowered into the list, at most about three rows down, inside the visible page.
        self.assertGreater(frame.winfo_y(),round(12*table.s));self.assertLessEqual(frame.winfo_y(),round(3*table.rowheight)+1)
        self.assertLess(frame.winfo_rooty()+frame.winfo_height(),app.scroll.winfo_rooty()+app.scroll.winfo_height());self.assertFalse(errors)


if __name__=='__main__':unittest.main()
