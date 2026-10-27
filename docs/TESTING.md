# 按改动验证

开发以功能和使用体验为主，测试只验证本次修改及直接关联的风险。不要在每轮界面优化后重跑全部历史用例，也不要为低风险改动堆叠重复测试。

- 默认入口：六项基础检查，加上待提交改动对应的常见功能检查。纯文档改动不启动运行测试。
- 精确检查：排版、文案、单个交互通常选少量直接相关用例；使用 `--tests` 指定方法，避免为一个小改动执行整份历史 UI 测试文件。
- 基础检查覆盖版本入口、隐私边界、数据精度、完整保存和纪录筛选。存储、采样、导入导出等模块发生修改时，再补充该功能的相关检查。
- 同一用例 ID 只执行一次。GUI 用例仍独立进程、串行运行，避免 Tk 状态和焦点互相干扰。
- 完整历史测试保留为 `--full` 手动选项，不是普通优化或每次发布的默认前提。同一份已经通过的改动不重复验证，只有新修改、失败或明确未覆盖的风险才补测。

```powershell
# 先看本次选择，不执行测试
.venv\Scripts\python.exe tools/run_tests.py --plan
# 默认：基础检查 + 本地待提交改动相关检查
.venv\Scripts\python.exe tools/run_tests.py
# 只验证特定交互（--modules 同样接受模块、类和方法）
.venv\Scripts\python.exe tools/run_tests.py --tests tests.test_ui_polish74.UI.test_stop_hides_main_and_all_five_addons_before_reports_finish
# 查看 HUD 停止相关范围
.venv\Scripts\python.exe tools/run_tests.py --paths src/hud_shutdown.py --plan
# 检查已提交改动；CI 使用推送前的提交或 PR 基线
.venv\Scripts\python.exe tools/run_tests.py --base HEAD^ --plan
# 仅在确有必要时手动执行完整历史回归
.venv\Scripts\python.exe tools/run_tests.py --full
```

自动范围是常见功能映射，不代表完整依赖分析。新增功能或未映射的模块应使用 `--tests` 补选实际相关用例，不能把“只通过基础检查”说成整项功能已验证。修改测试方法时只选择被修改的方法；修改共享测试夹具时保守选择其所在模块。

GitHub Actions 的 main/PR 默认按改动选择测试，不再重复构建整包；版本标签和手动构建保留发布包及实际 EXE 检查。完整回归仅在手动启动工作流时明确选中。标签按上一个已发布正式 Release 的改动范围选择相关检查，未发布成功的标签不作为缩小范围的依据。
