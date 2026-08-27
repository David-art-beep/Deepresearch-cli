# Heavy Smoke q01–q07 测试与改造汇总

> 统计日期：2026-08-26  
> 统计范围：`smoke q01 heavy` 以及同一批次的 q02–q07 Heavy，共7个 Run。  
> 重要：q01–q07 的实测发生在最新 Research 纯时间预算落地之前；第二部分会明确区分“运行时已生效”、“测试后已实施”和“尚待实施”。

## 第一部分：测试记录与失败分析

### 1.1 统计口径

本文使用以下 Run：

| Query | Run |
|---|---|
| q01 | `bench-finalrepair-smoke-q01-heavy-r01` |
| q02 | `bench-finalrepair-headless-q02-heavy-r01` |
| q03 | `bench-finalrepair-headless-q03-heavy-r01` |
| q04 | `bench-finalrepair-headless-q04-heavy-r01` |
| q05 | `bench-finalrepair-headless-q05-heavy-r01` |
| q06 | `bench-finalrepair-headless-q06-heavy-r01` |
| q07 | `bench-finalrepair-headless-q07-heavy-r01` |

指标口径：

- **Agent 数**：Journal 中 Node Spec `kind=agent` 的实际 attempt 数；并行 dimension、unit 的每个 attempt 分别计数，Python Script Node 不计入。
- **工具调用**：`acp-events.jsonl` 中唯一 `toolCallId` 的 `tool_call` 数；失败数是最终状态为 `failed` 的工具调用。
- **阶段 Active 耗时**：同一阶段内并行 instance 时间区间的并集，接近该阶段对墙钟时间的贡献。
- **累计 Agent 耗时**：同一阶段所有并行 instance 耗时之和，用于衡量计算工作量。
- 旧 Run 的 `harness.json` 未提供可汇总 Token usage，因此本文不推测 Token 成本。

### 1.2 总体结果

| 指标 | 结果 |
|---|---:|
| Run 数 | 7 |
| 完成 | 2 |
| 失败 | 5 |
| 完成率 | 28.6% |
| Agent attempt 总数 | 138 |
| Script attempt 总数 | 8 |
| 工具调用总数 | 3,054 |
| 失败工具调用 | 92 |
| 7个 Run 墙钟耗时之和 | 268.24 分钟 |
| 累计 Agent 耗时 | 约 672.22 分钟 |

两个完成 Run 的最终状态：

- q01：57.94 分钟完成，FinalReview 首次为 `pass`，最终报告 55,493 bytes。
- q07：68.41 分钟完成，FinalReview Diagnostic 为 `revise`，定向修复 `u2` 后 Recheck 为 `pass`，最终报告 175,503 bytes。

### 1.3 单 Run Agent、工具与结果

| Query | 状态 | 墙钟耗时（分） | Agent | 工具/失败 | Validator warning | 终止节点 | 失败原因/最终结果 |
|---|---|---:|---:|---:|---:|---|---|
| q01 | completed | 57.94 | 39 | 755/22 | 22 | Render | FinalReview 首次 `pass` |
| q02 | failed | 9.93 | 1 | 20/3 | 0 | Scout | Provider 请求3次失败，`Broken pipe` |
| q03 | failed | 36.11 | 6 | 306/4 | 7 | Research d2 | Research 达到 1800 秒硬超时，未交付 `evidence.json` |
| q04 | failed | 8.62 | 1 | 10/0 | 0 | Scout | Provider 请求3次失败，`Broken pipe` |
| q05 | failed | 75.28 | 38 | 892/23 | 9 | ReportPlanner | 大上下文请求3次 stale 150秒后以 `Broken pipe` 终止 |
| q06 | failed | 11.94 | 2 | 30/1 | 0 | Plan | Provider 请求3次失败，`Broken pipe` |
| q07 | completed | 68.41 | 51 | 1,041/39 | 6 | Render | 定向修复后 FinalReview Recheck `pass` |

### 1.4 各 Run 阶段 Active 耗时

单位为分钟；`N/A` 表示 Run 在到达该阶段前已失败。并行阶段取时间区间并集，不是各 dimension 耗时直接相加。

| 阶段 | q01 | q02 | q03 | q04 | q05 | q06 | q07 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Scout | 3.28 | 9.93 | 3.97 | 8.62 | 7.41 | 6.89 | 3.32 |
| Plan | 1.87 | N/A | 2.10 | N/A | 5.59 | 5.06 | 5.25 |
| Research ① | 8.46 | N/A | 30.04 | N/A | 10.56 | N/A | 10.55 |
| Review ① | 5.97 | N/A | N/A | N/A | 8.68 | N/A | 7.34 |
| Perspective ① | 1.93 | N/A | N/A | N/A | 1.73 | N/A | 2.04 |
| SupplementPlanner | 1.81 | N/A | N/A | N/A | 2.04 | N/A | 2.19 |
| Research ② | 9.90 | N/A | N/A | N/A | 19.62 | N/A | 9.60 |
| Review ② | 7.40 | N/A | N/A | N/A | 9.16 | N/A | 5.76 |
| Perspective ② | 1.82 | N/A | N/A | N/A | 1.78 | N/A | 2.01 |
| ReportPlanner | 6.16 | N/A | N/A | N/A | 8.72 | N/A | 4.89 |
| ReportWriter | 7.01 | N/A | N/A | N/A | N/A | N/A | 7.55 |
| Stitcher | <0.01 | N/A | N/A | N/A | N/A | N/A | <0.01 |
| FinalReview Diagnostic | 2.30 | N/A | N/A | N/A | N/A | N/A | 2.33 |
| FinalRepairPlanner | <0.01 | N/A | N/A | N/A | N/A | N/A | <0.01 |
| FinalRepair | N/A | N/A | N/A | N/A | N/A | N/A | 1.87 |
| RepairStitcher | <0.01 | N/A | N/A | N/A | N/A | N/A | <0.01 |
| FinalReview Recheck | N/A | N/A | N/A | N/A | N/A | N/A | 3.64 |
| Render | <0.01 | N/A | N/A | N/A | N/A | N/A | <0.01 |

### 1.5 跨 Run 阶段工作量

| 阶段 | 进入的 Run | Agent/Script attempt | Active 耗时之和（分） | 累计实例耗时（分） | 工具调用 |
|---|---:|---:|---:|---:|---:|
| Scout | 7 | 7 | 43.42 | 43.42 | 129 |
| Plan | 5 | 5 | 19.87 | 19.87 | 35 |
| Research ① | 4 | 18 | 59.61 | 191.31 | 1,042 |
| Review ① | 3 | 14 | 21.99 | 77.07 | 403 |
| Perspective ① | 3 | 14 | 5.70 | 22.05 | 113 |
| SupplementPlanner | 3 | 14 | 6.03 | 24.66 | 129 |
| Research ② | 3 | 14 | 39.12 | 119.24 | 569 |
| Review ② | 3 | 14 | 22.32 | 79.53 | 304 |
| Perspective ② | 3 | 14 | 5.61 | 20.35 | 108 |
| ReportPlanner | 3 | 3 | 19.77 | 19.77 | 47 |
| ReportWriter | 2 | 17 | 14.56 | 44.82 | 137 |
| Stitcher | 2 | 2 | 0.01 | 0.01 | 0 |
| FinalReview Diagnostic | 2 | 2 | 4.64 | 4.64 | 16 |
| FinalRepairPlanner | 2 | 2 | 0.01 | 0.01 | 0 |
| FinalRepair | 1 | 1 | 1.87 | 1.87 | 10 |
| RepairStitcher | 2 | 2 | 0.01 | 0.01 | 0 |
| FinalReview Recheck | 1 | 1 | 3.64 | 3.64 | 12 |
| Render | 2 | 2 | 0.01 | 0.01 | 0 |

Research 是这批测试的主要计算成本：两轮 Research 合计 32 个 dimension attempt、1,611 次工具调用，累计实例耗时约 310.55 分钟。

### 1.6 失败模式与证据

#### A. Provider 瞬态传输失败：q02、q04、q06

- q02 失败于 Scout，最终上下文摘要约 43,172 tokens。
- q04 失败于 Scout，最终上下文摘要约 59,832 tokens。
- q06 的 Scout 已成功，Plan 失败，最终上下文摘要约 32,739 tokens。
- 三者都是 Hermes Session 内的 Provider 请求连续3次 `ReadError: [Errno 32] Broken pipe`，而不是 Schema、Validator、认证或搜索 Provider 错误。
- 旧 Driver 在 Session 内重试耗尽后直接结束整个 Run，没有以全新 Session 重试当前 scope。

#### B. Research 不收敛：q03

- Scout 和 Plan 成功，Research ①启动4个并行 dimension。
- d3 在 9.70 分钟完成，d4 在 15.60 分钟完成，d1 在 23.87 分钟完成。
- d2 执行 30.04 分钟后触发 `Hermes invocation timed out after 1800.0s`。该 instance 已进行约79次模型调用和85次工具调用，但 staging 中没有 `evidence.json` 或 checkpoint。
- 根因是旧 Prompt 要求搜索完成后一次性写整份 Evidence；硬超时取消 Session 时，已搜索材料无法进入 Validator。

#### C. ReportPlanner 大上下文请求失败：q05

- q05 在失败前已完成两轮 Research、Review 和 Perspective，共38个 Agent attempt、892次工具调用。
- ReportPlanner 的非流式请求连续3次在150秒 stale threshold 被强制断开，随后返回 `Broken pipe`。
- 日志在 stale call 处记录约97,063 tokens，最终会话摘要约129,716 tokens。这说明大上下文是风险放大器，但直接错误仍是 Provider 长请求 stale/`Broken pipe`。
- 由于已完成的上游 Artifact 没有节点级恢复路径，Run 在最接近写作的位置丢失了本次执行成果。

#### D. 输出合同和语义修复：q01、q07

这两个 Run 没有终止，但暴露了在拼接前需要稳定修复的合同问题：

- 在更早的 Heavy 链路中，FinalReview 只要输出 `VERDICT: revise`，Validator 就会把它当成阻断错误；工作流没有根据审查意见派生修复任务，因此“报告可修复”会被等同为 Run 失败。
- 该问题不是 FinalReview 判断错误，而是 Runtime 缺少 `revise → 定向修复 → 复审` 的状态转移。
- q01：ReportWriter `u2`、`u3`、`u4` 首次输出分别因引用覆盖或 H3/H4/要求结构违规进入 `repairable`，第二次 unit attempt 全部成功；FinalReview 首次 `pass`。
- q07：ReportWriter `u2`、`u8` 首次因引用覆盖/要求结构违规进入 `repairable`；修复后 Stitcher 通过。FinalReview 仍定向要求修复 `u2`，修复后 Recheck `pass`。
- 这些问题证明格式、标题、引用和 `render_contract` 适合由 Python 硬校验；模型只需处理定位后的局部修复和语义问题。

## 第二部分：针对失败模式的修改

### 2.1 已在这批测试中生效：Stitch 确定性收口

改造前设想过三段式链路：

```text
stitch-preparer（确定性代码）
  → stitch-polisher（必要时少量模型润色）
  → stitcher（确定性代码）
```

实际落地时合并为一个确定性 Stitcher，避免每次 Run 固定增加全局润色 Agent：

```text
ReportWriter units
  → ReportWriter 代码合同校验/当前 unit 修复
  → Stitcher（Python 确定性拼接）
  → FinalReview Diagnostic
      → materializer（Python 定位 unit）
  → FinalRepair（仅修指定 unit）
  → FinalReview Recheck（Python preparer 拼接 + Agent 最多复审一次）
  → Render（Python）
```

确定性检查包括：

- 按 Outline 顺序拼接 unit，不让 Agent 自由重组全文；
- 标题级别、重复标题、唯一 H1 和 unit 边界检查；
- `render_contract` 要求的 element 是否在指定 unit 落地；
- claim/source ID 是否存在，引用是否跨 unit 或越界；
- routed claim 是否在要求的 unit/element 中被引用；
- 违规时报出具体 `unit_id`、`element_id` 和适用的 `claim_id`，不依赖 Agent 凭感觉判断。

q01 和 q07 证明这条链路可以将格式/引用问题限定在具体 unit，并且在不全文重写的前提下完成交付。

### 2.2 已实施：FinalReview `revise` 定向修复闭环

旧链路中，通用 FinalReview Validator 明确将 `revise` 转换为阻断错误：

```text
FinalReview
  → pass：Render
  → revise：Validator 失败 → Run 失败
```

现在拆分为“首次诊断”和“最终门禁”两种语义：

```text
FinalReview Diagnostic
  → pass
      → Diagnostic materializer 不生成 task
      → 直接 Render

  → revise + REPAIR_TARGET
      → Diagnostic materializer（Python）
      → repair-tasks/uN.json
      → FinalRepair（只修当前 unit）
      → FinalReview Recheck preparer（只替换指定 unit并确定性拼接）
      → FinalReview Recheck Agent（唯一一次）
          → pass：Render
          → revise：Run 失败
```

具体修复：

1. `final-review-diagnostic` 的 Validator 允许 `VERDICT: revise`，但要求至少一条结构化
   `REPAIR_TARGET: uN | issue` 或 `REPAIR_TARGET: global | issue`。
2. `final-review-diagnostic` 的 materializer 是确定性 Python，只解析 `VERDICT` 和 `REPAIR_TARGET`，不从自由文本猜测修复位置。
3. 指定 `uN` 时只为这些 unit 生成 task；`global` 或没有可识别 unit 时才扩展到 Outline 中全部 unit。
4. FinalRepair 只读当前 unit 的原稿、Outline、Evidence subset 和定向审查意见，不搜索新资料、不改其他 unit。
5. `final-review-recheck` 先由受信任 preparer 确定性重新拼接，并锁定该产物禁止 Agent 改写；随后使用最终门禁 Validator，此时 `revise` 才是阻断错误，不再进入第二轮修复。
6. 整个过程最多一次 Repair 和一次 Recheck，避免 `Review → Repair` 无限循环。

q07 是该修复的实测证据：首次 Diagnostic 输出 `revise` 并定位 `u2`，Runtime 没有终止 Run，而是执行 1.87 分钟的 FinalRepair 和 3.64 分钟的 Recheck；Recheck `pass` 后成功 Render。

### 2.3 历史改造（已撤回）：Research 纯时间预算与强制收口

> 2026-08-26 已恢复 Research 为普通 Agent 节点：统一使用 `node_timeout_seconds`，不再创建
> Runtime checkpoint、不再触发独立 ResearchFinalizer，也不执行 Research 专属 attempt-2。
> 以下内容保留为当时的方案和测试记录，不代表当前链路。

该改造直接针对 q03 d2 “搜索30分钟但没有 Evidence”的失败模式。预算只看墙钟时间，模型和工具调用次数只做观测指标：

```yaml
research_budget:
  checkpoint_deadline_seconds: 120
  checkpoint_interval_seconds: 180
  soft_timeout_seconds: 900
  finalize_timeout_seconds: 180
  hard_timeout_seconds: 1140
  max_attempts: 2
```

当前执行链路：

```text
0–2 分钟
  建立 _runtime/research-checkpoint.json

0–15 分钟
  正常 Research，每3分钟更新 checkpoint

15 分钟
  取消原 Research Session，停止继续搜索
  → 按 invocation namespace 导出 Search Ledger
  → 启动独立 research-finalizer

15–18 分钟
  Finalizer 只整理已有材料，生成正式 Evidence

19 分钟
  当前 attempt 绝对上限
```

实现要点：

- checkpoint 位于 `staging/_runtime`，冻结 Candidate 时排除，不会被直接发布为 Evidence。
- checkpoint 只能保存已打开原文核验的 `fact_notes`；未读取 URL、搜索摘要和模型推测不能成为 factual claim。
- `invocation.json` 持久化 invocation ID；软超时后从 Run 级 Search SQLite 只导出当前 namespace 的去重候选。
- Finalizer 的 `node_type=research-finalizer`，代码层不挂载 Search MCP；Prompt 禁止浏览器、委派和新搜索。
- Finalizer 生成的文件仍须经过原 Research Validator；通过后才发布 Artifact，并写入 `RUNTIME_FORCED_FINALIZE` warning。
- Finalizer 或 Validator 失败时只重试当前 dimension；最多2个 attempt，不会无限重试。
- Benchmark 汇总现在单独记录 `retryable` attempt、Finalizer invocation 和强制收口次数。

该链路已通过确定性单元/集成测试，但尚未重跑 q03 或整批 q01–q07，因此本文第一部分中的强制收口次数仍为0，不能把旧 q03 视为改造后的回归结果。

### 2.4 尚待实施：Provider 节点级瞬态重试

该改造针对 q02、q04、q06，也可以在 q05 ReportPlanner 小上下文情况下复用。建议：

1. 将 `Broken pipe`、`ReadError`、stale-call kill、连接 reset 和可恢复 5xx 分类为结构化 `retryable` Provider 错误。
2. Hermes Session 内的3次 HTTP 重试耗尽后，Driver 使用全新 Session 只重跑当前 scope 一次。
3. 已成功的上游 scope 和 Artifact 保持不变；不重跑整个 Query。
4. 认证失败、额度问题、Schema/Validator 错误和 Python Script 错误不得当作瞬态 Provider 错误。
5. 最多2个节点 attempt，第二次仍失败才终止 Run。

当前代码已有 `retryable` outcome 和 Research 定向重试语义，但尚未把所有 Provider 瞬态错误接入该分支。

### 2.5 尚待实施：ReportPlanner Evidence 压缩

该改造针对 q05。建议在 ReportPlanner 前增加确定性 EvidenceIndexer：

```text
最终 evidence.json
  → EvidenceIndexer（Python）
  → evidence-index.json
  → ReportPlanner
```

`evidence-index.json` 只保留规划提纲所需的 dimension/claim/source ID、claim 文本与类型、来源标题/URL/日期/质量、gaps 和 conflicts；去除搜索过程、原始长文、重复来源和不影响 Outline 的运行元数据。

建议预算：

```yaml
report_planner_budget:
  target_input_tokens: 100000
  warning_input_tokens: 120000
```

这不是对完整 Evidence 的破坏性截断：ReportWriter 仍使用完整 Evidence，压缩索引只服务于 ReportPlanner 的结构规划。

### 2.6 回归测试建议

按以下顺序验证改造效果：

1. 先单独重跑 q03 Heavy，确认长尾 dimension 在15分钟进入 Finalizer，19分钟内成功发布或开始定向 attempt-2。
2. 再重跑 q01 和 q07，确认正常 Research 在15分钟内不会被错误强制收口，Stitch/FinalReview 结果不回退。
3. Provider 瞬态重试落地后重跑 q02、q04、q06，验证只重跑失败节点。
4. EvidenceIndexer 落地后重跑 q05，记录压缩前后 ReportPlanner 输入规模、耗时和成功率。
5. 最后重跑 q01–q07 Heavy，同时对比首次成功率、最终成功率、Agent、工具、强制收口和各阶段 Active/累计耗时。
