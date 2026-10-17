"""Read-only multi-lap practice priorities using one observed reference lap."""
import bisect,json,math,statistics
from pathlib import Path
from laps import extract_best,comparison_data,write_json
from lap_identity import text,same_layout,vehicle_class
from sessionlab import lap_conditions,condition_check
from i18n import tr
from training_cache import serialized


def interpolate(rows,d):
    i=bisect.bisect_left(rows,d,key=lambda row:row[0])
    if not i:return list(rows[0])
    if i>=len(rows):return list(rows[-1])
    a,b=rows[i-1],rows[i];f=(d-a[0])/max(1e-9,b[0]-a[0])
    return [x+(y-x)*f for x,y in zip(a,b)]


def cache_path(root,folder):
    from training_cache import path
    return path(root,folder)


@serialized
def profiles(root,folder):
    path=cache_path(root,folder)
    if path.is_file():
        from training_cache import read
        return read(path)
    found=[];path.parent.mkdir(parents=True,exist_ok=True)
    def collect(best):
        if best['validity']!='verified':return
        data=comparison_data(best)
        # Fixed distance samples keep memory bounded per lap; no fake curve.
        sample=[interpolate(data,best['length_m']*i/600) for i in range(601)]
        from training_zones import features
        extras=features(best['rows'],best['start_s'],best['end_s'],best['length_m'])
        lap=dict(features=extras,number=best['number'],time_s=best['time_s'],length_m=best['length_m'],conditions=lap_conditions(best['rows']),data=sample)
        filename='lap-'+str(len(found))+'.json';write_json(path.parent/filename,lap)
        found.append({k:v for k,v in lap.items() if k not in ('data','features')}|dict(file=filename))
    _,candidates,error=extract_best(folder/'inputs.csv',collect,retain_best=False)
    counts={}
    for candidate in candidates:counts[candidate.get('number')]=counts.get(candidate.get('number'),0)+1
    found=[lap for lap in found if counts[lap['number']]==1]
    value=dict(laps=found,excluded=len(candidates)-len(found),error=error)
    path.parent.mkdir(parents=True,exist_ok=True);write_json(path,value)
    write_json(path.with_name('index.json'),dict(laps=[{k:v for k,v in l.items() if k not in ('data','features')} for l in found],excluded=value['excluded'],error=value['error']))
    from training_cache import read
    result=read(path)
    from cache_budget import enforce
    enforce(root,keep=[path.parent]);return result


@serialized
def profile_index(root,folder):
    path=cache_path(root,folder).with_name('index.json')
    if not path.is_file():
        value=profiles(root,folder)
        if not path.is_file():
            laps=value['laps'];headers=laps.headers if hasattr(laps,'headers') else laps
            write_json(path,dict(laps=[{k:v for k,v in l.items() if k not in ('data','features')} for l in headers],excluded=value['excluded'],error=value['error']))
    return json.loads(path.read_text(encoding='utf-8'))

def selected_profiles(root,folder,numbers):
    laps=profiles(root,folder)['laps']
    return laps.selected(numbers) if hasattr(laps,'selected') else (lap for lap in laps if lap['number'] in numbers)


def conditions(a,b):
    check=condition_check(a,b)
    for key,tolerance in (('tyre_rear_compound',0),('ambient_temp_c',5),('rain',.05),('track_grip',0)):
        x,y=a.get(key),b.get(key)
        if isinstance(x,(int,float)) and isinstance(y,(int,float)) and all(map(math.isfinite,(x,y))):
            if abs(x-y)>tolerance:check['different'].append(key)
        else:check['unknown'].append(key)
    for key in ('tyre_front_name','tyre_rear_name'):
        if a.get(key) and b.get(key):
            if text(a[key])!=text(b[key]):check['different'].append(key)
        else:check['unknown'].append(key)
    check['allowed']=not check['different'];return check


def zones(reference):
    rows=reference['data'];length=reference['length_m'];apexes=[];active=[]
    for row in rows:
        if row[3]>=.05:active.append(row)
        elif active:
            if active[-1][0]-active[0][0]>=10:apexes.append(min(active,key=lambda r:r[6])[0])
            active=[]
    if active and active[-1][0]-active[0][0]>=10:apexes.append(min(active,key=lambda r:r[6])[0])
    merged=[]
    for apex in apexes:
        if not merged or apex-merged[-1]>=80:merged.append(apex)
    if not merged:
        return [dict(name='区间 '+str(i+1),start=i*length/8,end=(i+1)*length/8,apex=(i+.5)*length/8,source='equal_distance') for i in range(8)]
    boundaries=[0,*[(a+b)/2 for a,b in zip(merged,merged[1:])],length]
    return [dict(name='制动区 '+str(i+1),start=boundaries[i],end=boundaries[i+1],apex=a,source='reference_braking') for i,a in enumerate(merged)]


def measure(lap,zone):
    rows=lap['data'];a,b=zone['start'],zone['end']
    part=[interpolate(rows,a),*[r for r in rows if a<r[0]<b],interpolate(rows,b)]
    brake=next((r[0] for r in part if r[0]<=zone['apex'] and r[3]>=.05),None)
    after=[r for r in part if r[0]>=zone['apex']]
    full=None
    for i,row in enumerate(after):
        tail=[r for r in after[i:] if r[0]<=row[0]+12]
        if row[2]>=.9 and after[-1][0]>=row[0]+12 and all(r[2]>=.9 for r in tail):full=row[0];break
    from training_zones import feature_time
    coast=feature_time(lap,zone,'coast')
    if coast is None and not lap.get('features'):coast=sum(y[1]-x[1] for x,y in zip(part,part[1:]) if x[2]<.03 and x[3]<.03)
    return dict(time_s=part[-1][1]-part[0][1],brake_m=brake,minimum_kmh=min(r[6] for r in part),full_m=full,coast_s=coast,abs_s=feature_time(lap,zone,'abs'),tc_s=feature_time(lap,zone,'tc'))


def aggregate(laps,reference,definitions=None):
    sections=definitions if definitions is not None else zones(reference);targets=[measure(reference,z) for z in sections];buckets=[[] for _ in sections]
    # Retain only a handful of measurements per section, never all lap curves.
    for lap in laps:
        if lap is reference:continue
        for zone,bucket in zip(sections,buckets):bucket.append(measure(lap,zone))
    result=[]
    for zone,target,values in zip(sections,targets,buckets):
        losses=[v['time_s']-target['time_s'] for v in values]
        if not losses:continue
        median=statistics.median(losses);spread=statistics.pstdev(losses)
        differences={}
        for key in ('brake_m','minimum_kmh','full_m','coast_s','abs_s','tc_s'):
            valid=[v[key]-target[key] for v in values if v[key] is not None and target[key] is not None]
            differences[key]=statistics.median(valid) if valid else None
        result.append(dict(zone,target=target,count=len(losses),median_loss_s=median,mean_loss_s=statistics.mean(losses),std_s=spread,
            slower_fraction=sum(v>.02 for v in losses)/len(losses),score=max(0,median)+.25*spread,differences=differences))
    return sorted(result,key=lambda v:v['score'],reverse=True)


def report(root,entry,policy=None):
    from condition_match import settings,match
    from analysis_scope import check as scope_check
    from race_mode import overlay,annotate
    policy=settings(policy);modes=overlay(root)
    root=Path(root).resolve();anchor=dict(session=entry['session'],lap=entry['lap']);accepted=[];excluded=0;different=0;unknown=set();errors=[];seen={};conflicts=set()
    from session_groups import superseded
    hidden=superseded(root)
    for category in ('Logs','ImportedLogs','RecoveredLogs'):
        for metadata in (root/category).glob('*/session.json'):
            try:
                folder=metadata.parent.resolve()
                if not folder.is_relative_to(root) or folder in hidden:continue
                meta=annotate(json.loads(metadata.read_text(encoding='utf-8')),folder,modes)
                scope=scope_check(entry,meta,policy)
                if not scope['allowed']:continue
                if meta.get('status') in ('recording','write_error') or meta.get('demo') or text(meta.get('source'))=='synthetic demo':continue
                if text(meta.get('driver'))!=text(entry['session'].get('driver')):continue
                if text(meta.get('vehicle'))!=text(entry['session'].get('vehicle')) or text(meta.get('track'))!=text(entry['track']) or vehicle_class(meta)!=entry['vehicle_class']:continue
                la,lb=text(meta.get('track_layout')),text(entry['layout'])
                # Unknown layouts cannot be treated as a known named layout.
                if la!=lb:continue
                value=profile_index(root,folder);excluded+=value['excluded']
                for lap in value['laps']:
                    candidate=dict(session=meta,lap=dict(track_length_m=lap['length_m']))
                    if not same_layout(anchor,candidate):continue
                    check=match(entry.get('conditions',{}),lap['conditions'],policy)
                    if not check['allowed']:different+=1;continue
                    identity=(meta.get('started_utc') or str(folder),text(meta.get('driver')),text(meta.get('vehicle')),scope['mode'],scope['phase'],lap['number'])
                    signature=(lap['time_s'],lap['length_m'],json.dumps(lap['conditions'],sort_keys=True))
                    if identity in seen:
                        if seen[identity]!=signature:conflicts.add(identity)
                        continue
                    seen[identity]=signature;unknown.update(check['unknown']);unknown.update(scope['unknown']);
                    if scope['mixed']:unknown.add('跨类别探索')
                    accepted.append(dict({k:v for k,v in lap.items() if k!='data'},folder=str(folder),session=meta,sample_identity=identity))
            except (OSError,ValueError,TypeError,KeyError) as error:errors.append(metadata.parent.name+': '+str(error))
    accepted=[lap for lap in accepted if lap['sample_identity'] not in conflicts];excluded+=len(conflicts)
    if len(accepted)<4:raise ValueError(tr('至少需要 4 个相同布局、同车型、条件接近的有效完整圈；当前可用 ')+str(len(accepted))+tr(' 圈'))
    reference=min(accepted,key=lambda lap:lap['time_s'])
    # Also compare each candidate with the actual fastest reference. Tolerance
    # chains must not allow 4 L fuel / 10 C weather differences through anchor.
    matched=[]
    for lap in accepted:
        check=match(reference['conditions'],lap['conditions'],policy)
        if check['allowed']:matched.append(lap);unknown.update(check['unknown'])
        else:different+=1
    if len(matched)<4:raise ValueError(tr('与实际参考圈条件接近的有效圈不足 4 圈；当前可用 ')+str(len(matched))+tr(' 圈'))
    reference_profile=next(selected_profiles(root,Path(reference['folder']),{reference['number']}))
    observed=dict(reference,data=reference_profile['data'],features=reference_profile.get('features',{}))
    def curves():
        grouped={}
        for lap in matched:grouped.setdefault(lap['folder'],{}).update({lap['number']:lap})
        for folder,selected in grouped.items():
            for lap in selected_profiles(root,Path(folder),set(selected)):
                if lap['number'] in selected:
                    meta=selected[lap['number']]
                    yield observed if meta is reference else dict(meta,data=lap['data'],features=lap.get('features',{}))
    from training_zones import load as zone_load
    definitions=zone_load(root,entry)
    return dict(version=3,policy=policy,samples=[dict(folder=v['folder'],number=v['number']) for v in matched],zone_definitions=definitions or zones(observed),geometry=observed.get('features',{}).get('geometry',[]),reference_features=observed.get('features',{}),entry=entry,reference=reference,count=len(matched),excluded=excluded,condition_excluded=different,
        unknown=sorted(unknown),errors=errors,priorities=aggregate(curves(),observed,definitions))
