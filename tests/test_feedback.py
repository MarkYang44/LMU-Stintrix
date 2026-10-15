"""Local feedback correctness, plot integrity, and lifecycle cancellation."""
import sys,time,unittest,os
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from control_feedback import record_improvements

class FeedbackTests(unittest.TestCase):
    def test_pb_never_celebrates_historical_records_or_equal_times(self):
        first=[dict(identity=('track','GP',5000,'GT3'),time_s=90)]
        baseline,changes=record_improvements(first,None);self.assertEqual(changes,[])
        self.assertEqual(record_improvements(first,baseline)[1],[])
        better=[dict(first[0],time_s=89.9)];self.assertEqual(record_improvements(better,baseline)[1],better)
        other=[dict(first[0],identity=('track','Short',2000,'GT3'),time_s=40)];self.assertEqual(record_improvements(other,baseline)[1],[])

    def test_spinner_stops_when_hidden_complete_or_destroyed_and_reduced_motion(self):
        import tkinter as tk
        from control_feedback import StatusFeedback
        root=tk.Tk();status=tk.StringVar(root,value='正在处理…');feedback=StatusFeedback(root,status);feedback.pack();root.update()
        try:
            with patch('control_motion.system_motion',return_value=True):
                feedback.busy('one');feedback.busy('two');self.assertTrue(feedback.icon.job)
                feedback.busy('one',False);self.assertTrue(feedback.icon.active)
                feedback.pack_forget();root.update();self.assertIsNone(feedback.icon.job)
                feedback.pack();root.update();self.assertTrue(feedback.icon.job)
                status.set('已完成');feedback.busy('two',False);self.assertIsNone(feedback.icon.job);self.assertEqual(feedback.icon.itemcget(feedback.icon.mark,'text'),'✓')
                feedback.destroy();self.assertFalse(feedback.icon.motion.jobs)
            other=StatusFeedback(root,status);other.pack();root.update()
            with patch('control_motion.system_motion',return_value=False):
                other.busy('job');self.assertIsNone(other.icon.job)
            other.destroy();self.assertFalse(status.trace_info())
        finally:root.destroy()

    def test_hover_keeps_plot_items_and_click_ring_does_not_change_values(self):
        import tkinter as tk
        from control_history_chart import ProgressChart
        root=tk.Tk();root.geometry('700x320');selected=[];chart=ProgressChart(root,selected.append);chart.pack(fill='both',expand=True);root.update()
        values=[dict(observed_utc=f'2026-10-0{i+1}T10:00:00+00:00',time_s=100-i) for i in range(3)];chart.set(values)
        try:
            items=chart.find_all();coords=[chart.coords(item) for item in items if item not in (chart.cursor,chart.tooltip,chart.ring)]
            for point in chart.points:chart.inspect(SimpleNamespace(x=point[0]))
            self.assertEqual(chart.find_all(),items)
            self.assertEqual([chart.coords(item) for item in items if item not in (chart.cursor,chart.tooltip,chart.ring)],coords)
            chart.select(SimpleNamespace(x=chart.points[1][0]));self.assertEqual(selected,[values[1]])
            chart.destroy();self.assertFalse(chart.motion.jobs)
        finally:root.destroy()

    def test_image_placeholder_and_arrival_reuse_one_uploaded_thumbnail(self):
        import tkinter as tk
        from PIL import Image
        from control_feedback import ImageSurface,CountBadge
        root=tk.Tk();root.geometry('400x320');surface=ImageSurface(root);surface.pack(fill='both',expand=True);badge=CountBadge(root);badge.pack();root.update()
        try:
            surface.show(Image.new('RGB',(600,400),'white'));photo=surface.photo;items=surface.find_all();deadline=time.perf_counter()+.3
            while time.perf_counter()<deadline:root.update();time.sleep(.004)
            self.assertIs(surface.photo,photo);self.assertEqual(surface.find_all(),items);self.assertFalse(surface.motion.jobs)
            surface.pending('更新中');self.assertIsNone(surface.photo);self.assertEqual(surface.itemcget(surface.bitmap,'state'),'hidden')
            badge.set(5);badge.set(3);self.assertEqual(badge.count,3)
            surface.destroy();badge.destroy();self.assertFalse(badge.motion.jobs)
        finally:root.destroy()

    def test_short_tasks_never_flash_loader_and_long_tasks_show_it(self):
        import tkinter as tk
        from control_feedback import Activity
        root=tk.Tk();icon=Activity(root);icon.pack();root.update()
        try:
            icon.set(True);self.assertEqual(icon.itemcget(icon.arc,'state'),'hidden')
            icon.set(False);deadline=time.perf_counter()+.2
            while time.perf_counter()<deadline:root.update();time.sleep(.004)
            self.assertIsNone(icon.job);self.assertEqual(icon.itemcget(icon.arc,'state'),'hidden')
            icon.set(True);deadline=time.perf_counter()+.2
            while time.perf_counter()<deadline:root.update();time.sleep(.004)
            self.assertEqual(icon.itemcget(icon.arc,'state'),'normal')
        finally:root.destroy()

    def test_forms_retain_drawing_items_during_focus_and_hover(self):
        import tkinter as tk
        from control_fields import Field,Select
        root=tk.Tk();field=Field(root);field.pack();choice=Select(root,values=('a','b'));choice.pack();root.update()
        try:
            old=(field.find_all(),choice.find_all())
            for t in (0,.3,.7,1):field.amount=t;field.paint();choice.amount=t;choice.paint()
            self.assertEqual((field.find_all(),choice.find_all()),old)
        finally:root.destroy()

    def test_theme_recolors_in_place_keeps_focus_filters_selection_and_scroll(self):
        import tkinter as tk,tempfile
        from control_center import ControlCenter
        from control_theme import T
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as folder,patch('control_center.ROOT',Path(folder)):
            center=ControlCenter()
            try:
                center.show_page(1);center.root.update();tree=center.tree;search=center.search
                center.search.set('Spa')
                def walk(w):
                    yield w
                    for child in w.winfo_children():yield from walk(child)
                field=next(w for w in walk(center.content) if isinstance(w,tk.Entry) and str(w.cget('textvariable'))==str(search));field.focus_force();center.root.update()
                before=center.root.focus_get();center.set_theme('light');center.root.update()
                self.assertIs(center.tree,tree);self.assertIs(center.search,search);self.assertEqual(search.get(),'Spa')
                self.assertEqual(center.root.cget('bg'),T.BG)
                if before:self.assertIs(center.root.focus_get(),before)
                center.set_theme('dark');center.root.update();self.assertIs(center.tree,tree)
            finally:center.close()

    def test_new_champion_requires_observed_baseline_and_confirmed_class_win(self):
        from control_feedback import new_champions
        old=[dict(folder='old',place=1),dict(folder='second',place=2)]
        baseline,new=new_champions(old,None);self.assertFalse(new)
        self.assertFalse(new_champions(old,baseline)[1])
        win=dict(folder='fresh',place=1);self.assertEqual(new_champions(old+[win],baseline)[1],[win])

    def test_detail_motion_uses_fixed_header_viewport_and_cancels_on_destroy(self):
        import tkinter as tk
        from control_record_art import RecordHeader
        root=tk.Tk();root.geometry('800x400');header=RecordHeader(root,None);header.pack(fill='x');label=tk.Label(header.text,text='Track / 1:23.456');label.pack();root.update()
        try:
            height=header.winfo_height();header.arrive();deadline=time.perf_counter()+.25
            while time.perf_counter()<deadline:root.update();time.sleep(.004)
            self.assertEqual(header.winfo_height(),height);self.assertEqual(header.surface.coords(header.text_item),[0.,0.]);header.destroy();self.assertFalse(header.motion.jobs)
        finally:root.destroy()

    def test_tab_interruption_and_victory_have_no_idle_or_destroy_callbacks(self):
        import tkinter as tk
        from control_feedback import TabIndicator,VictoryBadge
        root=tk.Tk();row=tk.Frame(root);row.pack();a=tk.Button(row,text='A');a.pack(side='left');b=tk.Button(row,text='B');b.pack(side='left');line=TabIndicator(root);line.pack(fill='x');win=VictoryBadge(root);win.pack(fill='x');root.update()
        try:
            line.select(a);line.select(b);win.celebrate();deadline=time.perf_counter()+.45
            while time.perf_counter()<deadline:root.update();time.sleep(.004)
            self.assertEqual(line.bounds,(b.winfo_x(),b.winfo_x()+b.winfo_width()));self.assertFalse(line.motion.jobs);self.assertFalse(win.motion.jobs)
            line.select(a);line.destroy();win.destroy();self.assertFalse(line.motion.jobs)
        finally:root.destroy()

if __name__=='__main__':unittest.main()
