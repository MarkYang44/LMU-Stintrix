# 维护与发布

在 Windows x64 上使用 CPython 3.13。默认构建不读取任何旧插件目录，资产按固定清单加入 EXE；每次使用新的暂存目录，现有记录和旧构建不会被清除。

1. 修改 VERSION 与应用版本，固定需要更新的依赖版本，执行 `tools/Build.cmd`。当前 CI 使用 `tools/build.py --no-checksums`，生成便携 ZIP 与文件大小清单。
2. 只验证本次改动：先用 `tools/run_tests.py --plan` 查看范围，再执行默认相关检查，或用 `--tests` 指定少量直接相关的方法。测试只生成合成记录，每条用例独立进程。完整历史回归仅为 `--full` 手动选项，参见 [测试策略](TESTING.md)。
3. 执行 `.venv\Scripts\python.exe tools/check_bundle.py --smoke --no-checksums`：按构建清单核对文件与大小，确认 ZIP 与 EXE 不带开发测试代码，然后以独立私有目录启动实际发布 EXE 的 DEMO，正常关闭后检查完整圈、离线报告及比赛包导入导出。测试代码与结果留在 `tests/` 和 `_local/`，不植入发布 EXE。
4. 使用明确文件清单暂存源码，然后执行 `.venv\Scripts\python.exe tools/audit_publication.py`。检查 `git diff --cached --stat`。不要暂存 dist 或任何个人记录。
5. 正常提交后运行 `tools/Publish.cmd`；它检查远程 URL、main 分支、已提交状态与隐私规则，再进行普通推送。Git 的浏览器登录由维护者本人完成。`tools/Publish.cmd -CheckOnly` 只检查、不上传。main/PR 的 CI 默认只做源码审查与改动相关检查；不再为普通推送重复构建整包。
6. 推送与 VERSION 一致的 `v*` 标签。标签会按上一版本以来的改动选择相关检查，执行隐私审查、构建及独立便携版验证；通过后，工作流自动发布附带便携 ZIP 的公开 Release。当前流水线不生成独立 SHA256 附件。只推送 main 不再生成整包，也不创建 Release。推送标签前应完成上述本地检查。

ZIP 内包括独立解释器、Tk、DuckDB、离线模板、许可证及 build-manifest.json，不要求用户安装 RaceCom 或 Python。GitHub 的源码 Download ZIP 不包含二进制，但 Setup.cmd 可一次配置并启动。

源码与输出分离的改动限于路径、SDK / DuckDB 依赖及发行脚本；公开版无授权不明的预置底图库。车轮盘体为程序绘制的示意图。新增静态素材前必须确认可再分发许可。

如果 Git checkout 由沙箱账号创建、发布由普通 Windows 账号执行，发布脚本和隐私审计会在每次 Git 调用中仅信任当前项目的确切路径。无需更改文件所有权，也不写全局 `safe.directory` 配置；Git 读取失败会单独报错，不会误报成远程地址不符。
