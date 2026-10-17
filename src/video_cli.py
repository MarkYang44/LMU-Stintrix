"""Shared source/portable offline video command; no Tk or HUD startup."""
import argparse
import json
from pathlib import Path
import signal
import sys
import threading


def main(argv=None):
    if sys.stdout is not None and hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='Local video HUD extraction; separate from native records')
    parser.add_argument('--config',type=Path);parser.add_argument('--video',type=Path)
    parser.add_argument('--compare-result',type=Path);parser.add_argument('--reference-lap',type=Path)
    parser.add_argument('--channel',choices=('raw','filtered'),default='filtered')
    parser.add_argument('--bind-history-layout',action='store_true')
    parser.add_argument('--output-root',type=Path);parser.add_argument('--ffmpeg-dir',default='');parser.add_argument('--telemetry',type=Path)
    args=parser.parse_args(argv)
    from paths import data_directory
    cancel=threading.Event();signal.signal(signal.SIGINT,lambda *_:cancel.set())
    try:
        if args.compare_result:
            if not args.reference_lap:raise ValueError('历史对比需要 --reference-lap')
            from video_history import export_comparison
            result=export_comparison(args.compare_result,args.reference_lap,args.output_root or data_directory(),args.channel,args.bind_history_layout,cancel=cancel)
        else:
            if not args.config or not args.video:raise ValueError('视频提取需要 --config 和 --video')
            from video_analysis import analyze
            config=json.loads(args.config.read_text(encoding='utf-8-sig'));config.update(video=str(args.video),ffmpeg_dir=args.ffmpeg_dir)
            if args.telemetry:config['telemetry']=str(args.telemetry)
            result=analyze(config,args.output_root or data_directory(),cancel,lambda p,t:print(f'{p}% {t}',flush=True))
    except Exception as error:
        print(str(error),file=sys.stderr)
        # Windowed portable invocations have no terminal. Leave an explicit local receipt.
        root=args.output_root or data_directory();root.mkdir(parents=True,exist_ok=True)
        (root/'video_cli_error.txt').write_text(str(error),encoding='utf-8');return 1
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0
