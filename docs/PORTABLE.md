# LMU Stintrix · Windows x64 便携版

完整解压到可写文件夹，双击 **LMU-Stintrix.exe** 打开控制中心，在左上角选择 **LMU** 或 **AC EVO**，再点击 **启动记录**。无需安装 Python，无需往游戏目录复制文件。请保留 EXE 旁的 **_internal** 文件夹。

右上角可切换深色 / 浅色工业风主题；选择只保存在本机。赛事列表支持平滑滚动、Ctrl / Shift 多选和键盘浏览，切换主题不中断正在运行的 HUD。

- 不开游戏时，在 LMU 控制中心点击 **演示模式**；`Demo.cmd` 保留为快捷入口。
- 在控制中心的 **显示模式** 选择纯曲线；`Start Clean.cmd` 保留为快捷入口。
- 另一种纯净模式同时显示曲线、油刹柱形图和方向盘；启动脚本继续兼容。
- **赛事复盘** 共用一个列表打开圈速单、比赛日志、记录概览与圈速对比；先选赛道，再选对应赛事和有效完整圈。两款游戏均支持个人最快圈和纪录履历：LMU 按布局／组别区分，EVO 按布局／具体车型区分。分区条件、轮胎摘要及完整车辆分析属于 LMU 功能。
- HUD 标题栏菜单按钮打开控制中心；右键快捷菜单继续保留。`LMU-Stintrix.exe --hud` 可直接进入旧 HUD。

LMU Qualify / Race、EVO 计时赛／正赛自动记录；可在 **采样与遥测 → 记录练习赛** 开启 Practice 完整记录，默认关闭，EVO 同时支持按需记录巡航，LMU Warmup 仅实时显示。点击 **停止并保存** 会立即隐藏 HUD，并在后台完整收尾；正常退出或切换游戏会等待写入与后台任务完成。LMU 记录保存在 `data/`，EVO 记录保存在 `data/Simulators/ac_evo/`；两者分别显示，旧 LMU 数据不搬迁。

EVO 提供完整物理／仪表输入曲线、有效圈 A/B 对比、个人纪录、圈速单和赛事日志；缺少完整圈证据的旧记录仍可读取，不补造圈速或完赛成绩。条件训练、实时参考圈、官方成绩导入与附加车辆面板仍属于 LMU 功能。EVO 车型图库支持品牌／类别筛选，赛道卡可切换已核实布局；官方照片和线路图需明确点击下载，只保存在本机。详细边界见 [LMU 与 AC EVO](docs/SIMULATORS.md)。

**图像与数据 → 报告与存储** 可查看分步报告状态、批量重试失败项及查看缓存／导出占用；赛事包和存储共用列表，保留筛选与选择。EVO 采集期间延期处理派生报告与压缩，HUD 默认手动 60 Hz，输入采样率独立保留。实机驾驶兼容性仍需验收，不承诺游戏帧率提升比例。

要使用 RaceCom 原版圈速单和比赛日志，在 **图像与数据** 中选择自己 RaceCom 安装目录里的 **Image Generate.exe**，保留该目录下的 `Source` 文件夹。生成器不会随本软件分发；未配置时记录仍保存，可配置后补图。可明确选择 `native` 兼容版式；演示模式使用兼容版式。

完整操作见 [使用说明](docs/USAGE.md)，本机记录与设置保护见 [数据与隐私](docs/PRIVACY.md)。便携包只包含运行文件、启动入口、使用文档和必要许可证；开发测试、构建发布脚本和自检程序留在源码仓库。

更新时保留自己的 `data/` 和 `local_settings.json`。演示记录也仅保存在本机；软件不会自动上传任何遥测数据。打不开程序时查看 `data/startup_error.log`。

源码、更新与问题反馈：[MarkYang44/LMU-Stintrix](https://github.com/MarkYang44/LMU-Stintrix)。公开版不附带授权不明的赛道底图，仍可根据记录中的世界坐标 / GPS 展示实测轨迹。

**English:** Fully extract, then run **LMU-Stintrix.exe** and choose **LMU** or **AC EVO**. Keep **_internal** next to the executable. Python is bundled. Each simulator has its own local sessions, settings and records. EVO includes verified-lap input comparison, personal records, lap sheets and journals; condition-based training, official results and extra vehicle panels remain LMU features. No game files are modified; all telemetry and settings stay local. Developer tests and standalone environment-check tools are excluded from this portable package. See [Simulator support](docs/SIMULATORS.md) for limits and live-driving validation status.

## Windows 快捷启动与表单操作

控制中心 **运行与 HUD → Windows 快捷启动 → 添加 / 更新开始菜单** 会创建当前用户的 `LMU Stintrix` 快捷方式。程序会核验 Windows 应用目录，确认识别后可在 Windows 搜索中输入 `Stintrix` 或 `LMU`，也可从开始菜单的所有应用启动；无需管理员权限。可右键搜索结果固定到开始菜单或任务栏。移动便携文件夹后，重新打开 EXE 点击更新入口即可；移除入口不会删除程序或个人数据。首次解压仍需保留完整 `_internal` 文件夹。

表单使用统一的切角输入框与下拉面板：黄绿焦点描边、短展开过渡、平滑选项高亮，兼容深浅主题。下拉框支持方向键、Home / End、输入前缀跳转、Enter 确认、Escape 取消和 Tab 切换；长列表可滚动。动画仅在交互时运行，离开页面会清理弹层与回调。

已启用的入口在新版启动时会按当前登录用户检查并修复；检查在后台进行。若显示“Windows 尚未列出应用”，可稍后再次点击更新。入口识别状态保存在本机 `data/desktop_registration.json`，不参与发布。

控制中心顶部 **EN / 中文** 可切换整个菜单语言，重启后保留；主题和语言分别保存到本机 `data/interface_settings.json`。赛道指南与车型图鉴随菜单语言切换，赛事记录、配置值和文件名不因语言切换而改变。


图像与数据页可选择 ZIP / 7z 导出，并一次导入多个赛事包。当前 v2 清单不保存或核对内容哈希；重复导入按本机收据与元数据复用，不表示通过完整性认证。路径、大小上限、格式检查与正常解压保留。旧 v1 比赛包仍可读取；新 v2 包直接导入需 v0.2.40 或更新版本。7z 精简工具随便携版包含，不需要额外安装。详见 [无损存储与归档](docs/STORAGE_OPTIMIZATION.md)。

**Archive options:** Export ZIP or 7z session packages. Current v2 manifests do not store or verify content hashes; duplicate handling uses local receipts and metadata, without claiming integrity certification. Path, size, format, and decompression checks remain. Legacy v1 packages are readable; direct v2 import requires v0.2.40 or newer.


LMU v0.2.29：个人赛道纪录新增“官方战绩”，支持只读同步游戏结果 XML 与明确的同组领奖台；训练报告增加可编辑距离区间、实测轨迹 / 距离分段和 ABS/TC 统计；同条件进步分析提供实测圈速与波动曲线。采样与遥测新增接口诊断。详细数据边界见随包使用说明。
