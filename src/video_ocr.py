"""Optional Windows OCR child, launched only for distance-HUD analysis."""
import base64
import json
from pathlib import Path
import queue
import threading
from video_media import Cancelled,process

SCRIPT=r'''
$ErrorActionPreference='Stop'
[Console]::InputEncoding=[Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
$null=[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
$null=[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
$asTask=([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
 $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
 $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1)
function Await($operation,$type) {
 $task=$asTask.MakeGenericMethod($type).Invoke($null,@($operation));$task.Wait();$task.Result
}
$language=[Windows.Globalization.Language,Windows.Globalization,ContentType=WindowsRuntime]::new('en-US')
$engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if ($null -eq $engine) { $engine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($null -eq $engine) { throw 'Windows OCR language pack unavailable' }
[Console]::WriteLine('{"ready":true}')
while ($null -ne ($line=[Console]::ReadLine())) {
 try {
  $inputPaths=ConvertFrom-Json $line;$texts=@()
  foreach($imagePath in $inputPaths) {
   $file=Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($imagePath)) ([Windows.Storage.StorageFile])
   $stream=Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
   $bitmap=$null
   try {
    $decoder=Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap=Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result=Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $texts+=,$result.Text
   } finally { if ($null -ne $bitmap) { $bitmap.Dispose() };$stream.Dispose() }
   $decoder=$null;$bitmap=$null;$stream=$null;$file=$null;$result=$null
  }
  [GC]::Collect();[GC]::WaitForPendingFinalizers()
  [Console]::WriteLine((ConvertTo-Json -Compress @{texts=$texts}))
 } catch { [Console]::WriteLine((ConvertTo-Json -Compress @{error=$_.Exception.Message})) }
}
'''


class WindowsOCR:
    def __init__(self, cancel=None):
        import subprocess
        self.cancel=cancel;self.lines=queue.Queue(maxsize=2)
        encoded=base64.b64encode(SCRIPT.encode('utf-16le')).decode('ascii')
        self.process=process(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
            text=True,encoding='utf-8',bufsize=1)
        self.reader=threading.Thread(target=self._read,daemon=True);self.reader.start()
        try:
            if not self._response(25).get('ready'):raise ValueError('Windows OCR 无法启动')
        except Exception:self.close();raise

    def _read(self):
        for line in self.process.stdout:
            try:self.lines.put(json.loads(line),timeout=2)
            except (ValueError,queue.Full):pass

    def _response(self, timeout=15):
        import time
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            if self.cancel and self.cancel.is_set():raise Cancelled('已取消')
            try:
                value=self.lines.get(timeout=.1)
                if 'error' in value:raise ValueError('Windows OCR: '+value['error'])
                return value
            except queue.Empty:
                if self.process.poll() is not None:break
        raise ValueError('Windows OCR 不可用或超时；请检查系统 OCR 语言包，或使用其他输入模式')

    def recognize(self, images, scratch):
        from PIL import ImageOps,ImageStat
        paths=[]
        for i,image in enumerate(images):
            path=Path(scratch)/f'ocr-{i}.png'
            # Tight numeric crops and contrasting padding improve small HUD text.
            patch=ImageOps.autocontrast(image.convert('L'))
            dark=ImageStat.Stat(patch).mean[0]<127
            ink=patch if dark else ImageOps.invert(patch)
            box=ink.point(lambda p:255 if p>130 else 0).getbbox()
            if box:patch=patch.crop(box)
            scale=min(4,max(1,round(88/max(1,patch.height))))
            patch=patch.resize((patch.width*scale,patch.height*scale))
            if dark:patch=ImageOps.invert(patch)
            ImageOps.expand(patch,border=25,fill='white').convert('RGB').save(path)
            paths.append(str(path.resolve()))
        self.process.stdin.write(json.dumps(paths)+'\n');self.process.stdin.flush()
        return self._response()['texts']

    def close(self):
        if self.process.poll() is None:self.process.kill()
        self.process.wait(timeout=5)
        self.reader.join(2)
        self.process.stdin.close();self.process.stdout.close()
