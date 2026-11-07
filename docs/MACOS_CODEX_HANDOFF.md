# MacBook 实机验收 Prompt

将下面内容交给 MacBook 上的 Codex。用户提供的真实赛事文件夹／比赛包应另行复制到 Mac；公开仓库和 Release 不含个人赛事数据。

```text
请接手 LMU-Stintrix v0.4.0 的 MacBook 实机验收，发现问题后直接修复并验证。
仓库：https://github.com/MarkYang44/LMU-Stintrix
Release：https://github.com/MarkYang44/LMU-Stintrix/releases/tag/v0.4.0

定位：Windows 保留实时遥测、HUD 和完整分析；macOS 为纯离线分析。两端共用数据格式和分析代码，LMU／AC EVO 资料库严格隔离。Mac 版支持 Apple Silicon、最低 macOS 13，目前只经过 macOS 15 云端原生构建和合成数据验证，还需要真实 MacBook 的图形界面、触控板和真实记录验收。

先读取当前 AGENTS.md、docs/MACOS.md、docs/TESTING.md、docs/RELEASE_NOTES.md、docs/MACOS_CODEX_HANDOFF.md。克隆源码并核对 v0.4.0 标签；修复请新建 codex/macbook-verify 分支，不覆盖已有工作。先验证下载的正式 DMG/ZIP 与同一 Release 的 SHA256SUMS.txt，再测试实际发行 .app，不要只运行源码或命令行就宣布通过。

请按重要性执行：
1. 记录 Mac 型号、芯片、macOS 版本。通过 Finder 打开 DMG、拖入 Applications、首次启动、退出和重开，检查 Dock 图标、窗口、Retina 清晰度、应用迁移后资源路径。记录 Gatekeeper 的真实提示；当前为临时签名、未公证，不要关闭 Gatekeeper 或全局清除隔离属性。系统安全确认需要我处理时再说明。
2. 在独立测试数据目录完成后续操作，先备份任何已有设置/资料库。使用用户提供的 Windows 记录副本，分别验收 LMU 和 AC EVO 的文件夹、ZIP、7z 导入；有样本时检查 DuckDB 与 .csv.stc。核对原始字节、采样数、精度、UTC、有效圈规则、赛道布局和 No BOP 分组，确认两款游戏互不可见且错误游戏导入被拒绝。缺少某种样本就明确标为未验证，不要编造结果或改写源文件。
3. 真正操作界面：赛事筛选/备注/收藏、历史和个人纪录、完整圈曲线、圈 A/B 与跨场对比、HTML 可视化、圈速单/赛事日志/成绩卡、后台任务、导出和无损压缩/还原；检查 Finder 打开路径及浏览器打开报告。有视频和 FFmpeg 时再检查可选视频分析与 Apple Vision OCR；正常分析不应启动 OCR 或游戏连接。
4. 检查深浅主题、中英界面、页面切换、窗口缩放、触控板纵横滚动、Command/F1 快捷键、中文字体、长文本和图片；Mac 不应出现采集、HUD、游戏连接或全局游戏快捷键入口。后台任务中退出与 Command+Q 应走现有保存/退出保护。保存截图、错误日志，记录空闲内存和代表性导入/对比耗时，别凭主观估计报性能数值。
5. 修复只改平台边界或共享模块中的必要部分，不维护第二套分析引擎，不改变 Windows 默认行为、游戏判圈规则和完整数据精度。运行本次修改直接相关检查，先 --plan，不默认 --full，不重复跑已通过且代码未变的历史用例。修改后重建 .app/DMG，验证实际新包及重开后的状态持久化；GUI 检查串行执行。无法自动操作的环节明确列出人工步骤，不将无图形界面的检查称为实机 UI 验证。

无需逐项确认；自主完成授权范围内的安装、检查和修复。不要删除或迁移个人原始记录，不自动上传任何个人数据、日志、截图或含个人信息的报告；不要擅自发布新 Release 或覆盖远端主分支。最后用中文给出实际验证范围、发现及修复、证据路径、新包路径、未验证项目与剩余风险。若需要我验证某一步，只给出最少且可执行的步骤。
```
