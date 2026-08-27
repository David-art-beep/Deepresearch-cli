# Heavy 工作流确定性收口改造与可靠性增强方案

> 状态：拼接硬化和 FinalReview 定向修复已落地；Research 纯时间预算/强制收口已于
> 2026-08-26 撤回，恢复为使用统一 `node_timeout_seconds` 的普通 Agent 节点；
> Provider 通用瞬态重试和 ReportPlanner 输入压缩仍待实施。
>
> 日志基线日期：2026-08-26。

## 1. 文档目的

本文说明两部分内容：

1. Heavy 模式此前完成的确定性拼接、代码级格式/引用检查，以及 FinalReview 一次定向修复闭环。
2. 根据 q02–q06 Heavy 实测失败日志制定的后续可靠性改造方案，包括节点级瞬态重试、Research 预算控制与超时强制输出、ReportPlanner 输入压缩和 Benchmark 指标补充。

本文以当前仓库代码为准。当前 Heavy 工作流定义见 [`config/workflows/heavy.yaml`](../config/workflows/heavy.yaml)。

## 2. 改造背景

原来的收口阶段过度依赖 Agent 阅读多个草稿后自行判断：

- 内容单元应该如何拼接；
- 标题是否缺失、重复或顺序错误；
- `render_contract` 是否兑现；
- 引用是否来自合法 Evidence；
- 每条 routed claim 是否在规定的 unit/element 中得到引用；
- 发现问题后应该修改哪一部分。

这些规则大部分是结构化、可枚举和可重复判断的合同，不适合交给模型凭语义感觉检查。模型判断会带来以下问题：

- 同一份输入重复运行可能得到不同结论；
- 报错位置不稳定，难以直接定位到 `uN`；
- 为修复局部格式问题而重写整篇报告，可能破坏已正确内容；
- 拼接 Agent 会引入新的标题、过渡语或未路由事实；
- 链路变长，增加模型调用、上下文和失败概率。

因此改造原则是：**可以由代码确定的规则全部代码化；模型只处理代码无法判断的语义质量问题。**

## 3. 设计演进与当前落地形态

### 3.1 讨论过的三段式设计

最初讨论的收口结构是：

```text
ReportWriter drafts
  → stitch-preparer（确定性代码）
  → stitch-polisher（仅在必要时调用模型）
  → stitcher（确定性代码）
```

其职责设想为：

- `stitch-preparer`：整理草稿、生成拼接上下文和待修问题；
- `stitch-polisher`：只对无法由代码处理的问题做少量语言润色；
- `stitcher`：最终确定性拼接和硬校验。

### 3.2 当前实际实现

最终采用了合并方案，没有在 Heavy 工作流中保留三个独立节点：

```text
ReportWriter drafts
  → stitcher（确定性 Python）
  → FinalReview Diagnostic（语义审查）
  → 一次定向修复闭环
  → render（确定性 Python）
```

当前代码状态：

- `stitch-preparer` 的准备和检查职责已经合并进确定性 `stitcher`；
- 当前没有独立的 `stitch-polisher` 节点，也不执行全局自由润色；
- ReportWriter 的 Validator 可以触发一次当前 unit 的模型修复；
- FinalReview 只在发现语义硬伤时触发一次定向 unit 修复；
- 最终拼接、引用渲染和结构检查均由 Python 完成。

这样既保留“必要时少量模型修改”的能力，又避免在每次运行中固定增加一个全局润色 Agent。

## 4. 当前 Heavy 收口链路

完整 Heavy 链路为：

```text
Scout
  → Plan
  → Research ① / Review ① / Perspective ①
  → SupplementPlanner
  → Research ② / Review ② / Perspective ②
  → ReportPlanner
  → ReportWriter（按 content unit 并行）
  → Stitcher（确定性代码）
  → FinalReview Diagnostic
      ├─ materializer pass：不生成 repair task
      └─ materializer revise：生成指定 unit 的 repair task
  → FinalRepair（仅 revise 时按 unit 并行）
  → FinalReview Recheck（preparer 确定性拼接，Agent 仅修复后复审一次）
  → Render（确定性代码）
  → report.md
```

## 5. 已完成：确定性代码拼接

### 5.1 Stitcher 的输入输出

节点定义见 [`config/nodes/stitcher.yaml`](../config/nodes/stitcher.yaml)，实现见 [`src/deepresearch_cli/stitch_finalize_node.py`](../src/deepresearch_cli/stitch_finalize_node.py)。

输入：

- `outline.json`；
- 全部 `report-draft`；
- 最终 `evidence.json`。

输出：

- `stitched.md`。

Stitcher 不调用模型，主要执行：

1. 按 `outline.content_units[]` 的顺序读取草稿；
2. 确认每个 unit 都存在且只出现一次；
3. 根据 `show_heading` 决定是否保留 unit 标题；
4. 检查每个 unit 的 Markdown 形态是否符合 `render_contract`；
5. 建立 `claim_id → source_id` 的确定性映射；
6. 拒绝越界引用、未知来源和内部 claim ID 泄漏；
7. 生成统一 H1、可选目录占位符和按顺序拼接的 `stitched.md`。

拼接核心合同实现位于 [`src/deepresearch_cli/stitching.py`](../src/deepresearch_cli/stitching.py)。

### 5.2 FinalReview Recheck 的确定性 preparer

定向修复后，`final-review-recheck` 在调用 Agent 前使用 [`src/deepresearch_cli/repair_stitch_node.py`](../src/deepresearch_cli/repair_stitch_node.py) 重新拼接：

```text
原始 drafts + repaired drafts
  → 以 content-unit-id 精确替换
  → 再次运行相同拼接合同
  → 新 stitched.md
```

它不会对未被 FinalReview 点名的 unit 做任何修改；拼接产物被运行时锁定为只读，复审 Agent 修改它会直接失败。

## 6. 已完成：render-contract、引用和标题硬校验

### 6.1 校验位置

硬校验在两个位置执行：

1. ReportWriter 输出单个 `draft.md` 后，运行 unit 级 Validator；
2. Stitcher 拼接全文后，运行全文级 Validator。

主要实现：

- [`src/deepresearch_cli/stitching.py`](../src/deepresearch_cli/stitching.py)
- [`src/deepresearch_cli/node_validators/report_writer.py`](../src/deepresearch_cli/node_validators/report_writer.py)
- [`src/deepresearch_cli/node_validators/stitcher.py`](../src/deepresearch_cli/node_validators/stitcher.py)
- [`src/deepresearch_cli/node_validators/report_markdown.py`](../src/deepresearch_cli/node_validators/report_markdown.py)

### 6.2 render-contract 检查

代码根据 `outline.content_units[].render_contract` 检查：

- `mode=markdown_table`：必须存在 Markdown 表格，表头覆盖合同 schema；
- `mode=ordered_list`：必须存在有序列表；
- `mode=checklist`：必须存在 checklist；
- `mode=callout`：必须存在 Markdown 引用块；
- `mode=mermaid`：必须存在 Mermaid 代码块；
- `mode=qa`：必须包含合同要求的问答标签；
- `show_heading=true`：草稿必须以指定 H2 开始且只出现一次；
- `show_heading=false`：不得擅自增加对应 H2；
- `secondary_structure`：H3/H4 是否允许、是否必需、级别和顺序是否正确；
- element 是否完整、唯一并按 Outline 顺序出现；
- 表格、列表和 element 区域能否被稳定定位。

### 6.3 引用检查

引用规则由 Python 校验，不再让 Agent 判断“看起来是否引用充分”：

- 引用键必须使用合法 source ID；
- 禁止把 `dN.cM` claim ID 当成引用；
- source ID 必须存在于 routed Evidence；
- 每个 routed claim 至少引用一个与其绑定的 source；
- `citation_policy.scope=element` 时，引用必须出现在对应 element 区域；
- `citation_policy.scope=unit` 时，引用可以在当前 unit 范围内满足；
- 表格中配置为 `required_fields` 的单元格必须带引用；
- 拼接稿不得提前生成脚注定义或参考文献章。

### 6.4 标题和全文结构检查

代码检查：

- content-unit 草稿不得包含 H1；
- `stitched.md` 必须且只能有一个 H1；
- H1 必须是全文第一个非空内容；
- 需要显示的 unit H2 必须各出现一次；
- unit H2 必须与 Outline 顺序一致；
- 禁止 Writer 自行增加合同外的二级/三级结构。

### 6.5 结构化错误定位

错误不再只返回模糊自然语言，而是包含稳定规则 ID 和具体 unit/element，例如：

```json
{
  "rule": "UNIT_CITATION_COVERAGE",
  "severity": "error",
  "unit_id": "u2",
  "element_id": "e3",
  "claim_id": "d3.c14",
  "expected_source_ids": ["d3_s11"],
  "cited_source_ids": ["d3_s2", "d3_s21"]
}
```

当前已使用的典型规则包括：

- `UNIT_EMPTY`
- `UNIT_H1`
- `UNIT_HEADING`
- `UNIT_RENDER`
- `UNIT_ELEMENT_ORDER`
- `UNIT_SECONDARY_STRUCTURE`
- `UNIT_ELEMENT_REGION`
- `UNIT_CITATION_KEY`
- `UNIT_CLAIM_SOURCE`
- `UNIT_CITATION_COVERAGE`
- `UNIT_TABLE_CELL_CITATION`

Validator 失败时，Runtime 可以把具体错误交给同一 unit 的一次修复尝试，而不是让模型重新阅读整篇报告。

## 7. 已完成：最终引用渲染

Render 节点见 [`config/nodes/render.yaml`](../config/nodes/render.yaml) 和 [`src/deepresearch_cli/render_node.py`](../src/deepresearch_cli/render_node.py)。

它使用确定性脚本：

- 将内部 `[^source_id]` 转换为连续引用编号；
- 合并 URL 相同的来源别名；
- 生成脚注/参考文献；
- 拒绝 orphan citation；
- 拒绝 claim ID citation；
- 按需插入目录；
- 输出最终 `report.md` 和引用清单。

模型不负责最终编号，因此 unit 修复和重新拼接不会造成编号错乱。

## 8. 已完成：FinalReview 一次定向修复闭环

### 8.1 首次诊断

`final-review-diagnostic` 只处理代码无法可靠判断的语义问题，例如：

- 是否真正回答原始 Query；
- 是否遗漏用户点名对象、字段、时间或地域；
- 结论强度是否超过 Evidence；
- 是否用证据缺口替代直接回答；
- 跨维度冲突是否被正确表达；
- 报告组织是否符合读者任务。

输出必须包含唯一 Verdict：

```text
VERDICT: pass
```

或：

```text
VERDICT: revise
REPAIR_TARGET: u2 | 具体问题与修改方向
REPAIR_TARGET: u4 | 具体问题与修改方向
```

跨 unit 问题使用：

```text
REPAIR_TARGET: global | 具体问题与修改方向
```

### 8.2 确定性任务派生

[`src/deepresearch_cli/final_repair_planner_node.py`](../src/deepresearch_cli/final_repair_planner_node.py) 只解析稳定标记，不从任意自然语言猜测修复目标。

输出：

- `decision.json`；
- `repair-tasks/uN.json`；
- 修复后唯一一次复审所需的 `recheck-tasks/once.json`。

`VERDICT: pass` 时不生成 repair/recheck task。

### 8.3 定向修复

FinalRepair 每个实例只读取：

- 当前 `repair-task`；
- 首次 FinalReview；
- 当前 unit 的 Outline 和 evidence subset；
- 当前 unit 原稿。

它不能：

- 搜索新资料；
- 修改 Outline 或 Evidence；
- 修改其他 unit；
- 重排全文；
- 引入 subset 之外的事实和来源。

输出是当前 unit 的完整替换稿 `repaired-draft.md`。

### 8.4 只复审一次

`final-review-recheck` 的确定性 preparer 替换指定 unit、重新拼接并锁定终稿后，Agent 重新审查一次：

- `pass`：进入 Render；
- 再次 `revise`：工作流直接失败；
- 不允许 `Review → Repair → Review → Repair` 无限循环。

### 8.5 实际运行验证

本轮 Benchmark 已经验证了这些闭环：

- q01 的多个 ReportWriter unit 被代码级合同定位，第二次 unit 尝试修复后成功；
- q07 的 `u2`、`u8` 先经过 ReportWriter 合同修复；
- q07 首次 FinalReview 又定向修复 `u2`，随后 Recheck 和 Render 成功；
- q07 最终生成完整报告，说明确定性拼接和单次语义修复可以共同工作。

## 9. q02–q06 实测问题

本轮使用的公共配置为：

```yaml
execution:
  max_concurrency: 6
  node_timeout_seconds: 1800
```

隔离 Hermes 当时使用：

```yaml
agent:
  max_turns: 150
```

失败情况：

| Query | 失败节点 | 直接原因 | 根因分类 |
|---|---|---|---|
| q02 | Scout | 三次请求无响应后 `Broken pipe` | Provider 瞬态传输故障 |
| q03 | Research d2 | 超过 1800 秒 | Research 未收敛且没有提前写 Evidence |
| q04 | Scout | 三次请求无响应后 `Broken pipe` | Provider 瞬态传输故障 |
| q05 | ReportPlanner | 三次 150 秒 stale-call 后 `Broken pipe` | 大上下文长请求叠加 Provider 瞬态故障 |
| q06 | Plan | 三次请求无响应后 `Broken pipe` | Provider 瞬态传输故障 |

这些失败不是 API Key 缺失，也不是 Evidence/Render 合同失败。

## 10. Heavy 日志预算基线

已完成的 q01 和 q07 总耗时分别约为 57.9 和 68.4 分钟。节点实测范围如下：

| 节点 | 成功耗时范围 | 模型调用峰值 | 工具调用峰值 |
|---|---:|---:|---:|
| Scout | 3–7 分钟 | 16 | 22 |
| Plan | 2–6 分钟 | 8 | 8 |
| Research ① | 4–24 分钟 | 49 | 78 |
| Research ② | 6–20 分钟 | 36 | 48 |
| Review | 4–9 分钟 | — | — |
| Perspective | 1–2 分钟 | — | — |
| SupplementPlanner | 1–2 分钟 | — | — |
| ReportPlanner | 5–6 分钟 | 15 | 19 |
| ReportWriter | 1–4 分钟/尝试 | — | — |
| FinalReview | 2–4 分钟 | 9 | 12 |
| Python 节点 | 通常不足 1 分钟 | 0 | 0 |

q03 Research d2 的异常轨迹：

```text
API call #1   11:00
API call #50  11:13
API call #60  11:16
API call #70  11:20
API call #79  11:29
Session 被取消 11:30
```

取消时 staging 中没有 `evidence.json`。因此仅设置节点超时无法抢救已经完成的搜索工作。

## 11. 待实施：节点级瞬态重试

### 11.1 目标行为

```text
Hermes 内部 API 重试三次
  → 仍为 Broken pipe / ReadError / 429 / 5xx
  → 当前节点标记 retryable
  → 等待 30 秒
  → 使用全新 Hermes Session 重跑当前节点
  → 成功后继续工作流
```

对于 fan-out 节点，只重跑失败 scope：

```text
research[d1] succeeded ┐
research[d3] succeeded ├─ 保留 Artifact
research[d4] succeeded ┘
research[d2] retryable → 只运行 attempt-2
```

### 11.2 状态模型

节点结果建议扩展为：

```text
succeeded
repairable   # 输出/Validator 可由模型修复
retryable    # 网络、Provider、节点超时
failed       # 确定性不可恢复错误
```

`retryable` 不应注入内容修复 Prompt；下一次尝试必须使用干净上下文和全新 Session。

可重试错误：

- `Broken pipe`；
- `ReadError` / `APIConnectionError`；
- HTTP 429、502、503、504；
- Provider stale-call；
- Hermes invocation timeout；
- ACP 进程意外退出。

不可按瞬态重试处理：

- 认证失败；
- 余额/额度失败；
- Schema 或 Validator 失败；
- Python Script 异常；
- render-contract 硬校验失败。

### 11.3 建议参数

```yaml
retry:
  transient_max_attempts: 2
  transient_backoff_seconds: 30
```

这里的 `2` 是总节点尝试次数，即首次执行加一次全新 Session 重试。Hermes 每次 Session 内部仍保留自己的三次 Provider 请求重试。

## 12. 历史方案（已撤回）：Research 流程、预算和超时强制输出

> 本节保留用于说明 q01–q08 后曾实施的设计。当前代码不再创建 checkpoint、不启动
> ResearchFinalizer、不导出超时抢救材料，也不进行 Research 专属 attempt-2；Research 超时行为
> 与其他 Agent 节点一致，由统一的 `node_timeout_seconds` 控制。

### 12.1 Research 在 Heavy 中的位置

Heavy 包含两轮 Research：

```text
Plan
  → Research ①（initial）
  → Review ①
  → Perspective ①
  → SupplementPlanner
  → Research ②（supplement）
  → Review ②
  → Perspective ②
  → ReportPlanner
```

两轮都使用同一个 [`config/nodes/research.yaml`](../config/nodes/research.yaml) NodeSpec，但输入和输出语义不同。

第一轮 `initial` 输入：

- 当前维度的 `research-task`；
- 全局 `plan.json`；
- 原始 Query、语言、模式；
- Evidence Schema；
- 当前 `dimension-id`。

第一轮输出：

- 当前维度完整的 `evidence.json`。

第二轮 `supplement` 输入：

- SupplementPlanner 为当前维度派生的补研 task；
- 第一轮 `evidence.json`；
- `supplement-plan.json`；
- `plan.json`；
- 当前 `dimension-id`。

第二轮输出：

- 合并旧证据与补研结果后的完整新版 `evidence.json`；
- `supplement-plan.completed.json`。

第二轮输出不是增量 patch。ReportPlanner 消费第二轮发布的完整 Evidence，不自行合并两轮文件。

### 12.2 当前 Research 节点的内部流程

当前一个 Research dimension 的执行过程是：

```text
1. Runtime 构建 Node Context
   ↓
2. Agent 读取 task / plan / schema
   ↓
3. 将每条 KQ 转成内部研究工作单
   ↓
4. 选择搜索 domain / provider
   ↓
5. 发现候选 → 展开成员 → 打开原文 → 核验关键内容
   ↓
6. 形成 sources / claims / conflicts / gaps / writing_context
   ↓
7. 生成 headline 和 key_findings
   ↓
8. 一次性写出完整 evidence.json
   ↓
9. 运行 Evidence Validator
   ↓
10. supplement 模式再运行 SupplementPlan Validator
   ↓
11. 冻结 Candidate 并发布 Artifact
```

其中搜索分成两类：

1. DeepResearch Search MCP：按 domain/provider 进行批量发现，结果保存在 Run 级 `search/search.sqlite3`；
2. Hermes 网页工具：执行补充网页搜索、页面打开和内容提取。

Search Coordinator 以 Run 为生命周期，多个并行 dimension 共享数据库，但每次 invocation 使用独立 namespace。成功 Artifact 由 Runtime 按 `dimension-id` 分开发布。

### 12.3 当前流程为什么无法在超时后强制输出

当前 Research Prompt 明确要求：

```text
先完成 sources、claims 和 key_findings 的整体核对，
再一次写出完整 evidence.json；
不要边搜索边反复覆写整份 evidence。
```

这个约束有利于避免大 JSON 被频繁重写，但产生了一个运行时风险：Agent 可能完成大量搜索，却一直没有生成任何可发布或可抢救的结构化文件。

q03 d2 就是该问题的直接样本：

- 运行 30 分钟；
- 79 次模型调用；
- 85 次工具调用；
- 最后上下文约 177k；
- staging 中没有 `evidence.json`；
- 到达 1800 秒后 Session 被取消，全部已完成搜索无法直接进入 Validator。

因此不能在硬超时发生后再向原 Session 发送“请立即输出”。硬超时时 Prompt 已经被取消，模型没有继续写文件的机会。

### 12.4 q01–q08 Research 实测结果

q01–q08 中，只有 q01、q03、q05、q07 真正进入了 Research：

| Query | Research ① | Research ② | 结论 |
|---|---|---|---|
| q01 | 4 个维度全部成功；4–8 分钟，13–33 次模型调用 | 4 个维度全部成功；6–10 分钟，18–32 次模型调用 | 正常完成基线 |
| q02 | 未进入；Scout 失败 | 未进入 | 不参与 Research 预算统计 |
| q03 | d1/d3/d4 成功；10–24 分钟，21–49 次模型调用；d2 在 30 分钟、79 次调用时超时 | 未进入 | 唯一 Research 硬超时样本 |
| q04 | 未进入；Scout 失败 | 未进入 | 不参与 Research 预算统计 |
| q05 | 5 个维度全部成功；6–11 分钟，18–37 次模型调用 | 5 个维度全部成功；6–20 分钟，12–31 次模型调用 | 长补研成功基线 |
| q06 | 未进入；Plan 失败 | 未进入 | 不参与 Research 预算统计 |
| q07 | 5 个维度全部成功；7–11 分钟，26–49 次模型调用 | 5 个维度全部成功；7–10 分钟，19–36 次模型调用 | Headless 成功基线 |
| q08 | 未进入；Batch 在 Scout 中断 | 未进入 | 不参与 Research 预算统计 |

所有成功 Research 的观测边界：

- 最长成功耗时：24 分钟；
- 最高成功模型调用：49 次；
- 最高成功工具调用：78 次；
- Research ② 最长成功耗时：20 分钟；
- Research ② 最高成功模型调用：36 次。

异常 Research d2：

- 30 分钟硬超时；
- 79 次模型调用；
- 85 次工具调用；
- 没有正式输出，也没有中间 checkpoint。

由此得到两个预算结论：

1. 模型和工具调用次数与完成度不是稳定线性关系，只作为观测指标，不用作预算触发器；
2. 只依赖 30 分钟硬超时太晚，必须在硬超时前按墙钟时间切换到独立 Finalizer。

### 12.5 校准后的 Research 预算

收紧版建议：

```yaml
research_budget:
  checkpoint_deadline_seconds: 120
  checkpoint_interval_seconds: 180
  soft_timeout_seconds: 900
  finalize_timeout_seconds: 180
  hard_timeout_seconds: 1140
  max_attempts: 2
```

对应行为：

```text
0–2 分钟
  建立 runtime checkpoint；没有 checkpoint 只告警，不立即杀节点

0–15 分钟
  正常搜索；每 3 分钟更新 checkpoint

达到 15 分钟
  停止新搜索并取消原 Research Session

随后最多 3 分钟
  ResearchFinalizer 使用已有材料生成正式 Evidence

19 分钟
  当前 attempt 的绝对上限

Finalizer 仍失败
  当前 dimension 使用全新 Session 执行 attempt-2
```

`soft_timeout_seconds=900` 不是失败线，而是“从继续搜索切换到整理交付”的状态线。q03 d3/d4 分别约 10/16 分钟完成，d1 长尾到 24 分钟，q05 Research ②长尾到 20 分钟；在新机制下，超过 15 分钟的节点将不再扩展搜索，而是使用已保存的材料收口。

模型调用次数、工具调用次数和 Hermes `max_turns` 继续记录到 Benchmark 指标，但都不触发软超时或强制收口。

### 12.6 Runtime Checkpoint 设计

不建议在搜索过程中反复覆写正式 `evidence.json`。正式文件必须保持“一次收口、完整校验、通过后发布”的语义。

新增 Runtime 专用路径：

```text
staging/_runtime/research-checkpoint.json
```

现有 NodeRunner 在冻结 publication candidate 时已经排除 `_runtime` 顶层目录，因此该文件：

- 不会成为正式 Artifact；
- 不进入下游 Evidence 状态；
- 不需要满足完整 Evidence Schema；
- 可以被超时后的 ResearchFinalizer 读取。

Checkpoint 至少记录：

```json
{
  "dimension_id": "d2",
  "research_phase": "initial",
  "completed_kq_ids": ["kq1", "kq2"],
  "pending_kq_ids": ["kq3"],
  "sources": [
    {
      "url": "https://example.com/source",
      "title": "Source title",
      "retrieved": true
    }
  ],
  "fact_notes": [
    {
      "kq_id": "kq1",
      "source_url": "https://example.com/source",
      "text": "已经从原文核验的事实"
    }
  ],
  "conflicts": [],
  "gaps": ["尚未取得同口径年度数据"]
}
```

Checkpoint 只允许保存已经打开原文核验的事实。搜索摘要、未读取 URL 和模型推测不能写入 `fact_notes`。

更新时机：

1. 完成内部 KQ 工作单后创建空 checkpoint；
2. 每完成一个 KQ 更新；
3. 此后每 3 分钟更新；
4. 开始生成正式 Evidence 前再更新一次。

### 12.7 Search Ledger 抢救

除了模型 checkpoint，Search MCP 会把发现过程写入 Run 级 SQLite。当前已实施：

1. 在 `invocation.json` 中持久化 `invocation_id`；
2. 使用该 ID 对应 Search SQLite 的 namespace；
3. 在软超时后确定性导出当前 invocation 的搜索结果；
4. 输出为 `_runtime/search-materials.json`；
5. 对 URL 去重，并将 Ledger 中的条目统一标为 `candidate_only`；是否已核验以 checkpoint 为唯一依据。

Search Ledger 是发现候选的兜底，不自动等于 Evidence。没有原文内容的 hit 只能帮助 Finalizer记录 gap 或来源候选，不能直接生成 factual claim。

### 12.8 ResearchFinalizer 流程

软预算触发后，不依赖向繁忙的原 ACP Prompt 注入新消息。采用独立短 Session：

```text
取消原 Research Session
  → 冻结 checkpoint 和 search-materials
  → 启动 research-finalizer
  → 不挂载 Search MCP，Prompt 禁止浏览器/委派
  → 只整理已有材料
  → 写正式 evidence.json
  → supplement 模式写 completed plan
  → Runtime 运行正式 Validators
```

当前 Finalizer 预算：

```yaml
research_finalizer:
  timeout_seconds: 180
  allow_search: false
  allow_browser: false
  allow_delegation: false
```

Finalizer 输入：

- 原始 Query；
- 当前 research task 和 plan；
- Evidence Schema；
- runtime checkpoint；
- 当前 invocation 导出的 search materials；
- supplement 模式下的旧 Evidence 和 Supplement Plan；
- 正式输出路径。

Finalizer 只能写：

- `evidence.json`；
- supplement 模式下的 `supplement-plan.completed.json`。

### 12.9 强制输出的质量边界

强制输出不能伪造完整性：

- 已从原文核验的材料才能写为 claim；
- 来源冲突写入 conflicts；
- 未覆盖问题写入 gaps/writing context；
- 只有搜索 hit、没有原文内容的来源不能支撑 factual claim；
- 不得用搜索摘要补齐数值、日期、因果或监管状态；
- Validator 无法通过时不得发布 Artifact。

Supplement 模式下，原 `pending` item 必须按正式合同转成：

- `resolved`；
- `partial`；
- `no_data`；
- `out_of_scope`。

其中：

- `partial` 必须在 Evidence 中留下 `unresolved_gap`；
- `no_data` 必须留下 `availability_gap`；
- `out_of_scope` 必须留下 `scope_boundary`；
- 原有 `deferred_items[]` 原样保留。

成功强制收口应在 `validation_warnings` 或单独运行指标中记录：

```json
{
  "rule": "RUNTIME_FORCED_FINALIZE",
  "severity": "warning",
  "step_id": "research",
  "scope": {"dimension-id": "d2"},
  "attempt": 1,
  "trigger": "soft_timeout",
  "coverage_status": "partial"
}
```

### 12.10 触发优先级

建议使用以下确定性顺序：

```text
主 Research 正常结束且输出存在
  → Validator
  → succeeded / repairable

达到 Research 15 分钟软时间
  → ResearchFinalizer
  → Validator 通过：succeeded + forced-finalize warning
  → Validator 不通过：retryable

Research Provider 连接失败
  → 当前仍按原有失败语义处理
  → 待通用瞬态重试落地后再接入 retryable

retryable 且 attempt < 2
  → 只重跑当前 dimension

attempt-2 仍失败
  → 当前 Run 终止
```

Validator 的 `repairable` 与传输错误的 `retryable` 必须保持不同：

- `repairable`：模型已经交付文件，但文件合同不合格；下一次尝试携带具体 Validator 错误；
- `retryable`：Session、Provider 或预算失败；下一次使用干净 Session，不注入内容修复指令。

### 12.11 为什么不采用更简单的方案

不只提高节点超时：

- q03 d2 已经证明 30 分钟不一定会自然收敛；
- 提高到 60 分钟只会扩大时间和 Token 成本。

不使用 `max_turns` 作为 Research 预算触发器：

- Hermes 达到上限后会要求模型生成文本总结；
- 文本总结不会自动写入声明的 `evidence.json`；
- Runtime 最终仍会因为缺失输出失败。

不在超时后继续使用原 Session：

- ACP Prompt 已被取消；
- 原 Session 可能正处于 stale model call；
- 独立 Finalizer 的工具、上下文和时间预算更容易限制。

不把 checkpoint 直接发布为 Evidence：

- checkpoint 是增量运行状态，不保证完整 Schema；
- 只有 Finalizer 生成并通过正式 Validator 的文件才能成为 Artifact。

## 13. 待实施：节点级时间预算

建议从全局 `node_timeout_seconds: 1800` 改成节点级配置：

| 节点 | 硬超时 | 瞬态最大尝试 |
|---|---:|---:|
| Scout | 720 秒 | 2 |
| Plan | 600 秒 | 2 |
| Research ①/② | 1140 秒 | 2 |
| Review ①/② | 720 秒 | 2 |
| Perspective ①/② | 300 秒 | 2 |
| SupplementPlanner | 300 秒 | 2 |
| ReportPlanner | 720 秒 | 2 |
| ReportWriter | 480 秒 | 2 |
| FinalReview Diagnostic | 600 秒 | 2 |
| FinalRepair | 480 秒 | 2 |
| FinalReview Recheck | 600 秒 | 2 |
| Python Script | 120 秒 | 1 |

节点配置优先级建议为：

```text
NodeSpec timeout
  > workflow step override
  > CLI 全局 node timeout
```

## 14. 待实施：ReportPlanner 输入压缩

q05 ReportPlanner 失败时，模型上下文约为 97k，重试过程中总输入继续膨胀。日志同时表明 100k 不是绝对失败线：q01 约 103k 成功，q07 约 164k 也成功。因此不设置简单硬 token 截断，而是在 ReportPlanner 前增加确定性 EvidenceIndexer：

```text
最终 evidence.json
  → EvidenceIndexer（确定性 Python）
  → evidence-index.json
  → ReportPlanner
```

索引只保留：

- dimension、claim、source ID；
- claim 文本、类型、证据强度；
- source 标题、URL、日期和类别；
- gaps、conflicts 和必要 writing context。

去除：

- 重复来源；
- 搜索过程；
- 原始网页长文本；
- 重复 claim；
- 不影响 Outline 决策的运行元数据。

建议目标：

```yaml
report_planner_budget:
  target_input_tokens: 100000
  warning_input_tokens: 120000
```

完整 Evidence 继续保留给 ContentTask 派生和 ReportWriter，压缩索引只服务于 Outline 规划。

## 15. 待实施：Hermes 与并发配置

时间预算由 Runtime 控制，Hermes 保留现有的安全上限，不用 `max_turns` 控制 Research 收口：

```yaml
agent:
  max_turns: 150

streaming:
  enabled: true

tool_loop_guardrails:
  warnings_enabled: true
  hard_stop_enabled: true
```

Hermes 达到 `max_turns` 后只生成文本总结，不保证写出 `evidence.json`，因此该参数不能替代 Runtime 的 15 分钟软超时和 ResearchFinalizer。

Benchmark 并发建议从 6 降到 4：

```yaml
execution:
  max_concurrency: 4
  run_timeout_seconds: 7200
```

降低并发不是 Provider 故障的根治方案，但可以降低多个长上下文 Research 同时请求 TokenHub 的瞬时压力。

## 16. 部分已实施：Benchmark 可观测性

强制收口已通过 `RUNTIME_FORCED_FINALIZE` warning 进入 Run Journal，汇总脚本已输出
Finalizer invocation 数、`retryable` attempt 数和强制收口次数。Provider 通用重试的分类指标仍待落地：

- `node_attempt_count`；
- `transient_failure_count`；
- `recovered_node_count`；
- `forced_finalize_count`；
- `partial_research_node_count`；
- `first_attempt_success_rate`；
- `eventual_success_rate`；
- 每个 scope 的首次错误和最终状态；
- 正常执行、重试等待、Finalizer 的耗时拆分。

示例：

```text
q02 completed
  scout_attempts=2
  recovered=true
  first_error=provider_broken_pipe

q03 completed
  research[d2]_forced_finalize=true
  coverage_status=partial
```

## 17. 推荐实施顺序

### 第一阶段：瞬态重试

1. 为 Harness/NodeResult 增加结构化错误码；
2. 增加 `retryable` outcome；
3. Driver 只重跑失败 scope；
4. 不在可重试错误后立即写 `run_finished: failed`；
5. 增加定向重试和成功 Artifact 保留测试。

直接覆盖 q02、q04、q06，并允许 q05 只重跑 ReportPlanner。

### 第二阶段：Research 强制收口（已实施）

1. 已增加 Research checkpoint 合同和 `_runtime` 保留路径；
2. 已增加 15 分钟软超时、3 分钟 Finalizer 和 19 分钟硬上限；
3. 已在 `invocation.json` 保存 invocation ID，并按 namespace 导出当前节点检索材料；
4. 已实现独立 `research-finalizer` invocation，不挂载 Search MCP；
5. 已在 Validator 通过后发布 Evidence 并记录 `RUNTIME_FORCED_FINALIZE` warning；
6. 已增加强制收口成功和 Finalizer 失败后最多两次 attempt 的定向测试。

直接覆盖 q03。

### 第三阶段：ReportPlanner 压缩与评测

1. 实现 EvidenceIndexer；
2. ReportPlanner 改读压缩索引；
3. Benchmark 汇总重试和强制收口指标；
4. 将并发降到 4；
5. 使用 q02–q06 做回归，再重跑 q01–q10。

## 18. 验收标准

### 确定性收口

- 同一组 Outline、Draft 和 Evidence 重复执行得到字节稳定的拼接结果；
- 非法引用、标题和 render-contract 必须稳定失败；
- 错误必须包含具体 `unit_id`，适用时包含 `element_id` 和 `claim_id`；
- FinalReview Recheck 的 preparer 只替换被点名 unit，且 Agent 不能修改预拼接产物；
- FinalReview 最多触发一次修复和一次复审。

### 瞬态重试

- 注入第一次 `Broken pipe`、第二次成功时，Run 最终完成；
- 并行 Research 中只重跑失败 dimension；
- 成功 dimension 的 Artifact hash 和 attempt 不发生变化；
- 认证、Validator 和 Script 错误不进入瞬态重试。

### Research 强制收口

- 软超时后不再发起新搜索；
- 有合法 checkpoint 时由 Finalizer 生成正式 Evidence，通过 Validator 后才发布；
- 无 checkpoint 或已核验材料不足时不得用搜索摘要造 claim，应重试当前 dimension；
- 未完成问题必须显式进入 gaps；
- Finalizer 的 `node_type` 不挂载 Search MCP；浏览器和委派由 Finalizer Prompt 明确禁止；
- 无法形成合法 Evidence 时进入当前 scope 的一次重试，不发布空产物。

### Benchmark

- 报告同时展示首次成功率和最终成功率；
- 能区分 Provider 故障、节点预算耗尽、Validator 修复和 FinalReview 修复；
- q02–q06 重新运行时，不再因为单次可恢复节点故障丢弃已成功的上游结果。

## 19. 不建议的做法

- 只把 `node_timeout_seconds` 从 1800 提高到 3600；
- 任一 dimension 失败后重跑整个 Query；
- 把 `max_turns` 直接降到 50；
- 在没有 Finalizer 的情况下单独降低 Hermes turn 上限；
- 对认证、余额、Schema 或 Python 错误进行无限重试；
- 让 FinalReview 自由重写整篇报告；
- 为了“润色”在 Stitcher 和 Render 之间固定增加一个全局 Agent；
- 强制输出时用模型猜测补齐没有来源支持的 claim。

## 20. 当前结论

此前改造已经把 Heavy 的最终收口从“Agent 自由拼接和凭感觉检查”变成：

```text
按 unit 写作
  → Python 合同检查
  → Python 确定性拼接
  → Agent 只做语义诊断
  → Python 定位修复目标
  → Agent 只修指定 unit
  → Python 重新拼接和引用渲染
```

q02–q06 说明下一阶段的主要问题已经不在最终格式收口，而在长链路执行可靠性：Provider 瞬态连接、Research 不收敛和大上下文规划。Research 不收敛现在已由纯时间预算和受限 Finalizer 处理；下一步应实现 Provider 通用瞬态重试，再增加 ReportPlanner 输入压缩。
