# README screenshot provenance / 首页截图来源

The English and Simplified Chinese READMEs use the same four views, in the same order. Captured from the **v0.2.43 LMU source UI** on Windows; no UI mockups, generated interface artwork, or relabeled screenshots are used. These are historical captures; the current interface also includes a simulator selector and later workflow improvements.

中英文首页使用相同的四组视图与展示顺序，来自 Windows 上运行的 **v0.2.43 LMU 源码界面**。没有生成界面、拼接控件或替换截图文字；这些是历史截图，当前界面已增加游戏选择与后续操作优化。

| File in `en/` and `zh-CN/` | Capture | Data source |
| --- | --- | --- |
| `control-center.webp` | 1280 × 900, dark theme | Actual control center, before HUD startup |
| `personal-best.webp` | 1280 × 900, dark theme | Generated documentation sessions, processed by the normal lap exporter and record browser |
| `input-hud.webp` | 1280 × 450, clean controls mode | Built-in DEMO; graphics are language-neutral in both captures |
| `session-library.webp` | 1280 × 900, dark theme | The same eight generated documentation sessions |

All lap times, dates, conditions, and input traces in these samples are illustrative fixture data. They do not establish real lap performance, recognition accuracy, or game compatibility. Vehicle photos are the app's existing catalog assets; they are not images of a recorded fixture race. No personal sessions are used.

示例圈速、日期、条件和输入曲线均为合成数据，不代表真实驾驶成绩、识别精度或兼容性测试。车型照片来自程序已有图鉴，不表示示例赛事的实录画面；没有读取私人赛事。

The same generated files, selected record, window size, and scroll target are reused for both languages. Font metrics can change the layout slightly. HUD captures are successive frames of the same running demo, so the waveform endpoint can differ. WebP encoding is lossless; screenshots are captured from the application window, without desktop content.

两种语言使用相同示例文件、选中纪录、窗口尺寸和滚动目标；字体尺寸差异会带来少量布局变化。HUD 为同一演示流的相邻画面，曲线末端可能略有差异。WebP 无损编码，捕获范围仅为应用窗口。

## Reproduce / 重新采集

From a configured Windows source checkout:

```powershell
.venv\Scripts\python.exe tools/capture_readme.py
```

The script creates a new ignored directory under `_local/readme-capture/`, generates its own sessions, captures both locales, and records dimensions and byte sizes in `capture-evidence.json`. Review the output before replacing these public images and updating the exact allowlist in `tools/readme_assets.py`. No new content hashing is performed.

脚本只在 `_local/readme-capture/` 创建新的私有目录，生成自用示例并采集两种语言；证据记录图片尺寸和字节数。人工检查后再替换公开图片，并更新 `tools/readme_assets.py` 的精确白名单，不新增内容哈希。

Older screenshots from v0.2.21 are no longer used on the home page. Bilingual offline lap-analysis reports are not currently available, so no English report screenshot is presented as if it existed. The native personal-record view and clean HUD are used instead.

旧 v0.2.21 截图已从首页移除。离线圈速分析报告目前没有完整双语界面，因此没有伪造英文报告截图；首页改用双语个人纪录页面和纯净 HUD。
