[English](README.md) | 简体中文

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="src/branding/stx-menu.png">
  <img src="src/branding/stx-menu-light.png" alt="STINTRIX 标志" width="220">
</picture>

# LMU Stintrix

面向 **Le Mans Ultimate** 与 **Assetto Corsa EVO** 的本地遥测 HUD 与圈速分析工具。

在控制中心选择 **LMU** 或 **AC EVO**，共用工业风界面、输入 HUD、快捷键、保存与无损归档；两款游戏的赛事、设置与个人纪录分别保存和显示。[适配范围与切换说明](docs/SIMULATORS.md)

驾驶时看清油刹与转向，赛后比较制动、给油与圈速变化，持续记录自己的进步。

[![Release](https://img.shields.io/github/v/release/MarkYang44/LMU-Stintrix?label=release)](https://github.com/MarkYang44/LMU-Stintrix/releases/latest)
![Windows x64](https://img.shields.io/badge/platform-Windows%20x64-0078D4)
[![MIT License](https://img.shields.io/badge/license-MIT-668B28)](LICENSE)

**[下载 Windows x64 版](https://github.com/MarkYang44/LMU-Stintrix/releases/latest)** · [快速开始](#快速开始) · [使用文档](#使用文档)

## 项目简介

Stintrix 把实时输入反馈、自动记录和赛后分析放在同一个桌面应用里。查看同一布局的完整圈，比较输入与圈速差异，再结合个人纪录回顾练习效果。

程序直接读取所选游戏的共享内存，不注入 DLL、不修改游戏文件。菜单支持简体中文和 English，可切换深浅主题；记录与报告默认保存在本机。可用分析取决于游戏接口和实际记录的通道。

## 界面预览

以下为 v0.2.43 采集的真实 LMU 程序窗口，使用生成的示例赛事与内置 DEMO，不代表真实驾驶成绩。当前界面已增加游戏选择与后续操作优化；纯净 HUD 采用无语言文字的图形显示。[截图来源与采集说明](docs/screenshots/README.md)。

<table>
  <tr>
    <td width="50%"><strong>控制中心</strong><br><a href="docs/screenshots/zh-CN/control-center.webp"><img src="docs/screenshots/zh-CN/control-center.webp" alt="中文控制中心，包含 HUD 控制与附加遥测选项" width="520"></a></td>
    <td width="50%"><strong>个人最快圈与条件</strong><br><a href="docs/screenshots/zh-CN/personal-best.webp"><img src="docs/screenshots/zh-CN/personal-best.webp" alt="中文个人最快圈详情，展示车型、圈速、赛道与轮胎条件" width="520"></a></td>
  </tr>
  <tr>
    <td><strong>实时输入 HUD</strong><br><a href="docs/screenshots/zh-CN/input-hud.webp"><img src="docs/screenshots/zh-CN/input-hud.webp" alt="DEMO 纯净 HUD，显示油门、刹车、转向曲线及踏板柱形图" width="520"></a></td>
    <td><strong>赛事资料库</strong><br><a href="docs/screenshots/zh-CN/session-library.webp"><img src="docs/screenshots/zh-CN/session-library.webp" alt="中文赛事资料库，包含生成的示例赛事和复盘入口" width="520"></a></td>
  </tr>
</table>

## 核心功能

### 驾驶时，看清输入

- 实时显示油门、刹车与转向曲线：LMU 可切换原始／游戏过滤后输入，EVO 分别保留物理／仪表输入。
- 提供紧凑 HUD、布局保存、静默记录与全局快捷键；LMU 还可按需开启轮胎、燃油、虚拟能量、进站、Stint 与天气面板。

### 赛后，留下可复盘的记录

- 排位／计时赛与正赛自动记录，练习赛录制可按需开启，EVO 同时支持按需记录巡航。
- 无损保存遥测，支持 CSV 导出、赛事搜索与 ZIP / 7z 比赛包。
- 后台报告显示分步状态，失败任务可重试；EVO 在停止采集后处理报告与压缩，减少驾驶期间的后台负载。
- 支持批量更正线上／线下分类，原始赛事保留；赛事菜单提供来源目录、全选与清除选择入口。

### 比较两圈，找到差异

- 选择同一赛道布局的有效完整圈，支持同场或跨场对比。
- LMU 按距离对齐输入、速度和累计时间差，并显示已记录的行驶轨迹；EVO 提供完整输入曲线与游戏整圈时间差，支持缩放、平移和原始样本读数。
- 可直接比较已保存的最快有效圈，EVO 支持同布局 2–6 场，选中 3–6 场时顶部主按钮直接切换为跨场对比；A/B 重开保留上次赛道、赛事和圈号，两款游戏分别记忆，并重新核对当前有效圈。本次运行生成的 EVO 多圈结果可单独重开，保留 A/B 记忆。
- EVO 圈速总览显示有效圈数、最快圈、中位数与波动，支持单圈查看、A/B 及 3–6 圈叠加。多选可即时查看所选可用圈的均速、最快／最慢与波动，未作条件校正。混合选择可一键“保留所选可用圈”，再继续对比或导出。可批量导出最多六圈完整遥测 CSV，或按当前筛选、排序导出圈速清单。个人纪录／履历可直达，双击或 Enter 操作所选圈；按需节奏图定位来源圈，连续圈段可预览并选择最快 3／5 圈，遇缺圈及采样断开即中断。

### 给下一次练习一个重点

- LMU 可根据已记录圈生成训练优先级，保存本次训练目标。
- 结合车型、燃油、轮胎、天气及已知条件，观察练习进步。

### 持续积累个人纪录

- 两款游戏均支持个人最快圈与纪录履历：LMU 按布局／车辆组别区分，EVO 按布局／具体车型区分。
- 生成圈速单、赛事日志与个人战绩卡；LMU 另支持已确认的同组领奖台和游戏结果 XML 只读关联。
- EVO 车型图库支持品牌／类别筛选与双车并排比较，保留已选车型和浏览位置；赛道卡展示已核实布局与可用官方线路图，图片可按需下载到本机。

### 从视频回看油刹 · 实验功能

- LMU 模式下，对本地视频手动标定后提取估算油刹曲线，并可与历史圈作条件受限的对比。
- 结果与原生纪录分开保存，需要本机 FFmpeg；详见[视频分析](docs/VIDEO_ANALYSIS.md)。

## 下载安装

1. 从[最新 Release](https://github.com/MarkYang44/LMU-Stintrix/releases/latest) 下载 `LMU-Stintrix-v*-windows-x64.zip` 附件。
2. 将整个压缩包解压到可写文件夹。
3. 双击 **`LMU-Stintrix.exe`**。

无需安装 Python。请保留 EXE 旁的 `_internal`，移动程序时一起移动整个文件夹；更新时保留自己的 `data/` 和设置。

<details>
<summary>从源码运行</summary>

通过 **Code → Download ZIP** 下载源码，或克隆仓库。解压后先运行 `Setup.cmd`，再运行 `Start.cmd`。

源码环境使用带 Tcl/Tk 的 **Python 3.13 x64**。配置脚本可通过 winget 安装 Python，并准备固定依赖版本的本地环境；首次配置需要联网。配置与故障排查见[使用说明](docs/USAGE.md)。

</details>

## 快速开始

1. 打开 Stintrix，在左上角选择 **LMU** 或 **AC EVO**；LMU 需在游戏中开启 **Settings → Gameplay → Enable Plugins**。
2. 点击**启动记录**；顶部 **EN / 中文** 可切换菜单语言。
3. 使用窗口或无边框窗口模式进入赛道。
4. 驾驶排位／计时赛或正赛，收到支持的驾驶数据后自动录制。练习赛默认不记录，可在**采样与遥测**中开启。
5. 结束后进入**赛事复盘**，查看记录或选择完整圈进行对比。

点击**停止并保存**会隐藏 HUD，并在后台完整保存。切换游戏时会正常关闭当前 HUD，等待待处理任务完成后打开所选模式。想先体验 LMU 界面，可使用**演示模式**或 `Demo.cmd`，无需连接游戏。

## 兼容性与数据来源

- **目标平台：**Windows 10 / 11 x64；构建与验证环境为 Windows x64、Python 3.13，运行游戏还需满足对应游戏自身的系统要求。
- **LMU 实时数据：**通过随附的 [pyLMUSharedMemory SDK](THIRD_PARTY_NOTICES.md#pylmusharedmemory) 读取原生 `LMU_Data` 共享内存。
- **EVO 实时数据：**只读连接 `Local\acevo_pmf_*` 共享内存，物理与仪表输入分别保留；接口缺少的时钟、条件和成绩留空。
- **历史数据：**两款游戏分别保存 Stintrix 记录与赛事包；原生 `.duckdb`、游戏结果 XML 导入属于 LMU 功能，另一游戏的赛事包需切换模式后导入。
- **字段与显示：**可用通道取决于游戏 / SDK 版本和记录来源；位置回放需要已记录坐标。独占全屏可能遮住桌面 HUD。

EVO 个人纪录与 A/B 对比只使用已观测到完整有效边界、带游戏计时的圈；缺少证据的旧记录仍可读取，不自动补造成有效圈。**更多操作 → 完整记录管理**可按布局搜索、整理备注、管理赛事包并选择有效圈。报告任务可直接定位所选赛事，并保留报告列表原筛选。EVO 支持最快圈及 A/B 指定有效圈 CSV 直出，完整字段与采样保留。条件训练、实时参考圈、官方成绩与附加车辆面板仍属于 LMU 功能。详见[适配范围](docs/SIMULATORS.md)。

圈速单和赛事日志可使用内置兼容生成器；个人战绩卡使用所选游戏的标识和匹配图片，EVO 展示已有圈记录信息，避免套用缺失的 LMU 条件。复用 RaceCom 原版引擎需自行在本机配置，发布包不附带该第三方引擎。EVO 图片按需从游戏或赛道运营方官方来源下载，不随源码或发行包分发。详见[素材与来源声明](THIRD_PARTY_NOTICES.md#evo-official-artwork-and-svg-rendering)。

## 项目状态

项目持续开发中。EVO 已验证合成共享内存、保存往返与界面工作流，安装版本的实机驾驶验收仍待完成。视频提取仍为实验功能，输出属于估算。改动见[发布说明](docs/RELEASE_NOTES.md)，已打包版本见 [Releases](https://github.com/MarkYang44/LMU-Stintrix/releases)。

## 数据与隐私

遥测保存在自己的电脑上，报告在本地生成，没有自动上传遥测的行为。导出文件可能包含车手姓名与日期，分享前请自行检查。详见[隐私与迁移](docs/PRIVACY.md)。

## 使用文档

详细文档目前以中文为主。

| 文档 | 内容 |
| --- | --- |
| [使用说明](docs/USAGE.md) | HUD 操作、录制、复盘与故障排查 |
| [LMU 与 AC EVO](docs/SIMULATORS.md) | 游戏切换、适配范围、数据隔离与 EVO 配置 |
| [架构说明](docs/ARCHITECTURE.md) | 模块职责与开发边界 |
| [性能说明](docs/PERFORMANCE.md) | 实测数据、测试场景与取舍 |
| [无损存储](docs/STORAGE_OPTIMIZATION.md) | 存储格式、CSV 恢复与赛事归档 |
| [数据处理](docs/DATA_PROCESSING.md) | 分析流程、训练复用、实测耗时与精度保护 |
| [视频分析](docs/VIDEO_ANALYSIS.md) | 标定、工具要求、对比方式与精度边界 |
| [隐私说明](docs/PRIVACY.md) | 本地数据、分享与迁移 |

## 开发

使用带 Tcl/Tk 的 **Windows x64 / Python 3.13** 环境，在已配置的源码目录运行：

```powershell
.\Setup.cmd -BuildTools
.venv\Scripts\python.exe tools/run_tests.py
.venv\Scripts\python.exe tools/build.py --no-checksums
```

维护与验证流程见[架构说明](docs/ARCHITECTURE.md)和[发布流程](docs/RELEASE.md)。

日常验证默认只选少量基础检查及本次改动相关用例；`--plan` 查看范围，`--tests <用例>` 精确指定，`--full` 才运行完整历史测试。详见[测试策略](docs/TESTING.md)。仅在准备发布时构建便携 ZIP。

## 许可证与致谢

项目采用 [MIT 许可证](LICENSE)，第三方代码与素材归属见[第三方声明](THIRD_PARTY_NOTICES.md)。

LMU Stintrix 是独立社区项目，与 Studio 397、Motorsport Games、KUNOS Simulazioni、505 Games 无隶属或官方背书关系。Le Mans Ultimate、Assetto Corsa EVO 及文中其他名称的权利归各自所有者。
