"""Human-readable interface diagnostics and a private JSON evidence export."""
import tkinter as tk,os,json
from pathlib import Path
from datetime import datetime,timezone
from i18n import tr
from control_theme import T
from control_motion import reveal_window
from control_feedback import StatusFeedback
from telemetry_contract import probe

def show(app):
    window=tk.Toplevel(app.root);window.title(tr('数据接口检查'));window.configure(bg=T.BG);window.geometry('850x640');window.minsize(650,440)
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    app.label(body,'数据接口检查',20,T.FG,True).pack(anchor='w',pady=10)
    status=tk.StringVar(window);feedback=StatusFeedback(body,status);feedback.pack(fill='x',pady=8)
    output=tk.Text(body,wrap='word',bg=T.FIELD,fg=T.FG,insertbackground=T.FG,font=(T.FONT,10),relief='flat');output.pack(fill='both',expand=True)
    state=dict(request=0,busy=False)
    def scan():
        if state['busy']:return
        state['busy']=True;status.set(tr('正在检查接口…'));feedback.busy('scan')
        def done(value,error):
            if not window.winfo_exists():return
            state['busy']=False;feedback.busy('scan',False)
            if error:status.set(error);return
            state['value']=value
            headers=value['headers'];reviewed=bool(headers) and all(h['interface_declarations'] for h in headers)
            rows=[tr('官方 SDK 头文件')+': '+tr('接口声明可用' if reviewed else '已变化或尚未发现'),tr('游戏版本标记')+': '+str(value.get('game_version',tr('未知'))),tr('玩家通道')+': '+tr('可用' if value.get('channels_available') else '等待玩家遥测'),tr('数据陈旧')+': '+tr('是' if value.get('stale') else '否' if value.get('age_s') is not None else '尚无有效帧'),tr('有效更新帧数')+': '+str(value.get('frames',0)),tr('评分车辆数')+': '+str(value.get('scoring_vehicles',0)),tr('快照被拒绝')+': '+str(value.get('rejected',0)),tr('共享内存读取方式')+': '+tr('稳定双快照（不消费事件信号）'),tr('官方协调锁')+': '+tr('已发现（未修改）' if value.get('lock_present') else '未发现'),'',tr('接口检查与实机验收不同；头文件变化时需重新核对布局并录制有效圈验证。'),tr('仅打开既有共享内存和事件；游戏数据映射始终只读。')]
            if value.get('message'):rows.append(value['message'])
            output.configure(state='normal');output.delete('1.0','end');output.insert('1.0','\n\n'.join(rows));output.configure(state='disabled');status.set(tr('已完成'))
        live=dict(getattr(app.hud.engine,'interface_status',{})) if app.active() else None
        app.run_background(lambda:probe(live=live),done)
    def export():
        if 'value' not in state:return
        from storage import atomic_json
        from uuid import uuid4
        folder=app.data_path/'Diagnostics';folder.mkdir(parents=True,exist_ok=True);path=folder/('interface-'+uuid4().hex+'.json');atomic_json(path,state['value']);app.status.set(str(path));os.startfile(str(path))
    row=app.row(body);app.button(row,'重新检查',scan,True,140);app.button(row,'导出接口诊断',export,False,160);scan();reveal_window(window)
