# Stintrix for macOS

macOS is the **offline analysis** edition. Windows keeps live telemetry, recording, HUD, game hotkeys and the full analysis toolkit. Both editions use the same session readers, lossless telemetry format, analysis engine, comparison pages, report pipeline and personal-record rules. No Wine, virtual machine, game installation or background capture service is required on Mac.

## Install on Apple Silicon

Requires Apple Silicon (M1 or newer) and macOS 13 or later. Intel Macs are not included in this first build. Download the [v0.4.0 DMG](https://github.com/MarkYang44/LMU-Stintrix/releases/download/v0.4.0/LMU-Stintrix-v0.4.0-macos-arm64.dmg) or [application ZIP](https://github.com/MarkYang44/LMU-Stintrix/releases/download/v0.4.0/LMU-Stintrix-v0.4.0-macos-arm64.zip) from the Release. Verify it against the same Release's `SHA256SUMS.txt`, open the DMG and drag **LMU-Stintrix.app** into **Applications**. You can also unzip the application ZIP and copy the app directly. Development builds remain available as **LMU-Stintrix-macos-arm64** Actions artifacts. The version-tag workflow publishes both platforms only after Windows and Mac validation succeed.

The default build is ad-hoc signed and **not notarized**. Gatekeeper may require **System Settings → Privacy & Security → Open Anyway** on first launch. An Apple Developer ID certificate is required for normal signed/notarized public distribution; no certificate or account is embedded in this project. The app does not need Screen Recording, Accessibility or game-memory permissions.

## Bring your Windows records

1. Select **LMU** or **AC EVO** using the context selector under the logo. Each has a separate library; imports from the other game are rejected until you switch.
2. Use **Session review → More actions → Import session archive** for the existing Stintrix ZIP / 7z formats (both supported manifest versions). Windows should finish saving and exporting before you transfer the archive.
3. For an unpacked Windows record, choose **Import Windows session folder** and select the **single session folder containing `session.json` and `inputs.csv` or `inputs.csv.stc`**. It is a copy operation: original timestamps, metadata, raw bytes and unknown fields remain intact. Nested links, active records, partial writes, unsafe paths and oversized imports are rejected. A changing source is rolled back before publication.
4. LMU official `.duckdb` telemetry remains available under **Images & data → Archives → Import official telemetry**. Use only completed telemetry files.
5. Reuse existing reports or select report tasks to regenerate analysis, comparison HTML, lap sheets and race logs. Personal records are calculated from the imported sessions. Ordinary LMGT3 and explicitly marked No BOP records retain their separate identities.

No downsampling, float32 conversion, rounding of stored samples or invented missing channels is added. ZIP/7z exports stay compatible with Windows. STX column storage is lossless on both systems. NTFS LZX is Windows-only; Mac uses the shared column storage and normal archive compression.

Keep related sessions in their own folders. A bare CSV without `session.json` cannot reliably identify its simulator, track, timing rules or car and is not silently guessed. To transfer notes, use a Stintrix archive; library-wide settings and private artwork are not bundled automatically. Optional official EVO artwork is downloaded only on request. Locally cached artwork and HTML reports work offline afterward. Windows RaceCom software is not included or executed on macOS; Mac generates equivalent **content** using the built-in PNG renderer, with its own paginated industrial layout. Existing imported RaceCom PNGs remain viewable.

## Mac layout and storage

The navigation contains session review, images & data, personal records, track guide, car catalogue and offline preferences. Capture, HUD, live sampling, game-interface diagnostics and global game hotkeys are absent. Search, filtering, batch tasks, deletion safeguards, notes, charts, lap comparison, training analysis and exports keep their shared workflows. Analysis availability still depends on the game and the channels actually saved by Windows.

Data lives in `~/Library/Application Support/LMU-Stintrix`; EVO uses its `Simulators/ac_evo` subfolder. Updating or moving the `.app` leaves this data in place. To use an external drive, set `LMU_STINTRIX_DATA_DIR` when launching the executable. Never put data inside the signed `.app`. The offline preferences page opens the active data folder in Finder. Windows reads game icons from the installed games; on Mac the selector shows the LMU vector mark and an EVO badge, or your own icon files (for example `evo.ico` copied from the Windows game folder) chosen under **Offline preferences → Game icons**. They stay in the local library; no game artwork ships with Stintrix.

Command+K opens quick navigation; Command+F searches; Command+1–6 select the visible pages. Control shortcuts also remain available. F1 lists keyboard actions. Standard macOS text editing uses Command.

Video analysis remains local and optional. Install native `ffmpeg` and `ffprobe` and select their folder in video preferences; packaged numeric OCR uses Apple Vision. It launches only for the distance-HUD video input mode. No OCR process runs during normal analysis. Image/curve output quality remains bounded by the source video, as on Windows.

## Build and verify

On an Apple Silicon Mac with Xcode Command Line Tools and arm64 CPython 3.13 (including Tk):

```sh
python3.13 -m venv .venv-mac
.venv-mac/bin/python -m pip install --only-binary=:all: -r requirements-build.txt
.venv-mac/bin/python tools/install_macos_7zip.py
.venv-mac/bin/python tools/run_tests.py --tests tests.test_macos_offline --plan
.venv-mac/bin/python tools/run_tests.py --tests tests.test_macos_offline
.venv-mac/bin/python tools/build_macos.py
.venv-mac/bin/python tools/check_macos_bundle.py
```

Release builds use the GitHub Actions CPython 3.13 (python.org framework with Tk 8.6). Homebrew's `python@3.13` bundles Tk 9, which is supported (trackpad `TouchpadScroll`, 120-per-notch wheels) but draws text larger, so treat Homebrew builds as local verification builds rather than release equivalents.

For source development use `.venv-mac/bin/python src/inputscope.py`. On Windows, `--offline` is an explicit preview mode; the normal Windows entry retains all live features. Mac source video OCR requires compiling `tools/macos_ocr.swift` to `_local/macos-tools/vision-ocr`; the build command does this automatically.

The build verifies the official 7-Zip macOS archive and executable using pinned SHA256 values, compiles the Apple Vision worker, excludes live adapters/EXEs/private data, ad-hoc signs the app and creates the DMG. `STINTRIX_MAC_SIGN_IDENTITY` may select an already-installed Developer ID instead of ad-hoc signing. Submit the final app with Apple's `notarytool` and staple the ticket before creating public ZIP/DMG assets when distributing a notarized edition; the workflow does not claim notarization without credentials.

The delivered-app check extracts the actual ZIP into a path with spaces, verifies arm64 and its signature, launches the frozen app without the development environment, imports synthetic folder/ZIP/7z records, generates native reports, visits all offline pages in both simulator contexts, verifies sources remain unchanged and checks that the app did not write into its bundle. This is targeted compatibility validation, not a complete historical regression or a substitute for user acceptance on real transferred records.

## 中文快速说明

macOS 版仅做离线赛事分析，保留原有工业风、深浅主题和中英界面。先选择 LMU 或 AC EVO，再从赛事复盘的「更多操作」导入比赛包或 Windows 单场赛事文件夹；两款游戏的记录保持隔离。也能读取无损 `.csv.stc`，无需先还原全部 CSV。比赛原文件不改动，导入中发生变化会回滚。

数据默认在 `~/Library/Application Support/LMU-Stintrix`，升级 `.app` 不影响数据。游戏图标在 Windows 上取自已安装的游戏；Mac 可在「离线偏好设置 → 游戏图标」选择你自己的图标文件（如从 Windows 游戏目录复制的 `evo.ico`），只保存在本机资料库，程序不分发游戏图片。报告图片使用内置原生引擎；Windows 的 RaceCom 版式不在 Mac 上执行，已保存的图片可以直接查看。Apple Silicon 构建流程会输出 `.app`、ZIP、DMG 和 SHA256；默认只有临时签名，首次打开可能需要在系统隐私与安全设置允许。Windows 正常启动仍保留全部实时功能。

For a real MacBook acceptance pass, use the [Codex handoff prompt](MACOS_CODEX_HANDOFF.md).
