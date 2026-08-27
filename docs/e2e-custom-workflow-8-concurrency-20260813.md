# 自定义 Workflow 与 8 路并发 E2E（2026-08-13）

## 结论

- Config/runtime E2E：通过。
- 8 路真实并发：通过；峰值为 8 个独立 Hermes ACP 进程。
- 最终报告导出：通过，Graph `status=completed`。
- 内容质量门：未通过；FinalReview 为 `VERDICT: revise`，不能把 Graph 完成解释成内容通过。

## 测试对象

- Workflow：`examples/custom-workflow/custom-heavy-8.yaml`
- 自定义 Node：`expand-research-plan`
- Run：`run-e2e-custom-heavy8-heavy-20260813`
- Query：研究 Python 3.14 相比 Python 3.13 在自由线程、子解释器和性能方面的关键变化，并为计划升级的后端团队给出有证据的迁移与风险建议
- 参数：`--mode heavy --max-concurrency 8 --no-node-timeout`

自定义 Script Node 读取正式 `plan.json`，把 Plan 实际生成的 5 个维度规范化为 `d1` 到 `d8`，同时发布 8 个 `research-task` batch Artifact。节点通过 `validators` 先直接执行 Prompt Bundle 的唯一正式 Plan Validator，再执行只检查 8 个任务一一对应关系的节点级 Validator。

## 真实运行结果

| 项目 | 结果 |
| --- | --- |
| Workflow 状态 | `completed` |
| 完成实例 | 60/60 succeeded |
| Artifact | 85 |
| Agent 进程 | 58 个独立 Hermes ACP runtime |
| 第一轮 | Research 8、Review 8、Perspective 8、SupplementPlanner 8 |
| 第二轮 | 按补研 batch 运行 Research 5、Review 5、Perspective 5 |
| 报告阶段 | ReportPlanner 1、ReportWriter 6、Stitcher 1、FinalReview 1、Render 1 |
| 峰值并发 | 8；Research、Review、Perspective、SupplementPlanner 均实际达到 8 |
| Agent 活跃时间并集 | 3703 秒 |
| Agent 累计工作量 | 11199 秒 |
| 并行系数 | 3.02 |
| 模型 API 调用 | 661 |
| 成功工具调用 | 1325 |
| 可恢复工具错误 | 26 |
| Validation warning | 0 |
| 最终报告 | `output/run-e2e-custom-heavy8-heavy-20260813/report.md`，119085 bytes |

时间来自 58 个 Hermes execution-session 日志的首尾时间。活跃时间并集会去除并发重叠；累计工作量是各 Agent 区间之和；并行系数为累计工作量除以活跃时间。

## 阶段与恢复验证

自动化测试先执行 `scout -> plan`，再删除原始自定义 Workflow、Node YAML、Script 和 Validator，随后只使用 Run 内的 Node/Workflow 快照 resume。自定义 Node 仍能运行、发布 8 个 batch task，8 个 Research 必须同时进入运行态后才允许结束，最后继续完成所有阶段并导出报告。

还覆盖了：

- CLI `nodes describe` 发现自定义 Node；
- 已有 `plan.json` 作为输入单独运行自定义 Script Node；
- 自定义 Node 的脚本、Validator 和正式 Plan validator 都进入 Run 快照；
- 第一轮 8 scope、第二轮 5 scope 的通用 `batch + each` fan-out；
- ReportPlanner 对 8 份 current-state evidence 的 fan-in；
- 6 个 content task 到 Writer 的 fan-out；
- Artifact 发布、hash、scope、resume 和最终导出。

## 发现并修复的问题

原 CLI 将 `--mode` 与 `--workflow` 设为互斥。自定义 Heavy 拓扑因此会静默使用默认 `normal` 节点合同，Plan 的 `mode` 与 Workflow 语义不一致。本次已允许两者组合，并新增回归测试和文档：`--workflow` 决定拓扑，`--mode` 决定节点业务合同；自定义 Workflow 未显式传 mode 时仍默认 `normal`。

第一次语义错误的试跑已停止，Run 证据移动到 `/tmp/deepresearch-aborted-mode-mismatch-20260813`，且确认无残留 Hermes 进程。正式 E2E 使用修复后的 `mode=heavy` Manifest。

## 真实运行暴露的边界

- 当前 Driver 使用 `asyncio.gather` 等待同一 fan-out 组全部完成；一个慢任务会阻塞整组 `step_finished` 发布。
- 8 路并发本身稳定，但部分 Research 产生约 19 万 token 上下文并触发两次压缩；高并发不会消除单任务上下文和延迟风险。
- ReportPlanner 是 8 路 evidence fan-in 的主要慢点，曾两次生成脚本失败，Hermes 在同一 attempt 内修复后通过 Validator。
- 运行中出现一次 mid-tool-call stream drop 和 26 次可恢复工具错误；最终 60 个实例全部 succeeded，没有坏候选被发布。

## 内容质量结论

FinalReview 返回 `VERDICT: revise`。主要硬伤是终稿把“本轮 evidence 未提供可泛化生产灰度案例”升级成更强的公开缺失结论，并写入未被正式 evidence 支撑的 Reddit 403 细节。其余组织、引用形态和三个核心主题覆盖基本成立。

因此本结果只证明配置、调度、并发、Artifact 和完整导出有效；不证明该报告已通过内容质量验收。
