# LMU 与 AC EVO

控制中心左上角的游戏选项可选择 Le Mans Ultimate 或 Assetto Corsa EVO。切换会走正常退出流程：停止 HUD，保存输入，等待后台任务完成，再重新打开所选游戏的控制中心。未保存草稿仍使用现有的保存／放弃／继续编辑流程。重开后点击“启动记录”。

选择框和下拉选项会读取本机游戏图标；未找到安装文件时使用带名称的徽标。图标只在本机读取，不打包游戏素材，不修改游戏文件。

## 数据范围

v0.3.40 在 EVO 圈速总览增加上下文操作“保留所选可用圈”，仅当当前选择同时含有可用和不可用圈时显示。点击只取消其中不可用圈的勾选，不替换为其他最快圈；保留筛选、排序和合法滚动位置，再由用户选择查看曲线、对比或导出。节奏图模式不切换；加载期间禁用，不自动开始后台任务，不修改原始记录。

v0.3.39 在 EVO 圈速总览的操作区增加即时选中圈统计。显示已选／可用数量，仅对其中符合现有导出证据的完整有效圈计算平均圈速、最快、最慢与总体标准差；单个可用圈的波动显示“—”，不将无效、未知、进站或部分圈补为成绩。筛选、刷新及主题语言切换保持一致，无数据／读取失败会清除过期统计。统计只读取已加载圈清单；同一选择的数值复用，不额外扫描遥测，不作条件校正或驾驶归因，原始 CSV 和成绩不改写。

v0.3.38 在 EVO 圈速总览增加“导出圈速清单”。按点击时的当前筛选和排序，导出所有显示行的赛道、布局、车型、日期、原始圈号／圈速、距本场最快的原值、可用性、完整／部分／有效／进站标记、采样数及计时来源，不受整圈遥测导出六圈上限影响。UTF-8 BOM CSV 保留原始浮点表示与缺失空单元；无效／部分圈不会被提升为有效圈。输出新文件，不覆盖旧导出，发布前后检查来源；不重读原始采样、重建圈索引或生成图片。完整遥测 CSV 仍使用原按钮与规则。

v0.3.37 在 EVO 赛事页与完整记录管理的“最近对比”中加入“打开上次多圈对比”。本次应用运行中，同场 3–6 圈叠加和跨场 3–6 场最快圈结果共用一个按当前游戏目录隔离的最近结果，内存只保存页面路径及圈数；不覆盖 A/B 记忆。重开明确使用已有页面，不扫描遥测或重新生成，不代表按新来源重新分析；文件移走或路径不属于当前 EVO 多圈输出目录时禁用。游戏切换重开应用后不自动恢复该运行内记忆。

v0.3.36 将 EVO 跨场最快圈入口扩展到同布局 2–6 场。主列表多选 3–6 场时，顶部主按钮直接比较各场已保存的最快有效圈；选择 0–2 场仍打开原 A/B 选择器，更多操作可直接比较 2–6 场。完整记录管理提供同一跨场入口。共用已有完整曲线／CSV、逐对布局核验与页面缓存；点击时固定赛事及圈号，之后改变选择不替换已接受的任务，缺少最快有效圈或超过六场不截断。两场继续保存原 A/B 结果记忆，3–6 场独立生成多圈页，不覆盖双圈上下文。采集互斥、成功／失败释放和关闭窗口后已接受的任务均沿用后台机制。

v0.3.35 在 EVO 圈速总览增加“连续圈段”：从当前筛选的可用圈清单中选择最快连续 3／5 圈，菜单显示确切圈号及平均游戏圈速；缺圈、无效、进站、未知有效性或原始采样范围不相邻均断开。共用已有叠加／CSV 操作，从节奏图选择时返回列表并显示所选圈；保留筛选、排序和原始数据，不作条件校正或驾驶归因。选择只处理现有小型圈清单。

v0.3.34 在 EVO 圈速总览增加“圈速节奏”，与列表切换并共用空间。只使用当前筛选中的完整有效圈，按原始圈号显示游戏圈速，间断不连线；悬停看读数，点击返回列表并选中来源圈。默认不创建图、不重扫遥测，也不作条件或驾驶归因。

v0.3.33 在 EVO 圈速总览支持双击有效圈和 Enter 主操作：一圈查看、两圈进入 A/B、3–6 圈叠加。保留原筛选与选择，不可用或超过六圈时不自动替换；首次提取共用原字段 CSV 与七通道数值读取，完整采样、精度和源校验保留。

v0.3.32 在 EVO 个人最快圈的更多操作及纪录履历操作区加入“圈速总览与节奏”，直接查看来源赛事，保留原列表和总览筛选。LMU／EVO 个人完整圈页面按数据、资源内容及独立修订复用，纯界面升级不再重复处理整圈；首次旧格式升级可能重建一次，旧结果保留。报告车图补齐明确的 Ferrari 296 Evo／No BOP 别名，完整车型名称和纪录分组保持独立。

v0.3.31 将 EVO 圈速总览的所选有效圈 CSV 导出扩展到 1–6 圈，可与“选择最快多圈”连续使用。批量任务显示 A–F 标签，点击时固定圈号，支持当前项完成后停止、继续剩余项及仅重试失败项。同场复用受大小限制的索引／元数据／表头，相邻圈复用同一顺序读取器，完成或停止后关闭。普通 CSV 的完整简单行直接写出等价的规范 CSV 文本；复杂、稀疏、重复表头和列式来源保留原解析规则。每圈仍独立核对样本数及来源，唯一命名，原有导出不覆盖。

v0.3.29 在 EVO 圈速总览中开放同场 3–6 圈完整输入叠加，选择两圈仍进入已有 A/B 选择器；“选择最快多圈”会选取当前筛选中最多六个可用圈。后台逐对核对赛道、布局和可靠长度，保留游戏计时、全部样本、原始字段 CSV、来源检查和采集互斥；超过六圈或混入不可用圈时不自动截断或替换。新页面用 A–F 标签与六组深浅主题颜色显示输入和原始样本读数，窄窗口按单列排列。车速上限在初次校验时计算，缩放、平移与通道切换不再为刻度重复扫描整圈；不降采样、不补造分段或条件分析。

v0.3.28 在 EVO 圈速总览中增加“打开所选圈曲线”，可查看任意已验证的完整有效圈，并与 A/B 共享原格式的完整 JSON／原始字段 CSV；页面命中时无需重读整圈矩阵。增加“选择最快两圈”，只选择当前筛选中的可用圈。圈速与“距最快”按原始数值排序，刷新／主题／语言切换保留排序和可用选择，源清单重排时按圈号及采样范围重新匹配；缺失圈不自动替换成其他圈。后台准备曲线期间阻止启动采集，无论总览是否仍打开，任务完成或失败都会释放占用。

v0.3.27 在 EVO 赛事的“更多操作”及完整记录管理中增加“圈速总览与节奏”。后台读取已有圈索引，显示完整有效圈数、最快圈、中位数与圈速标准差；只统计与选圈导出相同的可用圈，不推算首尾残圈、缺失游戏计时或未知有效性。标准差未做油量、轮胎、天气等条件校正，不视为驾驶归因。按圈号／状态搜索，筛选完整有效圈或待检查圈后，可导出 1–2 个所选圈 CSV，或将两个确切圈号直接带入共用 A/B 窗口。窗口复用及刷新保留筛选和可用选择，失败清除过期统计并禁用操作；两款游戏的目录及证据边界保持独立。

v0.3.26 在 EVO 车型图库复用 LMU 的选车比较交互：可跨品牌筛选或分页选择两台车，通过可移除标签管理选择，再并排查看本机已缓存的确切车型官方图片、品牌与组别。小窗口自动纵排；返回保留筛选与滚动位置，切页、主题和语言切换保留当前进程内的选择。图库与布局详情中的 Ctrl+F 可直接返回搜索。没有本机图片时显示缺失提示，比较不扫描赛事或自动联网；未加入缺少依据的性能评分和驾驶归因。

v0.3.25 在 EVO 的 A/B 选圈窗口加入“导出 A / B 圈 CSV”：使用当前 A、B 各自的赛事与有效圈号，可导出非最快圈，不再先生成对比页。点击时固定两圈身份，批量任务分别显示 A／B 与圈号；后续修改选择不改变已接受任务，选择与上次对比结果仍保留。复用上一版的完整字段导出、来源校验、唯一命名、失败重试及采集互斥。LMU 原有选圈与对比入口不变。

v0.3.24 将 LMU 已有的最快圈 CSV 工作流接入 EVO：在赛事菜单或完整记录管理中选择“导出最快圈 CSV（可多选）”，再选输出目录。每场只导出已验证的最快完整有效圈，保留全部采样与字段字符串，沿用选圈导出的重复表头／缺失字段规则；普通和列式来源均可用。只读必要范围，不额外生成 JSON、曲线或网页，浏览列表时不会自动生成。使用现有批量进度、失败重试和唯一输出文件名；任务及重试运行期间阻止开始采集，记录运行中也不能启动此导出。输出保存在用户选择的目录，两款游戏的赛事仍严格隔离。

v0.3.23 补齐 EVO 个人战绩卡适配：读取当前游戏缓存中的官方标识和确切车型图片；缺少图片时用完整游戏名／车型名，不借用 LMU 素材。信息栏使用参赛方式、计时来源、完整采样数和赛道长度，未知字段保留未知；不补造轮胎、油量或天气条件。不重复显示用于车型隔离的内部未知组别标签。两款游戏的个人卡只读取所需条件元数据，不再生成未使用的缩略曲线；领奖台卡的独立数据路径保留。

v0.3.22 在 EVO 赛事菜单增加“报告任务与分步重试”，完整记录管理和共用数据页也会带入所选赛事。报告列表保留原搜索与筛选，临时显示目标，处理后可返回原选择／位置；主动修改筛选会取消定位。重试仍只处理 EVO 自己的四步报告，保留已成功步骤，浏览和定位不触发原始遥测扫描。

v0.3.21 将 LMU 的完整记录管理入口接入 EVO 的赛事菜单。窗口只加载当前游戏目录，支持布局列与搜索、赛道／车辆／参赛方式筛选、备注标签、参赛方式更正、赛事包导入导出、压缩备份及批量进度。选中 1–2 场可打开共用 A/B 有效圈选择器；同场对比也使用 EVO 的边界与计时校验。窗口复用与重开保留当前进程中的筛选、选择、列宽和位置。稳定参考圈、LMU 完整分析和 LMU 中断重建按能力隐藏并在业务入口拦截；不会生成虚构分析结果。

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

v0.3.19 在赛事“更多操作”复用 LMU 的批量参赛方式更正，默认只改未知记录，可撤销人工更正恢复自动识别；分类写入 EVO 自己的覆盖文件，原始赛事和采样不重写。增加直接打开赛事目录、全选及清除选择，保留主题／语言切换与刷新后的浏览上下文。更正及目录入口再次核验当前游戏归属。完整圈 JSON 与原始字段 CSV 同次读取、同次校验来源，不减少字段或样本；来源变化或转换失败保留原导出。

v0.3.20 复用 LMU 的跨场最快圈快捷入口：勾选两场已有最快有效圈的同布局赛事，在“更多操作 → 跨场最快圈对比”直接生成。A/B 窗口按游戏目录记住赛道、搜索、赛事、有效圈及上次生成页，主题／语言切换或关闭后重开可继续；换入不同赛事时使用新的上下文。旧圈号失效会要求重选，每次仍核对当前有效清单。界面记忆仅存目录、圈号和页面路径，不常驻完整采样或混合两款游戏的数据。

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

The shared full record manager is available from **More actions → Manage Recordings**. It includes layout search, notes, participation corrections, archives, lossless backups and batch progress. One or two selected sessions open the existing verified-lap selector. Browsing context stays within the current simulator; LMU-only reference, analysis and reconstruction actions are hidden and guarded.

Report recovery can open directly on selected sessions from the EVO session menu, full record manager or shared data browser. Targets appear temporarily without clearing report filters; return restores the previous selection and scroll position. Changing the search or source ends temporary location. Retry keeps successful steps and uses EVO's existing four-step policy.

EVO personal achievement cards use the official logo and exact model artwork already cached for that simulator, with full names as fallbacks. The fact tiles show recorded participation mode, timing source, sample count and track length. Missing LMU conditions remain unavailable. Both games' personal cards read only the required metadata rather than constructing an unused curve; podium-card loading remains separate.

EVO's session menu and full record manager can export the fastest verified complete lap directly to CSV, including multiple selected sessions. This reuses batch progress and failed-item retries, keeps original field strings and every selected sample, and supports ordinary or packed sources. No unused curve, JSON or page is generated. Capture and this task, including retries, are mutually exclusive; each output gets a unique filename in the selected folder.

The EVO A/B selector also exports the two selected valid laps directly to CSV, including laps that are not session bests. A and B identities are captured when clicked and labeled in the batch window. Changing the selector afterward does not change the accepted task; selections and the previous comparison page stay available. This uses the same export protections and capture exclusion.
