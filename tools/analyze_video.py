"""Run a saved local video calibration without opening a second GUI."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


from video_cli import main


if __name__=='__main__':raise SystemExit(main())
