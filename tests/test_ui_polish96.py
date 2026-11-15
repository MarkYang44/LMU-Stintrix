"""HUD controls in one place: a state-aware HUD menu, Settings as the single
editor (deep links, sampling presets, live rates, choice-dependent fields), a
visible reference lap card and the DuckDB import in the shared window style."""
import json,os,re,unittest
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests import test_ui_polish69 as helpers

ROOT=Path(__file__).resolve().parents[1]
HAN=re.compile('[\u4e00-\u9fff]')


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


def entries(menu):
    """(type, label, accelerator, sub-entries) for every entry; '---' for separators."""
    rows=[];end=menu.index('end')
    for index in range(0 if end is None else end+1):
        kind=menu.type(index)
        if kind=='separator':rows.append(('---','','',None));continue
        sub=menu.nametowidget(menu.entrycget(index,'menu')) if kind=='cascade' else None
        rows.append((kind,menu.entrycget(index,'label'),menu.entrycget(index,'accelerator'),entries(sub) if sub is not None else None))
    return rows


def find(rows,label):
    return next(row for row in rows if row[1]==label)


def invoke(menu,*path):
    """Invoke the entry at a label path, descending through cascades."""
    for label in path[:-1]:
        index=next(i for i in range(menu.index('end')+1) if menu.type(i)=='cascade' and menu.entrycget(i,'label')==label)
        menu=menu.nametowidget(menu.entrycget(index,'menu'))
    index=next(i for i in range(menu.index('end')+1) if menu.type(i)!='separator' and menu.entrycget(i,'label')==path[-1])
    menu.invoke(index)


class FakeHud:
    """What the HUD menu reads and calls, without telemetry or overlay windows."""
    def __init__(self,root,simulator='lmu',demo=True):
        from simulator_profiles import profile
        self.root=root;self.profile=profile(simulator);self.capabilities=self.profile.capabilities;self.calls=[]
        self.engine=SimpleNamespace(demo=demo)
        variable=lambda kind,value:kind(root,value=value)
        self.reference_on=variable(tk.BooleanVar,False);self.reference_auto=variable(tk.BooleanVar,True);self.reference_locked=variable(tk.BooleanVar,False)
        self.reference_kind=variable(tk.StringVar,'fastest');self.hud_mode=variable(tk.StringVar,'normal');self.input_channel=variable(tk.StringVar,'raw')
        self.window=variable(tk.StringVar,'10')
        for key in ('tyres','strategy','pit','stint','weather'):setattr(self,key+'_on',variable(tk.BooleanVar,False))
        self.evo_hud_vars={key:variable(tk.BooleanVar,True) for key in ('instruments','assists')}
        self.vehicle_panels=self.endurance_panels=SimpleNamespace(toggle=lambda kind:self.calls.append(('toggle',kind)))
    def __getattr__(self,name):
        # Every command the menu wires records its name and arguments.
        return lambda *args:self.calls.append((name,*args))


@unittest.skipUnless(os.name=='nt','Native Tk menus')
class HudMenu(unittest.TestCase):
    def root(self):
        root=tk.Tk();root.geometry('640x228+40+40');root.update();self.addCleanup(root.destroy);return root

    def test_menu_groups_entries_marks_state_and_shows_hotkeys(self):
        import hud_menu
        root=self.root();app=FakeHud(root);built=hud_menu.build(app);rows=entries(built.top)
        self.assertEqual([row[1] for row in rows if row[0]!='---'],['打开控制中心','显示参考圈差','开启鼠标穿透','显示模式','输入通道','波形窗口','附加面板','参考圈','面板尺寸与不透明度','记录与复盘','性能诊断','设置','切换到真实遥测'])
        # Hotkeys sit in the accelerator column, not inside labels.
        self.assertEqual(find(rows,'显示参考圈差')[2],'F6');self.assertEqual(find(rows,'开启鼠标穿透')[2],'F8');self.assertEqual(find(rows,'输入通道')[2],'F7')
        modes=find(rows,'显示模式')[3];self.assertEqual([row[2] for row in modes],['','F9','F11'])
        self.assertEqual(find(find(rows,'设置')[3],'采样与刷新…')[2],'F10')
        self.assertFalse([row[1] for row in rows if re.search(r'[（(]F\d',row[1])])
        # Radio marks follow the panel's real size and opacity.
        menu=built.top.nametowidget(built.top.entrycget([r[1] for r in rows].index('面板尺寸与不透明度'),'menu'))
        marks=[menu.getvar(menu.entrycget(i,'variable'))==menu.entrycget(i,'value') for i in range(menu.index('end')+1) if menu.type(i)=='radiobutton']
        self.assertEqual(marks,[False,True,False,False,False,True])
        # Preferences open their Settings section instead of a separate editor.
        for label,section in (('采样与刷新…','输入采样'),('轮胎、燃油与能量策略…','车辆策略'),('进站、Stint 与天气…','耐力与天气')):invoke(built.top,'设置',label)
        invoke(built.top,'设置','HUD 布局…')
        self.assertEqual(app.calls,[('open_settings','输入采样'),('open_settings','车辆策略'),('open_settings','耐力与天气'),('open_center_tool','layouts')])
        # One source choice replaces the two coupled reference checkboxes.
        invoke(built.top,'参考圈','固定当前参考圈')
        self.assertTrue(app.reference_locked.get());self.assertEqual(app.calls[-1],('apply_reference',))
        invoke(built.top,'参考圈','自动匹配同车同赛道')
        self.assertFalse(app.reference_locked.get());self.assertTrue(app.reference_auto.get())

    def test_menu_leaves_out_what_the_simulator_cannot_do_and_follows_the_language(self):
        import hud_menu,i18n
        root=self.root()
        for simulator in ('lmu','ac_evo'):
            app=FakeHud(root,simulator);caps=app.capabilities;built=hud_menu.build(app);rows=entries(built.top);labels=[row[1] for row in rows]
            self.assertEqual('显示参考圈差' in labels,caps.reference_laps,simulator);self.assertEqual('参考圈' in labels,caps.reference_laps,simulator)
            records=[row[1] for row in find(rows,'记录与复盘')[3]]
            self.assertEqual('导入 LMU 官方遥测…' in records,caps.native_import,simulator);self.assertEqual('打开赛事复盘…' in records,caps.full_review,simulator)
            panels=[row[1] for row in find(rows,'附加面板')[3]]
            self.assertEqual('进站计时与补给' in panels,caps.endurance,simulator);self.assertEqual('紧凑仪表条 · 挡位 / 转速' in panels,caps.driving_instruments,simulator)
            # Nothing is shown disabled: unsupported entries are simply absent.
            def states(menu):
                for i in range(0 if menu.index('end') is None else menu.index('end')+1):
                    if menu.type(i)=='separator':continue
                    yield menu.entrycget(i,'state')
                    if menu.type(i)=='cascade':yield from states(menu.nametowidget(menu.entrycget(i,'menu')))
            self.assertNotIn('disabled',list(states(built.top)),simulator)
        i18n.set_language('en');self.addCleanup(i18n.set_language,'zh')
        rows=entries(hud_menu.build(FakeHud(root)).top);panel=entries(hud_menu.panel(FakeHud(root),'pit',lambda kind:None).top)
        def labels(rows):
            for row in rows:
                yield row[1]
                if row[3]:yield from labels(row[3])
        self.assertFalse([label for label in labels(rows+panel) if HAN.search(label)])

    def test_hud_and_panel_settings_open_settings_sections(self):
        from hud import App
        import vehiclehud,endurancehud
        calls=[];fake=SimpleNamespace(open_settings=calls.append)
        App.show_sampling_settings(fake)
        vehiclehud.Panels.settings_dialog(SimpleNamespace(app=fake));endurancehud.Panels.settings_dialog(SimpleNamespace(app=fake))
        self.assertEqual(calls,['输入采样','车辆策略','耐力与天气'])
        # The duplicate editors, the positional capability map and the inline menu are gone.
        for name in ('hud.py','vehiclehud.py','endurancehud.py'):
            source=(ROOT/'src'/name).read_text(encoding='utf-8')
            self.assertNotIn('应用并保存',source,name);self.assertNotIn('tk.Menu(',source,name)
        self.assertNotIn('entryconfigure(index',(ROOT/'src/hud.py').read_text(encoding='utf-8'))
        # A side panel's menu offers its own Settings section.
        import hud_menu
        root=tk.Tk();root.withdraw();self.addCleanup(root.destroy);app=FakeHud(root)
        built=hud_menu.panel(app,'tyres',lambda kind:app.calls.append(('hide',kind)))
        invoke(built.top,'轮胎、燃油与能量策略…');invoke(built.top,'隐藏该面板')
        self.assertEqual(app.calls,[('open_settings','车辆策略'),('hide','tyres')])


@unittest.skipUnless(os.name=='nt','Native Tk')
class NativeImport(unittest.TestCase):
    def test_import_asks_in_the_shared_window_and_keeps_bad_values_in_it(self):
        import control_native_import as native
        self.assertEqual(native.overrides({'track':' Spa ','vehicle':'','track_length':'7004'}),{'track':'Spa','track_length':'7004'})
        with self.assertRaises(native.OverrideError) as caught:native.overrides({'track_length':'12'})
        self.assertEqual(caught.exception.field,'track_length')
        root=tk.Tk();root.geometry('400x300+40+40');self.addCleanup(root.destroy);owner=SimpleNamespace(root=root);runs=[]
        window=native.show(owner,'C:/logs/race.duckdb',lambda values,done:runs.append((values,done)));root.update()
        self.assertIsNotNone(window.header);controls=window.import_controls
        controls['variables']['track_length'].set('12');controls['begin']();root.update()
        self.assertEqual(runs,[]);self.assertTrue(controls['fields']['track_length'].error);self.assertTrue(window.status.get())
        controls['variables']['track_length'].set('7004');controls['variables']['track'].set('Spa');controls['begin']()
        self.assertEqual(runs[0][0],{'track':'Spa','track_length':'7004'})
        # A failed import keeps the window and its values; success closes it.
        runs[0][1]('缺少 TrackName / CarName');root.update();self.assertTrue(window.winfo_exists());self.assertIn('TrackName',window.status.get())
        controls['begin']();runs[1][1](None);root.update();self.assertFalse(window.winfo_exists())
        # The HUD menu entry opens this window for the chosen file, above the HUD.
        from hud import App
        fake=SimpleNamespace(capabilities=SimpleNamespace(native_import=True),root=root,run_background=lambda work,done:None)
        with patch('hud.filedialog.askopenfilename',return_value='C:/logs/race.duckdb'),patch('control_native_import.show') as shown:App.import_native_dialog(fake)
        self.assertEqual(shown.call_args.args[1],'C:/logs/race.duckdb');self.assertTrue(shown.call_args.kwargs['topmost'])


class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def anchors(self,app):return dict(app.settings_anchors)

    def test_open_settings_lands_on_the_requested_section(self):
        app,root,errors=self.app();app.root.geometry('1240x850')
        for section in ('车辆策略','耐力与天气','输入采样'):
            app.open_settings(section);self.settle(app,lambda:app.page==2);self.pump(app,.3)
            self.assertIs(app.settings_spy.current,self.anchors(app)[section],section)
        self.assertFalse(errors)

    def test_settings_presets_live_rates_and_choice_dependent_fields(self):
        import i18n,sampling
        from control_forms import equal
        from control_widgets import Segmented
        app,root,errors=self.app();app.root.geometry('1240x850');app.request_page(2);self.settle(app);self.pump(app,.2)
        anchors=self.anchors(app);body=anchors['输入采样'];forms=app.pages.active.forms;preset=body.form_preset
        self.assertEqual(preset.get(),'custom')  # the defaults sample at a fixed rate
        control=next(w for w in walk(body) if isinstance(w,Segmented) and w.variable is preset)
        control.select(control.values.index('均衡'));self.pump(app,.1)
        for key,value in sampling.PRESETS['均衡'].items():self.assertTrue(equal(forms['sampling'][key].get(),value),key)
        # A preset is a draft like any edit: nothing is saved until Save or Ctrl+S.
        self.assertEqual(preset.get(),'均衡');self.assertGreater(body.form_changed(),0)
        self.assertEqual(sampling.load_settings(app.data_path/'settings.json')['mode'],'fixed')
        forms['sampling']['min_hz'].set('61');self.pump(app,.05);self.assertEqual(preset.get(),'custom')
        body.form_reset();self.pump(app,.05)
        # The manual race length names its unit and explains when it applies.
        vehicle=anchors['车辆策略'];captions=('手动赛程数值','手动总圈数','手动剩余分钟')
        caption=next(w for w in walk(vehicle) if getattr(w,'source_text',None) in captions)
        note=lambda:[w for w in walk(vehicle) if isinstance(w,tk.Label) and w.cget('text')=='仅按圈数或按时间时生效' and w.winfo_ismapped()]
        self.assertEqual(caption.source_text,'手动赛程数值');self.assertTrue(note())
        for mode,expected in (('laps','手动总圈数'),('time','手动剩余分钟')):
            forms['vehicle']['target_mode'].set(mode);self.pump(app,.05);self.assertEqual(caption.source_text,expected);self.assertFalse(note())
        vehicle.form_reset();self.pump(app,.05)
        # Live rates: a hint while idle; measured rates with a running HUD.
        rates=body.live_rates;self.assertEqual(rates.text(),'启动 HUD 后，这里显示实际采样与绘制频率。')
        hud=SimpleNamespace(closing=False,root=app.root,engine=SimpleNamespace(actual_rates=lambda:(120.0,60.0),target_hz=120,reason='固定'),drawing_target=lambda:120,actual_draw_rate=lambda:59.9)
        with patch.object(app,'hud',hud):
            text=rates.text();self.assertIn('固定频率',text);self.assertIn('60.0',text);self.assertIn('59.9',text)
            i18n.set_language('en')
            try:english=rates.text()
            finally:i18n.set_language('zh')
        self.assertIn('Fixed rate',english);self.assertNotIn('Pin',english)
        self.assertFalse(errors)

    def test_reference_lap_card_saves_and_follows_changes_made_by_the_hud(self):
        app,root,errors=self.app();app.root.geometry('1240x850');app.request_page(0);self.settle(app);self.pump(app,.2)
        controls=app.reference_controls;status=lambda:controls['status'].cget('text')
        self.assertIn('自动匹配同车同赛道已记录的最快完整圈',status());self.assertIn('HUD 不显示参考圈差',status())
        controls['source'].select(1);self.pump(app,.05)
        saved=json.loads((app.data_path/'reference_settings.json').read_text(encoding='utf-8'))
        self.assertTrue(saved['locked']);self.assertFalse(controls['kind'].enabled)  # the kind only picks matched laps
        # F6 or the HUD's menu write the same file; the card shows it on its next refresh.
        saved.update(enabled=True,locked=False,automatic=True,kind='stable')
        (app.data_path/'reference_settings.json').write_text(json.dumps(saved),encoding='utf-8');app.reference_refresh()
        self.assertTrue(app.reference_on.get());self.assertEqual(app.reference_kind.get(),'stable');self.assertTrue(controls['kind'].enabled)
        self.assertIn('典型稳定圈',status());self.assertNotIn('HUD 不显示参考圈差',status())
        self.assertFalse(errors)
