# LMU 与 AC EVO

控制中心左上角的游戏选项可选择 Le Mans Ultimate 或 Assetto Corsa EVO。切换会走正常退出流程：停止 HUD，保存输入，等待后台任务完成，再重新打开所选游戏的控制中心。未保存草稿仍使用现有的保存／放弃／继续编辑流程。重开后点击“启动记录”。

选择框和下拉选项会读取本机游戏图标；未找到安装文件时使用带名称的徽标。图标只在本机读取，不打包游戏素材，不修改游戏文件。

## 数据范围

v0.3.13 的 `simulator_profiles.py` 是游戏名称、读取器工厂、时钟／输入语义、能力和报告策略的共同定义。档案不可变且导入时不加载 Tk 或游戏 SDK；最小 `InputReader` 仅要求 `read()`／`close()`，接口诊断保持可选。EVO 不继承不存在的 LMU 通道或分析能力。采集循环只访问已选择的能力标志。

报告任务共用 `report_pipeline.py`，各游戏提供自己的操作集合。LMU 保持分析／耐力／复盘等依赖，EVO 仍可独立生成部分报告；两者共用原状态文件、延期、成功复用及重试备份机制，不合并游戏数据或补造缺失信息。

- LMU 继续使用原来的数据目录，不搬迁历史记录。
- AC EVO 使用数据目录下的 `Simulators/ac_evo/`，记录、备注、最近赛事、缓存、配置均独立。
- 每次只展示当前游戏的数据。未带游戏标记的旧记录属于 LMU。导入赛事包会在发布文件前检查来源；另一款游戏的包需先切换再导入。
- 第一次进入 EVO 只复制界面、输入采样、HUD 布局、快捷键和存储偏好，已有配置不覆盖；不复制赛事或缓存。

## EVO 已适配范围

已接入现有工业风界面、输入曲线／踏板／方向盘 HUD、布局、静默模式、快捷键、停止并保存、无损列式存储、ZIP／7z 赛事包和后台任务。EVO 记录页可打开输入记录概览、写备注、导出原始 CSV、压缩或归档。

v0.3.10 开放具体布局列、圈速单、赛事日志、个人赛道最快圈、完整物理／仪表输入曲线，以及官方车型／赛道图片浏览。个人纪录按赛道、布局、长度、具体车型区分；未提供性能组别的街车不会互相覆盖最快圈。

圈速单和日志复用本机 LMU 已配置的 RaceCom 原版引擎，EVO 在自己的数据目录准备独立标识、配置和车型图片，不覆盖 LMU 素材。未安装 RaceCom 时可在 EVO 图像与数据页选择内置兼容生成器；第三方生成器不随公开包分发。

v0.3.14 开放“赛道 → 赛事 → 有效圈”的 A／B 对比，同场／跨场均可；个人纪录的更多操作可直接带入来源赛事。共用选择器、完整采样提取、无损存储读取和来源缓存，EVO 网页独立保留物理／仪表输入与重复游戏计时。支持缩放、平移、最近原始样本读数和整圈时间差，不插值补造圈边界或生成缺少条件依据的驾驶归因。首次选中时才扫描旧赛事，已生成组合及单圈可复用。

v0.3.15 接入纪录履历与成绩提升曲线。仅按真实有效 PB 的日期排序，布局、具体车型及参赛方式隔离，导入副本和冲突记录沿用 LMU 的去重规则；不是同条件因果分析。履历可直接打开圈曲线、战绩卡、来源目录或 A/B 选择器，切换页面／主题／语言保留浏览上下文。新生成的单圈页面使用与 EVO A/B 一致的完整采样查看器；历史原报告不批量重写。最速圈和履历的同一曲线按来源与素材凭据复用，之前导出的页面保留。

v0.3.16 在“图像与数据 → 报告与存储”开放报告任务和缓存／导出占用查看，复用 LMU 的分步重试、批量进度和文件保护。EVO 按 fastest／review／images／compression 四步处理，不套用 LMU 的分析／耐力依赖。切换赛事包和存储只移动同一列表，选择及筛选保留，存储偏好保存失败可回退并重试。官方原生导入、完整复盘导出和视频关联功能仍按能力关闭。

赛事页的更多操作复用收藏／标签、复制单元格／选中行、列视图、导入／导出；删除仍有独立入口及原确认。暂未开放 LMU DuckDB／官方成绩导入、训练条件匹配、实时参考差值及附加车辆分析面板。EVO 没有收集的分段、碰撞、组别及确认完赛成绩留空；观测名次不冒充官方成绩。

### 圈速证据与旧记录

新增保留 SDK `last_laptime_ms`、`best_laptime_ms`、当前名次和车辆数。只将两个已观测完圈边界之间、游戏标记有效、无进站、时间／距离连续且覆盖足够赛道的完整圈计入 PB。圈速使用游戏毫秒字段，不使用本机采集时长估算；跳圈、计时重置、回站、明显缺口和部分首尾圈不参与最快圈统计。

v0.3.9 及以前的输入记录缺少完圈毫秒字段，仍可生成赛事日志与输入记录概览；观测到的当前圈计时保留为部分记录，不自动补造成有效圈。原始 CSV、缺失值与旧记录字节不修改。完整圈曲线复用 SVG 绘图，但保留 EVO 游戏计时重复值和原距离，不套用 LMU 的边界插值。

### 官方图片

图片来源为 [KUNOS / 505 Games 官方 EVO 页面](https://assettocorsa.gg/assetto-corsa-evo/)，当前登记 74 个车型及 20 个赛道条目，另有 Touristenfahrten 专用图，共 95 张。`src/evo_art_sources.json` 仅保存来源 URL，图片下载到当前 EVO 私有目录 `assets/evo/`；不打包或重新分发官方素材。下载凭据保存来源与 SHA-256。

图库按页最多 12 项，只有可见图片解码，移出视口释放。点击“下载 / 更新官方图片”才连接网络，下载后当前图库自动刷新。采集／HUD 正在运行时不启动下载或缺失圈索引处理，派生报告仍在停止记录后低优先级执行。未知具体型号不会借用同品牌其他车图。

v0.3.11 增加 26 品牌与 7 类车型的组合筛选，分类用于图片浏览，不写入遥测的性能组别。赛道卡可点击或按 Enter 打开布局详情。v0.3.12 将布局目录与图片目录分开，20 个赛道条目列出 36 种已核实布局，补上 Brands Hatch GP／Indy、COTA GP／National、Donington GP／National、Fuji GP／GP Short、Red Bull Ring GP／National、Suzuka GP／East／West。布局依据官方版本公告和官方赛事平台记录；每个新增项保留具体来源。详情内可直接切换赛道，左右键切换布局，分别记住各赛道的选择；返回列表保留搜索、分页和位置。

线路图包括 29 份 KUNOS 原始 SVG 与对应 PNG，以及赛道运营方 MSV 提供的 Brands Hatch Indy／Donington National 图，共 31 套。另 5 种布局没有收录对应官方图，仍列出按钮及资料来源，界面明确提示缺图；不套用 GP 线路。加上完整官方 EVO 标识与原有 95 张照片，共 127 项可下载资源。只在明确下载时加载 SVG 转换库；驾驶采集不导入它。向量保留几何、透明度与布局深浅层次，仅对中性线条适配深浅主题，MSV 彩色图保持原色。来源见 [Brands Hatch](https://www.brandshatch.co.uk/about/circuit-layouts) 和 [Donington Park](https://www.donington-park.co.uk/about/circuit-layouts)。

EVO 日志使用完整官方游戏标识；报告用深色字标适配浅色纸面，原始官方向量与旧版报告标识均保留。赛事记录顶部和右键菜单提供“删除选中记录”，个人纪录的“更多操作”提供“删除来源赛事”。两处均复用既有确认、活动记录／后台任务保护与路径检查；确认窗口明确删除整场来源赛事，避免派生圈文件被重新生成。增加入口本身不会删除任何已有记录。

## EVO 运行负载

输入采样与 HUD 绘制分别设置。新 EVO 配置默认手动 60 Hz HUD，仍继承原输入采样参数；已有配置不自动覆盖。使用 1200 Hz 采样并同步 HUD 会让 CPU Canvas 尝试同样高频绘制，建议保持手动刷新，按屏幕与需求调整 60／120 Hz。显示刷新不会降低 CSV 采集频率或丢弃源数据，显示桶仍保留短促峰值。

隐藏／静默 HUD 暂停绘制，恢复时立即重绘。EVO 不计算未开放的轮胎、燃油及耐力面板，也不轮询其刷新定时器。EVO HUD 运行期间，派生报告和无损压缩保留待处理凭据，停止记录后在低优先级独立进程中继续；原始 CSV、写盘队列和 fsync 检查点照常完成。LMU 的报告时机保持原规则。

这降低插件的运行负载和主进程报告堆驻留，不承诺某个游戏 FPS／1% low 提升比例；实际效果需同场景驾驶对照。合成测量范围见 `DATA_PROCESSING.md`。

## 接口与精度

只通过 `OpenFileMappingW(FILE_MAP_READ)` 打开已存在的三页 `Local\acevo_pmf_*` 共享内存。不创建映射、不写入游戏、不安装游戏插件。

声明依据 Kunos [SharedFileOut v1 文档](https://docs.google.com/document/d/1WzqMLkW2o_C0LGcvdMRelAV31ZIifux0CSHD9k6ddz0/edit)（2026-04-28 增加 car_ids）。每页读取稳定快照，并检查读取期间的包号和静态元数据变化；物理页和仪表页由生产者以不同频率更新，不能保证它们是同一个游戏时刻。

- “物理输入”来自 `gas/brake/steerAngle`，“仪表输入”来自 `gas_percent/brake_percent/steering_percent`；不假定它们等价于 LMU 原始／过滤后通道，不复制或插值伪造通道。
- 使用本机单调采集时钟作为 `time_s`，`session_time_s` 和未经确认的圈起点留空。原生包号、圈计时毫秒、npos、场次编号另列保存。
- 保存已读取的 float32 实际数值提升后的完整表示，不再额外舍入；沿用现有字节可恢复的压缩与归档格式。
- 首次连接先等待物理包号发生更新，避免第三方程序保留的旧映射创建假记录。菜单、回放、暂停、旁观别车及不合法字段不产生驾驶输入记录。原生包号用于抑制重复帧。明确的场次变化／圈数回退分开记录；数据暂停保留当前记录，手动停止可靠收尾。
- 计时赛和正赛自动录制；练习与巡航可在设置中开启。

当前已验证合成原生映射、真实保存／压缩／归档往返和双模式 GUI 生命周期；尚未完成安装版本的实跑验收。游戏更新后的布局、输入方向、暂停／回站／完赛行为仍需以实际驾驶验证，不能将合成映射检查称为实机兼容验收。

## English

Choose the simulator at the top left. Switching saves and closes the current HUD, waits for background work, then reopens the control center. LMU keeps its existing data path; EVO uses `Simulators/ac_evo/`. Records, notes, recent sessions and caches are isolated. Archives from the other simulator are rejected before publishing imported files; untagged legacy records belong to LMU.

Initial EVO support includes the industrial interface, input HUD, shortcuts, layouts, input recording, lossless storage, archives and background tasks. Physics and HUD inputs remain distinct. The timeline uses the host capture clock; unavailable game clocks remain blank. Verified-lap input comparison, exact selected-lap exports, personal records, reports and official galleries are available. Live references, condition-based training, official results and vehicle panels remain unavailable. Synthetic native mappings and storage round trips have been verified; live driving compatibility has not yet been accepted.
