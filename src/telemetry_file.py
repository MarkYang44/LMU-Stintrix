"""Path-compatible read adapter for retired CSVs; no global pathlib patches."""
import io,os
from pathlib import Path as NativePath
from types import SimpleNamespace
from column_store import NAMES,packed,Reader,open_csv


class Path(type(NativePath())):
    def _virtual(self):
        if self.name not in NAMES or NativePath(str(self)).is_file():return False
        path=packed(self)
        if path.is_symlink() or path.is_junction():raise OSError('Linked column store is not supported')
        return path.is_file()
    def open(self,mode='r',buffering=-1,encoding=None,errors=None,newline=None):
        if self._virtual():
            if any(c in mode for c in 'wax+'):raise OSError('Compressed telemetry is read-only; export CSV first')
            return open_csv(self,mode,encoding,errors,newline)
        return super().open(mode,buffering,encoding,errors,newline)
    def exists(self,*,follow_symlinks=True):return NativePath(str(self)).exists(follow_symlinks=follow_symlinks) or self._virtual()
    def is_file(self,*,follow_symlinks=True):return NativePath(str(self)).is_file(follow_symlinks=follow_symlinks) or self._virtual()
    def stat(self,*,follow_symlinks=True):
        try:return NativePath(str(self)).stat(follow_symlinks=follow_symlinks)
        except FileNotFoundError:
            if self.name not in NAMES or not packed(self).is_file():raise
            reader=Reader(packed(self));s=packed(self).stat()
            return SimpleNamespace(st_size=reader.logical_bytes,st_mtime_ns=reader.mtime_ns,st_mtime=reader.mtime_ns/1e9,st_mode=s.st_mode)
