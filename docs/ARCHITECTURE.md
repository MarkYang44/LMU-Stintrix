# 模块与维护边界

v0.2.52：`control_confirm` 使用明确决策键并管理三个显示编辑器的关闭链；`control_settings_search` 只索引已渲染的控件及明确入口；`control_validation` 消费兼容 `ValueError` 的 `PreferenceError.fields/limits`，验证边界仍由原后端定义。`control_tooltip` 的延时任务和临时根绑定随表格销毁、滚动和失焦清理；复制为用户主动操作，不改行身份或数据。显示草稿只存在于控制中心实例内，不新增磁盘配置格式。

入口 `src/inputscope.py` 保留命令行和原有类 / 函数导出。`App` 及 Tk 对象按需加载；导入采集核心或运行 `--version` / `--import-duckdb` 无需加载 Tk。启动脚本、快捷键、HUD 模式和数据路径保持兼容。

| 模块 | 职责 |
| --- | --- |
| app_config.py / paths.py | 公共 CSV 列定义、界面常量、便携资源与本机私有路径 |
| telemetry.py | 验证共享内存快照、提取遥测；只读打开已有 LMU_Data |
| engine.py / sampling.py | 采样策略、时间调度、实时分析与双通道历史 |
| recorder.py / storage.py | 原样精度的 CSV、检查点、写盘故障与恢复 |
| session_reports.py / reporting.py | 结束后的分析调度、流式离线 HTML |
| race_journal.py | 官方计时与赛事事件；只对状态变化写入独立有界队列，不扩充高频输入行 |
| race_model.py / race_report.py | 流式圈摘要、官方圈号对齐、完整事件日志与带校验的生成缓存 |
| race_images.py / windows_png.py / race_art.py | 逐页高清 PNG、Windows 原生 GDI+ 与可选私有车辆照片 |
| hud.py / hud_geometry.py | Windows Tk 窗口、交互与绘制、几何和方向盘 |
| background.py | 至多两条后台任务线程；结果回到 GUI 主线程 |
| laps.py / sessionlab.py / reference.py | 完整圈、选定圈与参考圈分析 |
| vehiclelab.py / endurance.py | 轮胎、燃油、能量、进站、stint 和天气 |
| management.py / session_archive.py | 比赛库、备注和比赛包导入导出 |
| *view.js / laplab.js / dataview.js | 独立网页的图表、地图、分析和压缩数据读取 |

核心模块不导入 HUD 或 Tk，也不依赖入口模块，因此可独立测试或用于无界面的采集 / 分析工具。界面读取 Engine 的快照和有界缓存，不负责共享内存读取或比赛格式写入。

## 时间索引

NumericRing 保留 float64 数据和逻辑顺序。`lower_bound` 在首列时间戳上二分，支持环形回绕与相等时间；`iter_since` 只构建窗口内行，`rate_since` 直接计算首尾跨度。使用时间索引的调用者必须追加非递减时间戳，并在场次重置时清空。Engine 的共享缓存仍受原有锁保护；GUI 的绘制计数缓存仅由 GUI 线程访问。

完整 20 秒双通道历史、极值桶、单帧尖峰和完整赛事 CSV 都保留。性能收益来自跳过不可见行与避免临时时间列表，不依赖降低采样频率。

## 后台任务与退出

App 在主线程提交任务，并定时从完成队列取结果。后台任务禁止调用 Tk，包括 `root.after`。日志导入、完整圈提取、比赛包传输、库扫描和参考圈加载共享两线程执行器。关闭窗口时禁止新任务，完成已提交的工作，再释放界面；完成结果在关闭期间不再触发 UI 操作。

Recorder 的写盘及结束报告保留各自生命周期，App 继续等待 CSV 写完和报告完成。结束报告保持串行处理，避免多个大赛事同时生成网页的内存峰值。

赛后图片复用同一后台生命周期，在事件队列排空后生成。官方 `mLastSector2` 是 S1+S2，必须相减得到 S2；官方已完成圈数与可能从 0 开始的遥测圈号通过圈起点对齐。缓存 scoring 的车辆扫描，但同一时间戳下的终场名次 / 圈数变化仍采集；不把当前圈的计圈标志误用作上一圈有效性。事件记录与高频输入独立，有界队列溢出或写盘失败会显式报错。

`racecom_bridge` 用标准库写原版 XLSX / JSON / TXT，`renderer_process` 在独立受限生命周期中调用用户配置的原版生成器。Windows Job 关闭时结束属于本次任务的 PyInstaller 子进程，超时不会留下生成器。两个图像均成功才提交。`race_report` 缓存源文件、生成器、校准与照片哈希；更换生成方式备份旧报告。未配置原版不静默改变样式。兼容模式仍使用系统 GDI+ 逐页生成，CSV 摘要不持有整场样本。未知字段不补造，个人图像库不进入发布 ZIP。

`control_center` 默认启动时不创建 Engine；HUD 启动后共享一个 Tcl 解释器并使用独立 Toplevel。停止 HUD 等待写盘与报告后释放 Engine 缓存，控制中心保留。分类设置通过 `control_settings` 验证并保留未编辑偏好，可在未启动 HUD 时保存，也可实时应用并记录策略历史。`control_widgets` 提供轻量工业风组件与可切换的深浅色配色，正文保持不透明；没有第二个 EXE 或浏览器运行包。

## 兼容与验证

CSV 字段、JSON 格式标记、原始 / 过滤后输入、采样设置和旧记录路径保持一致。入口继续导出 Engine、Recorder、SharedReader、App 及既有辅助函数；测试替换全局依赖时应 patch 实际所属模块，例如 `recorder.make_report` 或 `hud.ROOT`。

开发测试只放在 tests/，开发工具只放在 tools/；便携包和编译 EXE 继续排除这些模块。发布白名单与个人数据哈希校验分别验证分享内容和本机数据保护。

The desktop shell is separated into `control_shell.py` (DPI layout / navigation), `control_widgets.py` (industrial surfaces / controls), `control_motion.py` (elapsed-time transitions / accumulated pixel scrolling), `control_list.py` (virtual session rows / selection / keyboard), `control_theme.py` (dark and light palettes / local preference / offline report embedding), and `branding.py` (window / taskbar identity). Theme changes rebuild the shell without recreating the HUD, Engine or recorder, and preserve page state. Table rendering is limited to visible rows; its text cache is bounded at 1024 entries. Completed animations schedule no frames.

Build-only `tools/build_brand.py` copies two hash-reviewed GTD assets and extracts six existing PNG frames without image processing dependencies. `interface_theme.js` embeds the same palettes into standalone reports, stores only a theme preference locally, and invalidates chart backgrounds by including the mode in cache keys. Historical personal HTML and RaceCom image layouts are not rewritten by an application update.


## v0.2.47：界面状态与离线视频边界

`control_forms.py` 负责设置表单、基准值及未保存状态；界面重建仅保存有改动的字段，草稿留在内存，不提前写入偏好。`control_transfers.py` 接管控制中心存储整理与导入导出动作，现有入口方法继续转发调用，后台任务及格式契约保持一致。

`video_sampling.py` 以固定时间桶选择真实源帧，按输入 timebase 半个 tick 容差处理量化，保留实际 PTS、不复制帧。`video_results.py` 以有界元数据头发现旧结果；新增提取同时保存私有摘要。`control_video_results.py` 提供可重开的只读列表，与解码、标定及原生赛事记录分离。


## v0.2.48：工作上下文与页面任务

`control_context.py` 保存有界的进程内页面上下文；异步赛事扫描完成后按文件夹身份恢复选择，不沿用易变化的行号。`control_toolbar.py` 管理固定操作栏和可用性，`control_sections.py` / `control_data.py` 保留任务组的控件与输入。`control_disposal.py` 在页面退休时于 GUI 线程销毁页面拥有的 Tk 变量，避免它们在后台 GC 中访问 Tcl；外部全局变量与缓存页保留。

`Select.labels` 只改变显示名称，变量及设置格式不变。`control_video_options.py` 合并用户主动修改后的偏好写入，不在每个字符输入时写盘；标定几何仍通过原有匹配流程验证。

`hud_layouts.py` 用独立私有 JSON 保存命名布局、最近画面和有界回退历史；`hud_presentation.py` 只改窗口，`layout_actions.py` 对应用失败做回退。显隐覆盖不写车辆 / 耐力采样配置，静默优先；主窗口与附加窗口均使用同一显示判定。

`native_hotkeys.py` 在独立 Win32 消息线程注册快捷键，以阻塞 GetMessage 等待；组合交换复用现有注册，新注册失败时撤销新项并保留旧绑定。GUI 线程由 `shortcut_service.py` 分派动作，停止时注销；控制中心与 HUD 共享服务，不重复注册。旧 F 键通过 `shortcut_keys.legacy_state` 排除修饰键组合及释放顺序造成的误触。

`recent_session.py` 只记真实且完整保存的最近赛事，用现有报告步骤收据区分复盘和图片就绪状态，不读采样 CSV。`control_recent_session.py` 复用固定操作栏及私有备注入口，不重复生成报告、不抢占比赛焦点。
# v0.2.51 display workflow additions

`control_layout_preview` edits only an editor-owned snapshot and maps actual monitor rectangles, including negative origins. `control_layouts` owns dirty baselines and session-local drafts; no preview gesture invokes recording or window-placement APIs. `control_run_state` shares the effective idle presentation with the next HUD launch and caches private settings by file revision. Explicit idle display adjustments use the existing bounded layout undo history without overwriting named profiles.

`control_table_preferences` validates and atomically saves per-view presentation to private `table_views.json`. `control_list` retains original row tuples and stable IDs while drawing selected visible columns in scrolling and pinned passes. Header resize persists logical widths; DPI scaling is applied at the display boundary. The preferences file is excluded by Git, publication audit and bundle audit.

## v0.2.53 interaction boundaries

`control_forms.close_forms` captures all mounted and retained numeric drafts, validates every module before any write, and retains unfinished modules if a later write fails. `control_profile` registers with the shared editor close guard. Conditional mode hints change presentation only; the stored values and authoritative validators stay intact.

`control_batch.run_items` checks a stop event only between complete operations. Worker threads publish plain status tuples to a queue; GUI-thread callbacks update the table, retry only failed indices or continue pending ones. Hiding a task window keeps the current job alive; starting a new completed-job replacement disposes the old window. Existing archive and lossless storage functions still own filesystem safety.

`control_table_sort` maps headings to existing metadata sort IDs, appending only the two reverse numeric sorts. Table values, stable selection and column preferences remain separate. `control_video_close` keeps hidden-task callbacks alive, explicitly handles app exit, and stores optional draft fields separately from extraction output. Restoring a draft cannot change decoder/tool paths; draft extensions are validated before mutating the editor.

## v0.2.54 context and cross-window actions

`control_notes` owns private annotation drafts, checks limits before atomic publication, and merges only the intended note fields into the latest file. `control_form_bar` follows field focus to the current module, counts changed fields, and reuses the authoritative form save/reset functions; all temporary root bindings are removed with the toolbar. `control_danger` supplies one explicit, cancel-focused confirmation for frozen targets, while existing deletion functions retain filesystem checks and backup semantics.

Batch history is session-local: unsuccessful and pending jobs remain resumable; older successful jobs are bounded. Both new tasks and historical retries consult all running jobs. A/B shortcuts operate only on the selected sessions' verified lap summaries, provide early compatibility feedback, and retain the original export-time validation. Recent video results pass a rechecked local curve file directly to the existing history comparison window.

## v0.2.56 maintenance workflows

`control_worklist` owns search, generation-guarded loading, stable selection, readonly detail and explicit action state for the report, cache and split-review tools. It removes window-owned traces and variables on the GUI thread. Maintenance button state is refreshed by the existing control-center tick; it never polls the filesystem while idle.

`control_report_tasks` sends only selected unfinished reports to the existing batch runner and report worker. Ready reports are rechecked before retry; deferred and failed reports remain retryable. `control_cache_panel` freezes the allowlisted target selection, rechecks offline state after confirmation, and keeps successful size feedback or errors visible. Starting a new recorder waits for active cache writes or report-retry jobs. `split_checks` atomically changes only explicit marks, preserving unknown fields and refusing malformed state; the UI holds a bounded session-local undo stack.

## v0.2.57 profile and lap selector continuity

`control_profile` reads recorded car names through the metadata inventory in a background task, guards late callbacks, and reuses the current editor. Default loading and revert remain drafts; only explicit save merges the selected car into the freshly read profile map. Search-target focus uses the shared scroll reveal helper. Save and close retain the existing draft guard contract.

`control_lap_pair.select_initial` preserves search and unchanged sides, accepts the latest pending selection during inventory loading, and refreshes metadata for newly selected events. Generation checks reject superseded lap scans. Comparison workers capture immutable source selections while every event/lap control is disabled. The last successful report path remains available independently of subsequent selection changes or open failures; reopening never reruns extraction. Both windows wrap actions at translated natural widths and keep actionable feedback visible.

## v0.2.58 achievement preview and export

`control_achievement` owns record-keyed window reuse, one active preview with latest-revision coalescing, immutable export snapshots and GUI-thread disposal. Stale render results are discarded before presentation. The previous preview stays visible while updates run, but export requires the current revision. Export reads the approved full-resolution image directly through `achievement_card.save_image`; privacy controls are locked until that write finishes. Independent open/folder actions and a readonly path keep successful files accessible after viewer failure.

PNG writes use a unique pending file and atomic Windows rename; cleanup removes only a pending file created by that invocation. Caption translations are captured in the payload before worker rendering, preventing mixed-language cards. The standard `render` API remains available. Window closure detaches UI callbacks while submitted writes finish and report their paths through the main status. No periodic poll or source-telemetry cache is added. The shared image surface supports instant keyboard-driven arrivals; theme retinting also covers readonly Entry backgrounds.


## v0.2.59 report image reading

`control_report_images` routes report PNG actions into one reusable viewer per control center. Existing files bypass generation validation and external application startup; missing files submit one coalesced generation job through the normal background queue. Explicit regeneration uses `race_report.generate(force=True)` and retains previous report artifacts before rendering. HTML opening and report validity algorithms are unchanged.

`report_images.ImageLoader` owns one read-only decoder independent of shared report-generation workers and serialization. Requests coalesce to the latest stamp (resolved path, size, mtime and ctime). Its LRU retains at most two decoded originals, evicting to a 64 MiB pixel budget except for a single oversized current original. Reads finish before file streams close; no Tk callbacks or widgets enter this worker. Application close rejects new reads and drops the cache while queued report writes follow the existing graceful shutdown path.

`control_image_viewport` keeps full-resolution source pixels and renders only the visible crop into Tk. Pan/zoom draws are coalesced; gesture previews use bilinear resampling and settle with Lanczos. Palette images convert only their display tile to RGBA before resizing. Reader-local stamp-keyed poses survive report switching without changing the main list's selection, query or scroll. Errors can reload or hand the unchanged file to the system viewer; closing the reader never cancels an already submitted report write.


## v0.2.60 reusable analysis sessions

`control_analysis_window.AnalysisWindow` manages one window per analysis kind and versioned record identity. UI-owned raw drafts are separate from the last completed result, current request and latest pending request. A result can enable export only when it matches the current draft and no scan/write is in progress. Only the newest queued request starts after the active one; callbacks ignore destroyed windows and outdated drafts.

Workers receive pure scanner functions, copied policy snapshots and filesystem paths. Configuration merges preserve unknown fields, skip unchanged writes and reject malformed existing JSON. A queued request accepted before close is submitted through the normal task tracker and waits on the previous future before persisting/scanning, maintaining order and normal shutdown guarantees. All Tk variables and timers are retired on the GUI thread. Unsubmitted drafts use the existing explicit editor-close guard.

Training and comparable windows retain their existing analysis functions and export writers. Export jobs capture the selected result object before submission and lock editable conditions until completion; file save and shell opening are separate outcomes. Closed-window export completion reports its path on the main UI without opening a browser. `control_analysis_policy` adds responsive field layout and inline feedback while delegating validation to `condition_match.settings`.

Comparable rows use local unique row IDs and preserve identity by folder plus observed timestamp; equal timestamps no longer collide. Chart metric IDs remain language-independent. Training selection uses zone name and distance; duplicate target creation is guarded per completed analysis revision. No sampling, statistics, comparison scope or training-score algorithms change.
