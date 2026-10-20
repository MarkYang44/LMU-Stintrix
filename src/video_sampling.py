"""Stable source-frame selection and measured extraction rates."""
import math


def selection(hz):
    if not math.isfinite(hz) or not 2<=hz<=30:raise ValueError('视频提取频率必须在 2–30 Hz')
    # Each absolute time bucket contributes at most one real frame. Half a
    # source tick handles timestamp quantization, without cumulative drift.
    current=f'floor((t+TB/2)*{hz:.9f}+1e-9)'
    previous=f'floor((prev_selected_t+TB/2)*{hz:.9f}+1e-9)'
    return f'isnan(prev_selected_t)+gt({current},{previous})'


def measured(rows,hz):
    elapsed=rows[-1]['video_pts_s']-rows[0]['video_pts_s'] if len(rows)>1 else 0
    return dict(requested_sample_hz=hz,actual_sample_hz=(len(rows)-1)/elapsed if elapsed>0 else None,
                selection='source_pts_time_grid')
