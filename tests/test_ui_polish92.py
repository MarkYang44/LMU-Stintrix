"""Deep windows share one anatomy: heading, content, and a footer that never clips its actions."""
import os,time,unittest
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from tests import test_ui_polish69 as helpers

ROOT=Path(__file__).resolve().parents[1]


def wait(root,condition,seconds=3):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


def walk(widget):
    yield widget
    for child in widget.winfo_children():yield from walk(child)


def inside(test,widget,window):
    test.assertGreaterEqual(widget.winfo_rootx(),window.winfo_rootx());test.assertGreaterEqual(widget.winfo_rooty(),window.winfo_rooty())
    test.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),window.winfo_rootx()+window.winfo_width())
    test.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),window.winfo_rooty()+window.winfo_height())


class Source(unittest.TestCase):
    def test_control_modules_use_platform_font_tokens(self):
        from control_theme import T
        self.assertEqual((T.MONO,T.LATIN),('Menlo','Helvetica Neue') if os.sys.platform=='darwin' else ('Consolas','Segoe UI'))
        for path in (ROOT/'src').glob('control_*.py'):
            if path.name=='control_theme.py':continue
            text=path.read_text(encoding='utf-8')
            self.assertNotIn("'Consolas'",text,path.name);self.assertNotIn("'Segoe UI'",text,path.name)
        self.assertNotIn('tk.Button(',(ROOT/'src/management.py').read_text(encoding='utf-8'))


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump

    def test_footer_keeps_primary_first_and_wraps_actions_inside_a_narrow_window(self):
        from control_window import window as sheet,fit,MAC
        app,root,errors=self.app();w=sheet(app.root,'窄窗口','一句说明')
        for index in range(5):w.add_action(f'第 {index} 个较长的操作',lambda:None,index==0,110)
        w.status.set('一段较长的状态说明，用来确认状态会移到操作上方的独立一行。'*2)
        fit(w,380);self.pump(app,.4)
        self.assertTrue(w.footer.stacked)
        for button in w.footer.buttons:inside(self,button,w)
        first=w.footer.buttons[0];row=[b for b in w.footer.buttons if b.winfo_rooty()==first.winfo_rooty()]
        edge=max if MAC else min
        self.assertEqual(first.winfo_rootx(),edge(b.winfo_rootx() for b in row))
        w.destroy();self.assertFalse(errors)

    def test_fitted_height_counts_wrapped_paragraphs(self):
        from control_window import window as sheet,fit,note
        app,root,errors=self.app();w=sheet(app.root,'换行','很长的一句用途说明，'*8)
        paragraph=note(w.body,'第二段较长的说明文字，'*14,10);paragraph.pack(fill='x')
        w.add_action('应用',lambda:None,True);w.add_action('取消',w.destroy)
        fit(w,420);self.pump(app,.5)
        for button in w.footer.buttons:inside(self,button,w)
        self.assertLessEqual(paragraph.winfo_rooty()+paragraph.winfo_height(),w.footer.winfo_rooty()+1)
        w.destroy();self.assertFalse(errors)

    def test_empty_select_reads_as_a_prompt(self):
        from control_fields import Select
        from control_theme import T
        app,root,errors=self.app();value=tk.StringVar(app.root)
        box=Select(app.root,textvariable=value,values=['Monza'],placeholder='选择赛事');box.place(x=0,y=0,width=300);self.pump(app,.1)
        self.assertEqual(box.itemcget(box.caption,'text'),'选择赛事');self.assertEqual(box.itemcget(box.caption,'fill'),T.MUTED)
        value.set('Monza');self.pump(app,.05)
        self.assertEqual(box.itemcget(box.caption,'text'),'Monza');self.assertEqual(box.itemcget(box.caption,'fill'),T.FG)
        box.destroy();self.assertFalse(errors)

    def test_draft_question_shows_its_message_marks_discard_and_defaults_to_keep_editing(self):
        from control_confirm import draft_choice
        from control_danger import Danger
        app,root,errors=self.app();seen={}
        def inspect():
            w=app.root._stintrix_confirm;buttons=w.confirm_buttons
            message=[c for c in walk(w) if isinstance(c,tk.Label) and '未保存' in str(c.cget('text'))]
            seen.update(message=bool(message) and message[0].winfo_ismapped(),danger=isinstance(buttons['discard'],Danger),
                focus=w.focus_lastfor() is buttons['cancel'],order=list(buttons))
            for button in buttons.values():inside(self,button,w)
            if message:self.assertLessEqual(message[0].winfo_rooty()+message[0].winfo_height(),w.footer.winfo_rooty()+1)
            buttons['cancel'].invoke()
        app.root.after(500,inspect)
        self.assertEqual(draft_choice(app.root,closing=True),'cancel')
        self.assertEqual(seen,dict(message=True,danger=True,focus=True,order=['save','keep','discard','cancel']));self.assertFalse(errors)

    def test_notice_replaces_native_error_boxes(self):
        from control_confirm import notice
        app,root,errors=self.app();seen={}
        def answer():
            w=app.root._stintrix_confirm;seen['buttons']=list(w.confirm_buttons);seen['title']=w.title();w.confirm_buttons['cancel'].invoke()
        app.root.after(400,answer)
        with patch('tkinter.messagebox.showerror') as native:notice(app.root,'设置未保存','数值无效')
        native.assert_not_called();self.assertEqual(seen,dict(buttons=['cancel'],title='设置未保存'));self.assertFalse(errors)

    def test_interface_check_lists_facts_and_keeps_its_actions_visible(self):
        from control_interface import show
        app,root,errors=self.app()
        value=dict(headers=[dict(interface_declarations=True)],game_version='1.2',channels_available=True,stale=False,age_s=.1,frames=10,scoring_vehicles=20,rejected=0,lock_present=False,message='Waiting for LMU shared memory')
        with patch('control_interface.probe',return_value=value):
            w=show(app);facts=w.interface_facts.values
            self.assertTrue(wait(app.root,lambda:facts['sdk'].cget('text')=='接口声明可用'))
        self.pump(app,.3)
        self.assertEqual(facts['frames'].cget('text'),'10');self.assertEqual(facts['version'].cget('text'),'1.2')
        self.assertTrue(any(isinstance(c,tk.Label) and str(c.cget('text')).startswith('正在等待 LMU 共享内存') for c in walk(w)))
        for button in w.footer.buttons:self.assertTrue(button.winfo_ismapped());inside(self,button,w)
        self.assertIs(show(app),w);w.destroy();self.assertFalse(errors)

    def test_diagnostics_show_rates_and_latency_without_native_buttons(self):
        from management import show_diagnostics
        app,root,errors=self.app();timing=lambda a,b,c:dict(p50_ms=a,p95_ms=b,p99_ms=c)
        snapshot=dict(read=timing(None,None,None),draw=timing(1.,2.,3.),interval=timing(16.,17.,18.),latency=timing(5.,6.,7.),stutters=2)
        engine=NS(actual_rates=lambda:(119.8,119.8),diagnostics=NS(snapshot=lambda:dict(snapshot)),recorder=NS(batch=None),target_hz=120,missed_cycles=0,
            reference_state=dict(mode='关闭',confidence=0,conditions=dict(unknown=['fuel_l'])))
        hud=NS(root=app.root,engine=engine,actual_draw_rate=lambda:57.3,drawing_target=lambda:120,render_clock=NS(missed_cycles=3),closing=False)
        w=show_diagnostics(hud,root);self.pump(app,.6)
        texts=[str(c.cget('text')) for c in walk(w) if isinstance(c,tk.Label)]
        self.assertIn('119.8 Hz',texts);self.assertIn('57.3 Hz',texts);self.assertIn('3.000',texts);self.assertIn('燃油',texts)
        self.assertFalse([c for c in walk(w) if isinstance(c,tk.Button)])
        w.footer.buttons[0].invoke();self.assertTrue((Path(root)/'Diagnostics'/'latest.json').is_file());self.assertIn('诊断已导出',w.status.get())
        self.assertTrue(w.footer.buttons[1].enabled);w.destroy();self.assertFalse(errors)

    def test_same_session_laps_extract_from_their_own_row(self):
        from management import show_lap_selection
        app,root,errors=self.app();folder=Path(root)/'Logs'/'2026-11-01_12-00-00_Race_Monza';folder.mkdir(parents=True)
        laps=dict(laps=[dict(number=1,time_s=147.9,validity='verified'),dict(number=2,time_s=147.3,validity='verified')],candidates=[1,2,3],error='')
        with patch('management.finished_metadata',return_value=dict(track='Monza',vehicle='Car')),patch('management.complete_laps',return_value=laps):
            w=show_lap_selection(app,root,folder);controls=w.lap_controls
            self.assertTrue(wait(app.root,lambda:controls['buttons']['compare'].enabled))
        self.assertFalse([c for c in walk(w) if isinstance(c,tk.Button)])
        self.assertIn('Car',w.header.subtitle.cget('text'))
        with patch('management.export_selected_laps',return_value=dict(folder=str(folder),comparison=None)) as export:
            controls['buttons']['B'].invoke();self.assertTrue(wait(app.root,lambda:export.called))
        self.assertEqual(export.call_args.args[1],[2]);self.pump(app,.2);self.assertTrue(controls['buttons']['folder'].enabled)
        w.destroy();self.assertFalse(errors)

    def test_worklist_refresh_sits_with_search_and_actions_in_the_footer(self):
        from control_report_tasks import show
        app,root,errors=self.app();w=show(app);self.pump(app,.4);view=w.worklist
        self.assertIs(view.buttons['refresh'].master,view.tools)
        for key,button in view.buttons.items():
            if key!='refresh':self.assertIs(button.master,w.footer.actions);inside(self,button,w)
        self.assertEqual(view.search.placeholder,'输入关键词筛选列表');w.destroy();self.assertFalse(errors)

    def test_goal_editor_sizes_to_content(self):
        from control_evo_goal import show
        app,root,errors=self.app();w=show(app,app.root,'2:05.300',lambda value:None);self.pump(app,.4)
        for button in w.footer.buttons:inside(self,button,w)
        inside(self,w.goal_controls['field'],w);w.destroy();self.assertFalse(errors)


if __name__=='__main__':unittest.main()
