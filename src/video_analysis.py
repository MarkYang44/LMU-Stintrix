"""Offline single-lap video pipeline. Outputs never enter the race catalog."""
from datetime import datetime,timezone
import csv
import json
import math
from pathlib import Path
import tempfile
import uuid
from video_media import Cancelled,frames,probe
from video_signal import arc_points,anchor_signature,visible,pedal,number,ocr_number
from video_alignment import native_lap,sync_map,interpolate,distance_readings,distances_for_rows

FIELDS=['video_pts_s','lap_time_s','distance_m','throttle','brake','native_throttle','native_brake','confidence','status']


def validate(config, media):
    if config.get('frame_size') and config['frame_size']!=[media['width'],media['height']]:
        raise ValueError('标定分辨率与视频不一致，请重新标定')
    start=number(config['start_s'],0);end=number(config['end_s'],start+.5,media['duration']+.02)
    hz=number(config.get('hz',20),2,30)
    if end-start>1800 or (end-start)*hz>54000:raise ValueError('只支持 30 分钟内的单圈视频')
    identity=config['identity']
    if not all(str(identity.get(k,'')).strip() for k in ('track','track_layout')):raise ValueError('请选择赛道并填写明确的布局')
    identity['length_m']=number(identity['length_m'],100,50000)
    if config['mode'] not in ('time','distance_hud','telemetry'):raise ValueError('未知输入模式')
    points={name:arc_points(config[name]) for name in ('throttle','brake')}
    boxes=[config['anchor']]
    if config['mode']=='distance_hud':boxes.extend(config[k] for k in ('distance_box','timer_box'))
    for box in boxes:
        if len(box)!=4 or not (0<=box[0]<box[2]<=media['width'] and 0<=box[1]<box[3]<=media['height']):
            raise ValueError('请在画面内框选有效区域')
        if box[2]-box[0]<8 or box[3]-box[1]<8:raise ValueError('识别区域太小')
    all_points=[p for series in points.values() for samples in series for p in samples]
    all_points.extend((box[i],box[j]) for box in boxes for i,j in ((0,1),(2,3)))
    if any(not 0<=x<=media['width'] or not 0<=y<=media['height'] for x,y in all_points):raise ValueError('圆弧超出画面')
    x=max(0,math.floor(min(p[0] for p in all_points))-2);y=max(0,math.floor(min(p[1] for p in all_points))-2)
    right=min(media['width'],math.ceil(max(p[0] for p in all_points))+2)
    bottom=min(media['height'],math.ceil(max(p[1] for p in all_points))+2)
    # RGB output avoids chroma subsampling constraints on odd crops.
    crop=(x,y,right-x,bottom-y)
    local_points={name:[[(px-x,py-y) for px,py in samples] for samples in series] for name,series in points.items()}
    local_boxes=[(a-x,b-y,c-x,d-y) for a,b,c,d in boxes]
    names=set();previous=start
    for mark in config.get('landmarks',[]):
        name=str(mark['name']).strip();when=number(mark['video_s'],start,end)
        if not name or name in names or when<previous:raise ValueError('地标名称须唯一，并按视频时间递增')
        names.add(name);previous=when
    return start,end,hz,crop,local_points,local_boxes


def analyze(config, root, cancel=None, progress=lambda *_:None):
    video=Path(config['video']).resolve();stat=video.stat();directory=config.get('ffmpeg_dir','')
    media=probe(video,directory,cancel)
    start,end,hz,crop,points,boxes=validate(config,media)
    native=mapping=None
    if config['mode']=='telemetry':
        native=native_lap(config['telemetry'],config['identity'],cancel)
        mapping=sync_map(config.get('sync',[]),start,end,native['duration'])
    output=Path(root).resolve()/'VideoCurves';output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pending-',dir=output) as scratch:
        ocr=None;ocr_failure=None
        try:
            # Anchor is sampled at the user's visible calibration frame.
            at=number(config.get('sample_s',start),start,end-.001)
            seed=frames(video,at,min(media['duration'],at+.2),hz,crop,directory,cancel)
            try:_,reference=next(seed)
            except StopIteration:raise ValueError('标定时间点没有可读取画面') from None
            finally:seed.close()
            signature=anchor_signature(reference,boxes[0])
            if config['mode']=='distance_hud':
                from video_ocr import WindowsOCR
                try:ocr=WindowsOCR(cancel)
                except (ValueError,OSError) as error:ocr_failure=str(error)
            rows=[];observations=[];last_ocr=-math.inf;errors={'throttle':[0.,0],'brake':[0.,0]}
            for pts,image in frames(video,start,end,hz,crop,directory,cancel):
                t=pts-start
                row=dict(video_pts_s=pts,lap_time_s=t,distance_m=None,throttle=None,brake=None,
                         native_throttle=None,native_brake=None,confidence=0.,status='hud_missing')
                if visible(image,boxes[0],signature):
                    values=[pedal(image,points[name],name) for name in ('throttle','brake')]
                    row.update(throttle=values[0][0],brake=values[1][0],confidence=min(v[1] for v in values),
                               status='estimated' if all(v[0] is not None for v in values) else 'arc_unreadable')
                    if ocr and t-last_ocr>=.19:
                        try:
                            texts=ocr.recognize([image.crop(box) for box in boxes[1:]],scratch)
                            distance=ocr_number(texts[0],unit=config.get('distance_unit','m'));timer=ocr_number(texts[1],timer=True)
                            observations.append((pts,distance,timer));last_ocr=t
                        except (ValueError,OSError) as error:
                            ocr_failure=str(error);ocr.close();ocr=None
                if native:
                    source_t=mapping['scale']*pts+mapping['offset']
                    sample=interpolate(native['samples'],source_t)
                    # Keep video lap-relative time for race deltas; sync only maps native distance.
                    if sample:
                        row['distance_m']=sample[1]
                        row.update(native_throttle=sample[2],native_brake=sample[3])
                        for i,name in enumerate(('throttle','brake')):
                            if row[name] is not None:errors[name][0]+=abs(row[name]-sample[i+2]);errors[name][1]+=1
                rows.append(row)
                if len(rows)>54001:raise ValueError('视频采样超出限制')
                if len(rows)%10==0:progress(min(99,int(t/(end-start)*100)),f'已分析 {t:.1f} / {end-start:.1f} 秒')
            if len(rows)<5:raise ValueError('有效视频帧不足')
            if rows[0]['video_pts_s']-start>max(.5,3/hz) or end-rows[-1]['video_pts_s']>max(.5,3/hz):
                raise ValueError('选段边界缺少视频画面；请检查完整一圈的开始 / 结束时间')
            intervals=[b['video_pts_s']-a['video_pts_s'] for a,b in zip(rows,rows[1:])]
            usable=sum(r['status']=='estimated' for r in rows)
            quality=dict(samples=len(rows),pedal_readable_ratio=usable/len(rows),
                         max_frame_gap_s=max(intervals),distance_usable=False,
                         frame_gap_limit_s=max(.25,3/hz),frame_gaps=sum(v>max(.25,3/hz) for v in intervals),
                         precision='视频估算；未经实录精度验收',missing_samples=len(rows)-usable)
            if ocr:
                accepted,ocr_quality=distance_readings(observations,start,config['identity']['length_m'])
                quality['ocr']=ocr_quality
                if ocr_quality['usable']:
                    distances_for_rows(rows,accepted);quality['distance_usable']=True
                else:quality['distance_reason']='OCR 覆盖 / 连续性未通过；保留时间轴，不计算距离时间差'
            if ocr_failure:quality['distance_reason']='OCR 不可用，保留时间轴：'+ocr_failure
            if native:
                valid=[r for r in rows if r['distance_m'] is not None]
                quality['sync']=mapping
                coverage=(valid[-1]['distance_m']-valid[0]['distance_m'])/config['identity']['length_m'] if valid else 0
                quality.update(distance_coverage=coverage,distance_usable=coverage>=.95 and len(valid)/len(rows)>=.95,
                    pedal_mae={k:v[0]/v[1] if v[1] else None for k,v in errors.items()},
                    telemetry_channel=native['channel'],telemetry_file=native['file'],telemetry_reference_hz_limit=60)
            if video.stat().st_mtime_ns!=stat.st_mtime_ns or video.stat().st_size!=stat.st_size:
                raise ValueError('视频文件仍在变化；请结束录制后重试')
            if cancel and cancel.is_set():raise Cancelled('已取消')
            identity=uuid.uuid4().hex[:12];stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            result=dict(format='stintrix.video-curves',version=1,id=identity,created_utc=stamp,
                source='video_hud_estimate',mode=config['mode'],video_file=video.name,
                identity=config['identity'],start_s=start,end_s=end,quality=quality,
                landmarks=config.get('landmarks',[]),rows=rows)
            # Store reusable geometry but no absolute source paths.
            calibration={k:v for k,v in config.items() if k not in ('video','ffmpeg_dir','telemetry')}
            folder=Path(scratch)
            (folder/'calibration.json').write_text(json.dumps(calibration,ensure_ascii=False,indent=2),encoding='utf-8')
            with (folder/'curve.json').open('w',encoding='utf-8') as stream:
                json.dump(result,stream,ensure_ascii=False,allow_nan=False)
            with (folder/'curve.csv').open('w',newline='',encoding='utf-8-sig') as stream:
                writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
            from video_report import write_report
            write_report(folder/'report.html',result)
            if ocr:ocr.close();ocr=None
            for file in folder.glob('ocr-*.png'):file.unlink()
            target=output/(stamp+'-'+identity)
            if not folder.resolve().is_relative_to(output) or not target.resolve().is_relative_to(output) or target.exists():
                raise ValueError('输出路径无效或已存在')
            folder.rename(target)
            progress(100,'提取完成')
            return dict(folder=str(target),report=str(target/'report.html'),quality=quality)
        finally:
            if ocr:ocr.close()
