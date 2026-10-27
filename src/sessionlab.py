"""All eligible laps, reproducibility and genuine median-lap references."""
import bisect
import json
from json_store import load as load_json
import math
from telemetry_file import Path
import statistics
from laps import comparison_data,trajectory_data,extract_best,DATA_COLUMNS,FORMAT,write_json,safe_name

CONDITION_RULES={'fuel_l':2,'tyre_compound':0,'track_temp_c':5,'wetness':.1,'tc_level':0,'abs_level':0}
NATIVE_NAMES={'fuel_l':'Fuel Level','tyre_compound':'TyresCompound','track_temp_c':'Track Temperature',
              'wetness':'Minimum Path Wetness','tc_level':'TCLevel','abs_level':'ABSLevel'}


def condition_check(a,b):
    known=[];unknown=[];different=[]
    for key,tolerance in CONDITION_RULES.items():
        x,y=a.get(key),b.get(key)
        if not isinstance(x,(int,float)) or not isinstance(y,(int,float)) or not all(map(math.isfinite,(x,y))):unknown.append(key)
        else:
            known.append(key)
            if abs(x-y)>tolerance:different.append(key)
    return dict(allowed=not different,known=known,unknown=unknown,different=different)


def lap_conditions(rows,native=None,start=0,offset=0):
    keys=(*CONDITION_RULES,'tyre_rear_compound','tyre_front_name','tyre_rear_name','ambient_temp_c','rain','track_grip')
    from analysis_spool import project_rows
    rows=project_rows(rows,keys)
    # Scratch layouts are fixed; absent columns cannot appear in a later row.
    layout=getattr(rows,'layout',None);pending={k for k in keys if layout is None or k in layout};observed={}
    for row in rows:
        for key in tuple(pending):
            if key in row:observed[key]=row[key];pending.remove(key)
        if not pending:break
    result={key:observed[key] for key in keys if key in observed}
    if native:
        for key,name in NATIVE_NAMES.items():
            s=native.get('channels',{}).get(name)
            if s and s['data']:
                shift=offset if s['event'] else 0
                data=s['data']
                i=max(0,bisect.bisect_right(data,start+shift,key=lambda row:row[0])-1)
                if data[i][0]-shift<=start+.2:result[key]=data[i][1]
    return result


def spread(values):
    if not values:return dict(count=0,median=None,std=None,min=None,max=None)
    return dict(count=len(values),median=statistics.median(values),std=statistics.pstdev(values),min=min(values),max=max(values))


def actions(rows):
    """Time-based debounce; cannot infer grip or the cause of a correction."""
    from analysis_spool import numeric_rows
    rows=numeric_rows(rows,('session_time_s','throttle','brake','steering','filtered_throttle','filtered_brake','filtered_steering','abs_active','tc_active'))
    states=[dict(prefix=prefix,names=names,slopes=[],corrections=0,last_sign=0,last_change=-100,extreme=0,armed=False,since=None,lift=0)
            for prefix,names in [('raw',('throttle','brake','steering')),('filtered',('filtered_throttle','filtered_brake','filtered_steering'))]]
    dt_sum=0;differences=[0,0,0];abs_time=tc_time=0;abs_known=tc_known=False
    previous=None
    for row in rows:
        t=row['session_time_s'];dt=t-previous['session_time_s'] if previous is not None else 0
        for state in states:
            throttle,brake,steering=state['names']
            if previous is None:state['extreme']=row.get(steering,0)
            elif 0<dt<=.2:
                change=(row[brake]-previous[brake])/dt
                if previous[brake]>.05 and change<-.02:state['slopes'].append(-change*100)
                value=row.get(steering,0);ds=value-state['extreme'];sign=1 if ds>.025 else -1 if ds<-.025 else 0
                if sign and sign!=state['last_sign']:
                    if state['last_sign'] and t-state['last_change']>.08:state['corrections']+=1
                    state.update(last_change=t,last_sign=sign,extreme=value)
                elif state['last_sign']==1:state['extreme']=max(state['extreme'],value)
                elif state['last_sign']==-1:state['extreme']=min(state['extreme'],value)
            if row[throttle]>.8:state['armed']=True;state['since']=None
            elif state['armed'] and row[throttle]<.6:
                if state['since'] is None:state['since']=t
                if t-state['since']>=.06:state['lift']+=1;state['armed']=False
        if 0<dt<=.2:
            dt_sum+=dt
            for i,(raw,filtered) in enumerate(zip(('throttle','brake','steering'),('filtered_throttle','filtered_brake','filtered_steering'))):
                if raw in previous and filtered in previous:differences[i]+=abs(previous[raw]-previous[filtered])*dt
            if 'abs_active' in previous:abs_known=True;abs_time+=bool(previous['abs_active'])*dt
            if 'tc_active' in previous:tc_known=True;tc_time+=bool(previous['tc_active'])*dt
        previous=row
    results={s['prefix']:dict(brake_release_pct_s=statistics.median(s['slopes']) if s['slopes'] else None,
        steering_corrections=s['corrections'],throttle_lifts=s['lift']) for s in states}
    results.update(input_difference_pct=[v/max(1e-9,dt_sum)*100 for v in differences],
        abs_active_s=abs_time if abs_known else None,tc_active_s=tc_time if tc_known else None)
    return results


def analyze_session(folder):
    folder=Path(folder);meta=json.loads((folder/'session.json').read_text(encoding='utf-8'))
    if meta.get('status')=='recording':raise ValueError('请等本场记录结束后再分析')
    if meta.get('status')=='write_error':raise ValueError('该记录存在写盘错误，保留原 CSV 供检查，不生成可信参考')
    native=load_json(folder/'native_channels.json') if (folder/'native_channels.json').exists() else None
    from vehiclelab import load_recording,lap_telemetry
    vehicle_bundle=load_recording(folder)
    from processing_context import current
    shared=current(folder);summaries=[];recent=[];recent_rows=[]
    from training_cache import warming
    warmer=warming(folder)
    if shared is not None:
        for name in ('best','best_curve','best_conditions','best_actions','candidates','error','analysed'):shared.values.pop(name,None)
        shared.values.update(native=native,vehicle=vehicle_bundle)
    clock_origin=None
    def collect(best):
        nonlocal clock_origin
        if clock_origin is None:clock_origin=best['rows'][0]['session_time_s']-best['rows'][0].get('time_s',best['rows'][0]['session_time_s'])
        condition=lap_conditions(best['rows'],native,best['start_s'],native.get('event_offset_s',0) if native else 0)
        action=actions(best['rows']);data=comparison_data(best)
        if warmer is not None:warmer.feed(best,data,condition if native is None else None)
        brake=next((r[0] for r in data if r[3]>=.05),None)
        full=next((r[0] for r in data if r[2]>=.9),None)
        info=dict(number=best['number'],time_s=best['time_s'],validity=best['validity'],conditions=condition,
            action=action,minimum_speed=min(r[6] for r in data),first_brake_m=brake,first_full_m=full,
            start_time_s=best['start_s']-clock_origin,end_time_s=best['end_s']-clock_origin,
            profile=[data[round(i*(len(data)-1)/max(1,min(1001,len(data))-1))] for i in range(min(1001,len(data)))])
        vehicle=lap_telemetry(best,vehicle_bundle)
        if vehicle:info['vehicle_summary']=vehicle['summary']
        summaries.append(info)
        if shared is not None and ('best' not in shared.values or best['end_s']-best['start_s']<shared.values['best']['time_s']):
            shared.values.update(best=best,best_curve=data,best_conditions=condition,best_actions=action)
        # Keep at most five actual candidates; representative is an observed lap.
        recent.append(info);del recent[:-5]
        recent_rows.append(best);del recent_rows[:-5]
    from lap_scan_index import builder,save
    from laps import _lap_inventory
    scan_index=builder(folder)
    _,candidates,error=extract_best(folder/'inputs.csv',collect,retain_best=False,_index=scan_index)
    save(folder,_lap_inventory(scan_index['candidates'],error),scan_index)
    if shared is not None:shared.check();shared.values.update(candidates=candidates,error=error,analysed=True)
    latest=recent[-1]['conditions'] if recent else {}
    training=[i for i in recent if condition_check(i['conditions'],latest)['allowed']]
    times=[i['time_s'] for i in training];stats=spread(times);reference=None
    if len(training)>=3:
        info=min(training,key=lambda i:abs(i['time_s']-stats['median']))
        if sum(candidate['number']==info['number'] for candidate in candidates)>1:
            # Retain historical epoch selection for ambiguous repeated numbers.
            selected=[]
            def select(best):
                if best['number']==info['number'] and abs(best['start_s']-clock_origin-info['start_time_s'])<1e-6:selected.append(best)
            extract_best(folder/'inputs.csv',select,retain_best=False);best=selected[0]
        else:best=next(best for best in recent_rows if best['number']==info['number'] and abs(best['start_s']-clock_origin-info['start_time_s'])<1e-6)
        refinfo={k:best[k] for k in ('number','time_s','validity','timing_source','distance_source','cadence_s')}
        refinfo.update(track_length_m=best['length_m'],sample_count=len(best['rows']),start_session_time_s=best['start_s'],end_session_time_s=best['end_s'])
        data=comparison_data(best)
        reference=dict(format=FORMAT,version=1,id=folder.name+':stable:'+str(info['number']),session={k:meta.get(k,'') for k in ('track','vehicle','driver','started_utc','source')},
            lap=refinfo,data_columns=DATA_COLUMNS,data=data,conditions=info['conditions'],reference_kind='stable',
            stability=stats,actions=info['action'],trajectory=trajectory_data(best,data))
        reference['vehicle_telemetry']=lap_telemetry(best,vehicle_bundle)
        if reference['trajectory'] and meta.get('position_source'):reference['trajectory']['source']=meta['position_source']
        name=f"Stable_Lap_{info['number']}_{safe_name(meta['vehicle'])}_{safe_name(meta['track'])}.lap.json"
        write_json(folder/name,reference)
    else:name=None
    detail=dict(version=1,laps=summaries,candidates=candidates,error=error,recent_stability=stats,
        stable_reference_file=name,conditions_unknown=condition_check(latest,latest)['unknown'],
        metrics={k:spread([i[k] for i in training if i[k] is not None]) for k in ('minimum_speed','first_brake_m','first_full_m')},
        note='最近最多五个完整圈；明确条件不同的圈排除。稳定参考为实测中位附近的一圈；不足三圈不生成。交通需人工标记。动作计数是阈值统计，不自动认定驾驶错误。')
    write_json(folder/'session_analysis.json',detail)
    from analysis_headers import save as save_headers
    save_headers(folder,detail)
    if warmer is not None:warmer.finish(candidates,error)
    return detail
