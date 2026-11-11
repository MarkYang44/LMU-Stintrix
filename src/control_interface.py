"""Human-readable interface diagnostics and a private JSON evidence export."""
from platform_runtime import open_path
from i18n import tr
from control_theme import T
from telemetry_contract import probe

# The reader's OSError text, said in the interface's own words.
MESSAGES={'Waiting for LMU shared memory':'正在等待 LMU 共享内存（游戏未运行或尚未进入赛道）'}
ROWS=[('sdk','官方 SDK 头文件'),('version','游戏版本标记'),('channels','玩家通道'),('stale','数据陈旧'),('frames','有效更新帧数'),
    ('vehicles','评分车辆数'),('rejected','快照被拒绝'),('mode','共享内存读取方式'),('lock','官方协调锁')]


def show(app):
    from control_window import window as sheet,fit,grow,Facts,card,note
    from control_widgets import px
    old=getattr(app,'interface_window',None)
    if old is not None and old.winfo_exists():old.deiconify();old.lift();return old
    window=sheet(app.root,'数据接口检查','核对 LMU 共享内存接口是否可读。只打开既有映射，不修改游戏数据。',feedback=True,transient=False);app.interface_window=window
    status=window.status;feedback=window.footer.feedback
    outer,inner=card(window.body,16);outer.pack(fill='x')
    facts=Facts(inner,ROWS);facts.pack(fill='x');window.interface_facts=facts
    message=note(window.body,'',9,T.ACCENT)
    notes=note(window.body,'接口检查与实机验收不同；头文件变化时需重新核对布局并录制有效圈验证。')
    notes.pack(fill='x',pady=(px(window,12),0))
    note(window.body,'仅打开既有共享内存和事件；游戏数据映射始终只读。').pack(fill='x')
    state=dict(request=0,busy=False)
    def scan():
        if state['busy']:return
        state['busy']=True;status.set(tr('正在检查接口…'));feedback.busy('scan');rescan.configure(state='disabled')
        def done(value,error):
            if not window.winfo_exists():return
            state['busy']=False;feedback.busy('scan',False);rescan.configure(state='normal')
            if error:status.set(error);return
            state['value']=value;export_button.configure(state='normal')
            headers=value['headers'];reviewed=bool(headers) and all(h['interface_declarations'] for h in headers)
            facts.set('sdk','接口声明可用' if reviewed else '已变化或尚未发现','good' if reviewed else 'warn')
            version=value.get('game_version')
            facts.set('version',str(version) if version is not None else '未知',None if version is not None else 'muted',translate=version is None)
            facts.set('channels','可用' if value.get('channels_available') else '等待玩家遥测','good' if value.get('channels_available') else 'muted')
            stale=value.get('stale');known=value.get('age_s') is not None
            facts.set('stale','是' if stale else '否' if known else '尚无有效帧','bad' if stale else 'good' if known else 'muted')
            for key,name in (('frames','frames'),('vehicles','scoring_vehicles'),('rejected','rejected')):facts.set(key,str(value.get(name,0)),translate=False)
            facts.set('mode','稳定双快照（不消费事件信号）')
            facts.set('lock','已发现（未修改）' if value.get('lock_present') else '未发现')
            text=value.get('message') or ''
            message.configure(text=MESSAGES.get(text,text))
            if text:message.pack(fill='x',pady=(px(window,10),0),before=notes)
            else:message.pack_forget()
            status.set(tr('已完成'));grow(window)
        live=dict(getattr(app.hud.engine,'interface_status',{})) if app.active() else None
        app.run_background(lambda:probe(live=live),done)
    def export():
        if 'value' not in state:return
        from storage import atomic_json
        from uuid import uuid4
        folder=app.data_path/'Diagnostics';folder.mkdir(parents=True,exist_ok=True);path=folder/('interface-'+uuid4().hex+'.json');atomic_json(path,state['value'])
        app.status.set(str(path));status.set(tr('诊断已导出：')+str(path));open_path(str(path))
    rescan=window.add_action('重新检查',scan,True,120)
    export_button=window.add_action('导出接口诊断',export,False,140);export_button.configure(state='disabled')
    window.add_action('关闭',window.destroy,False,90)
    scan();fit(window,640);return window
