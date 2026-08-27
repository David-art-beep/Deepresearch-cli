# DeepResearch CLI v0.1 Heavy E2E 测试结果

> 历史记录：本文只描述 2026-08-11 完成的指定 Run，保留当时的实测数据和结论，不代表
> 当前 Bundle 0.9 / Graph 0.3.0 / Policy 0.2.0 / Selector 0.3.0 基线已经通过真实 Hermes 验收。
> 当前 Loader 不接受旧控制面或 Prompt 快照；该 Run 不应直接 resume，也不能用作当前版本发布门禁。
>
> 统计风格参考 `DRB-hermes/benchmarks/2026-07-29-six-model-three-mode/TESTING_GUIDE.md`。
> 本文先记录可复核的运行效率与调用统计，再记录 Graph 和内容质量结果。

## 1. 测试摘要

| 项目 | 结果 |
| --- | --- |
| Run ID | `run-20260810T160940Z-ea25900801` |
| 测试时间 | 2026-08-11 00:09:41–00:50:26 CST |
| Query | 评估 Python 3.14 free-threaded build 是否适合生产采用 |
| 模式 | `heavy` |
| 语言 / 格式 | `zh-CN` / `report` |
| Harness / 模型 | Hermes Agent v0.19.0 / `gpt-5.5` |
| Run 状态 | `completed` |
| 总 Wall time | **40.76 分钟** |
| Agent 活跃并集 | **38.47 分钟** |
| Agent 累计工作量 | **84.44 Agent-minutes** |
| 平均并行度 | **2.20×** |
| Hermes Agent | **34** 个 |
| API 调用 | **261** 次 |
| 工具调用完成记录 | **603** 次 |
| 工具错误结果 | **42** 次，错误率 **7.0%** |
| Prompt tokens（含 cache read） | **19,955,786** |
| Output tokens | **313,903** |
| Graph 执行 | **PASS** |
| 内容质量门 | **FAIL**：FinalReview 为 `revise` |

一句话结论：这次 Heavy E2E 在 **40 分 45.68 秒**内完整跑完 35 个节点实例；
Graph、补研回流和文件产物链路都可运行，但审核结论没有参与路由，因此
`completed` 不能被解释为最终报告已通过内容验收。

## 2. 测试任务与环境

### 2.1 完整任务

> 截至 2026-08-10，评估 Python 3.14 free-threaded build 是否适合生产采用。
> 研究计划必须覆盖四个可独立取证且来源入口不同的研究任务：
> （1）正式版默认状态、安装/构建方式与运行时 GIL 开关；
> （2）解释器线程安全机制、C API/ABI 与扩展模块适配要求；
> （3）单线程开销、多线程收益、内存成本及可复核公开基准；
> （4）PyPI、conda、科学计算生态、wheel 兼容状态与公开生产采用案例。
> 每个维度都要交叉核对一手资料和独立公开资料，明确冲突、证据缺口和不可外推边界；
> 最终输出中文研究报告，包含生产采用判断矩阵和分场景建议，不能只做摘要。

### 2.2 环境

| 环境项 | 值 |
| --- | --- |
| CLI | `deepresearch-cli 0.1.0` |
| CLI Python | `3.10.20` |
| 操作系统 | macOS 26.3，Apple Silicon `arm64` |
| uv | `0.11.25` |
| Harness | Hermes Agent v0.19.0（2026.7.20） |
| Hermes Python | `3.11.15` |
| OpenAI SDK | `2.24.0` |
| 模型 | `gpt-5.5` |
| Billing provider | `custom` |
| API endpoint | `https://tokenhub.sensetime.com/v1` |
| Hermes profile | 未显式指定 |
| Agent attempt timeout | 1800 秒 / attempt |
| Hermes native sessions | 34 |
| Hermes ACP execution processes | 8 |

Hermes 数据库中的 `estimated_cost_usd=0.0` 不能解释为本次运行免费；自定义 endpoint
没有返回可用价格信息，因此本文不报告成本。

Run State 没有保存 Git commit，所以本次 Run 无法仅凭 `run.json` 与某个源码 commit
建立精确绑定。运行事实以 Run Journal、Artifact 和 Hermes session 数据为准。

## 3. 统计口径

本节沿用旧 DRB-hermes benchmark 的思路，并针对当前 CLI 没有 Controller/root Hermes
session 的情况作一处调整。

### 3.1 时间

- **总 Wall time**：`run.created_at` 到最终 `report.md` 写入时间，表示用户实际等待时间。
- **Agent 活跃并集**：34 个 Hermes session 的消息时间区间取并集，重叠只计算一次。
- **Agent 累计工作量**：34 个 session 各自活跃时长直接求和，不消除并行重叠。
- **阶段活跃时长**：同一阶段内所有 Agent 区间的并集。
- **平均单 Agent 时长**：阶段累计工作量除以 Agent 数量。
- **并行度**：`阶段累计工作量 ÷ 阶段活跃时长`。
- **非 Agent Wall 残差**：`总 Wall time - Agent 活跃并集`。它混合 ACP 进程启停、
  CLI 节点切换、Validator、Artifact publish、阶段间隙和内部 Render，不能直接叫作
  “Controller 时间”或“纯静默时间”。

Journal 当前没有逐事件时间戳，Render 又不是 Hermes Agent，因此无法独立复原 Render
的精确耗时。本文不把它伪记为 0 秒。

### 3.2 工具、API 与 Token

- **工具调用完成记录**：统计 Hermes `messages` 表中全部 `role=tool` 行，包含 active
  与 compacted 记录；每一行代表一次工具调用结果。
- **工具错误结果**：沿用旧 benchmark 的结果体错误分类器，对序列化工具结果识别错误。
- **ACP failed event**：只统计 ACP 轨迹中明确标为 `status=failed` 的更新；它与结果体
  错误分类不是同一口径。
- **API 调用与 Token**：按 34 个 Hermes native session 汇总。
- **Input tokens**：数据库的非 cache 输入；`cache_read_tokens` 单独列出。
- **Prompt tokens（含 cache）**：`input_tokens + cache_read_tokens`。

`sessions.tool_call_count` 只保留了 562 条 active 调用；另有 41 条工具结果已经进入
compacted history。故本报告使用 **603**，不使用 562 作为最终工具调用数。

## 4. 总体运行效率

| 指标 | 秒 | 分钟 | 说明 |
| --- | ---: | ---: | --- |
| 总 Wall time | 2,445.680 | **40.761** | 用户实际等待时间 |
| Agent 活跃并集 | 2,308.474 | **38.475** | 占 Wall time 94.39% |
| 非 Agent Wall 残差 | 137.206 | **2.287** | 占 Wall time 5.61% |
| Agent 累计工作量 | 5,066.559 | **84.443** | 并行 Agent 时间之和 |
| 平均并行度 | — | **2.195×** | 累计工作量 / 活跃并集 |

其他执行规模：

| 指标 | 数量 |
| --- | ---: |
| NodeInstance 总数 | 35 |
| Hermes Agent 节点 | 34 |
| Internal Render 节点 | 1 |
| 成功节点 / 失败节点 | 35 / 0 |
| Journal 事件 | 84 |
| `node_attempt_started` | 35 |
| `node_attempt_finished` | 35 |
| `transition_committed` | 14 |
| 正式 ArtifactRef | 53 |

## 5. 分阶段耗时

| 阶段 | Agent 数 | 活跃并集（分） | 累计工作量（Agent-min） | 平均单 Agent（分） | 最短–最长（分） | 并行度 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Scout | 1 | 2.71 | 2.71 | 2.71 | 2.71–2.71 | 1.00× |
| Plan | 1 | 1.23 | 1.23 | 1.23 | 1.23–1.23 | 1.00× |
| Research：初研 | 4 | **10.98** | **27.25** | 6.81 | 4.48–10.97 | 2.48× |
| Review：初研 | 4 | 3.68 | 8.50 | 2.12 | 1.43–3.68 | 2.31× |
| Perspective | 4 | 1.63 | 5.11 | 1.28 | 0.91–1.63 | 3.13× |
| SupplementPlanner | 4 | 1.28 | 4.63 | 1.16 | 1.07–1.28 | **3.61×** |
| Research：补研 | 4 | **5.11** | **13.92** | 3.48 | 2.54–5.10 | 2.72× |
| Review：补研后 | 4 | 3.55 | 9.60 | 2.40 | 1.63–3.54 | 2.70× |
| ReportPlanner | 1 | 3.68 | 3.68 | 3.68 | 3.68–3.68 | 1.00× |
| ReportWriter | 5 | 1.59 | 4.80 | 0.96 | 0.68–1.21 | 3.01× |
| Stitcher | 1 | 0.84 | 0.84 | 0.84 | 0.84–0.84 | 1.00× |
| FinalReview | 1 | 2.17 | 2.17 | 2.17 | 2.17–2.17 | 1.00× |
| Render | 内部节点 | — | — | — | — | — |
| **合计** | **34 Agent** | **38.47** | **84.44** | **2.48** | — | **2.20×** |

主要耗时集中在两轮 Research：初研与补研合计占 Agent 活跃时间约 **41.8%**，
但占累计 Agent 工作量约 **48.8%**。单个最慢 Agent 是初研 `Research:d4`，耗时
10.97 分钟，其中包含一次 300 秒后终止的 helper script。

## 6. 分阶段调用量

| 阶段 | 工具调用 | 错误结果 | API 调用 | Input tokens（不含 cache） | Output tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| Scout | 16 | 0 | 6 | 56,434 | 12,222 |
| Plan | 5 | 0 | 3 | 32,034 | 6,397 |
| Research：初研 | **156** | **15** | **51** | **1,849,570** | **57,144** |
| Review：初研 | 67 | 3 | 42 | 1,029,078 | 28,504 |
| Perspective | 31 | 0 | 19 | 256,159 | 25,471 |
| SupplementPlanner | 34 | 3 | 19 | 422,725 | 25,398 |
| Research：补研 | **141** | **8** | **38** | **1,674,831** | **68,602** |
| Review：补研后 | 76 | 8 | 33 | 1,258,658 | 36,524 |
| ReportPlanner | 9 | 1 | 7 | 190,339 | 17,723 |
| ReportWriter | 34 | 3 | 27 | 716,141 | 22,044 |
| Stitcher | 11 | 0 | 4 | 67,956 | 4,828 |
| FinalReview | 23 | 1 | 12 | 99,141 | 9,046 |
| **合计** | **603** | **42** | **261** | **7,653,066** | **313,903** |

两轮 Research 共调用工具 **297 次**，占全部工具调用的 **49.3%**；共发起 API
调用 **89 次**，占全部 API 调用的 **34.1%**。

## 7. 工具调用明细

### 7.1 按工具类型

| 工具 | 调用次数 | 占比 | 错误结果 | 错误率 |
| --- | ---: | ---: | ---: | ---: |
| `read_file` | 157 | 26.0% | 5 | 3.2% |
| `web_search` | 144 | 23.9% | 0 | 0.0% |
| `web_extract` | 91 | 15.1% | 11 | 12.1% |
| `skill_view` | 53 | 8.8% | 3 | 5.7% |
| `search_files` | 47 | 7.8% | 5 | 10.6% |
| `execute_code` | 45 | 7.5% | 10 | 22.2% |
| `write_file` | 35 | 5.8% | 1 | 2.9% |
| `todo` | 21 | 3.5% | 0 | 0.0% |
| `terminal` | 10 | 1.7% | 7 | 70.0% |
| **合计** | **603** | **100%** | **42** | **7.0%** |

`web_search + web_extract` 共 235 次，占总工具调用 **39.0%**。`read_file` 为最大单项，
主要来自 Agent 读取 Prompt 指定输入、搜索缓存正文、Evidence 和中间产物。

### 7.2 两种错误统计为什么不同

| 口径 | 数量 | 说明 |
| --- | ---: | --- |
| Benchmark-compatible 工具错误结果 | **42** | 从完整 `role=tool` 结果体识别，包含 compacted history |
| ACP `status=failed` 更新 | **23** | 只计算 ACP 明确标记 failed 的实时事件 |

23 次 ACP failed event 的分布为：

| ACP 工具类别 | failed 次数 |
| --- | ---: |
| `execute` | 15 |
| `read` | 3 |
| `search` | 5 |
| **合计** | **23** |

二者不矛盾：部分工具结果虽然在 ACP 层完成返回，但返回正文包含命令失败、读取失败或
业务错误；旧 benchmark 的结果体分类器会把它们计为错误，ACP 状态计数不会。

## 8. API 与 Token

| 指标 | 数量 |
| --- | ---: |
| Hermes native sessions | 34 |
| API calls | **261** |
| 平均 API calls / Agent | 7.68 |
| Input tokens（不含 cache read） | **7,653,066** |
| Cache read tokens | **12,302,720** |
| Prompt tokens（含 cache read） | **19,955,786** |
| Output tokens | **313,903** |
| Reasoning tokens | **67,337** |
| Hermes `totalTokens` | **20,269,689** |
| 平均 `totalTokens` / API call | 77,662 |

Cache read 占全部 Prompt tokens 的 **61.65%**。`reasoning_tokens` 是输出使用量中的细分
字段，不应再次加到 `totalTokens` 上。Hermes 的 `totalTokens` 等于含 cache 的 Prompt
tokens 加 Output tokens。

## 9. 单 Agent 耗时与调用量

### 9.1 Research

| 轮次 | 维度 | 活跃时长（分） | 工具调用 | 工具错误 | API 调用 |
| --- | --- | ---: | ---: | ---: | ---: |
| 初研 | d1 | 6.57 | 43 | 6 | 13 |
| 初研 | d2 | 5.23 | 33 | 2 | 11 |
| 初研 | d3 | 4.48 | 38 | 6 | 12 |
| 初研 | d4 | **10.97** | 42 | 1 | 15 |
| 补研 | d1 | 2.65 | 30 | 1 | 7 |
| 补研 | d2 | 3.63 | 23 | 4 | 14 |
| 补研 | d3 | 2.54 | 27 | 0 | 7 |
| 补研 | d4 | **5.10** | **61** | 3 | 10 |

`Research:d4` 在初研与补研中都是同轮最慢实例；补研 d4 还产生了全体 Research 中
最高的单实例工具调用数 61。

### 9.2 Review

| 轮次 | 维度 | 活跃时长（分） | 工具调用 | 工具错误 | API 调用 |
| --- | --- | ---: | ---: | ---: | ---: |
| 初研 | d1 | 3.68 | 37 | 1 | 26 |
| 初研 | d2 | 1.48 | 8 | 0 | 5 |
| 初研 | d3 | 1.91 | 12 | 1 | 6 |
| 初研 | d4 | 1.43 | 10 | 1 | 5 |
| 补研后 | d1 | 2.75 | 27 | 3 | 11 |
| 补研后 | d2 | 1.63 | 11 | 2 | 7 |
| 补研后 | d3 | 1.68 | 13 | 1 | 6 |
| 补研后 | d4 | 3.54 | 25 | 2 | 9 |

### 9.3 其他 Agent

| 阶段 | 实例 | 活跃时长（分） | 工具调用 | API 调用 |
| --- | --- | ---: | ---: | ---: |
| Scout | singleton | 2.71 | 16 | 6 |
| Plan | singleton | 1.23 | 5 | 3 |
| Perspective | d1 | 1.63 | 13 | 9 |
| Perspective | d2 | 0.91 | 6 | 3 |
| Perspective | d3 | 1.44 | 6 | 4 |
| Perspective | d4 | 1.12 | 6 | 3 |
| SupplementPlanner | d1 | 1.07 | 9 | 6 |
| SupplementPlanner | d2 | 1.21 | 9 | 4 |
| SupplementPlanner | d3 | 1.28 | 9 | 5 |
| SupplementPlanner | d4 | 1.08 | 7 | 4 |
| ReportPlanner | singleton | 3.68 | 9 | 7 |
| ReportWriter | u1 | 1.02 | 6 | 5 |
| ReportWriter | u2 | 1.21 | 9 | 7 |
| ReportWriter | u3 | 1.00 | 10 | 7 |
| ReportWriter | u4 | 0.89 | 5 | 4 |
| ReportWriter | u5 | 0.68 | 4 | 4 |
| Stitcher | singleton | 0.84 | 11 | 4 |
| FinalReview | singleton | 2.17 | 23 | 12 |

## 10. Graph 与产物结果

本次实际路径：

```text
Scout
→ Plan
→ Research[d1..d4, initial]
→ Review[d1..d4, initial]
→ Perspective[d1..d4]
→ SupplementPlanner[d1..d4]
→ Research[d1..d4, supplement round 1]
→ Review[d1..d4, post-supplement]
→ ReportPlanner
→ ReportWriter[u1..u5]
→ Stitcher
→ FinalReview
→ Render
→ END
```

| 能力 | 结果 |
| --- | --- |
| 四维 Research fan-out | PASS |
| 分组 Join | PASS |
| Review / Perspective 并行分支 | PASS |
| 定向补研 | PASS |
| 补研后回到 Review | PASS |
| 五章节并行写作 | PASS |
| Stitcher / Render | PASS |
| Review / FinalReview 质量路由 | **FAIL** |

最终 Evidence 规模：

| 维度 | 最终 claims | 最终 sources | 补研项 | 延后项 |
| --- | ---: | ---: | ---: | ---: |
| d1：状态、安装、构建和 GIL 开关 | 19 | 21 | 2 | 7 |
| d2：线程安全、C API/ABI 和扩展适配 | 15 | 15 | 5 | 8 |
| d3：性能、内存和公开基准 | 16 | 18 | 5 | 8 |
| d4：生态兼容和生产案例 | 27 | 35 | 6 | 10 |
| **合计** | **77** | **89** | **18** | **33** |

最终报告规模：

| 指标 | 结果 |
| --- | ---: |
| Markdown 行数 | 188 |
| Unicode 字符数 | 28,109 |
| 文件字节数 | 44,099 |
| 唯一引用 URL | 68 |
| Content units | 5 |

## 11. 审核与质量结论

### 11.1 Review verdict

| 维度 | 初研 Review | 补研后 Review |
| --- | --- | --- |
| d1 | `pass` | `pass` |
| d2 | `revise` | `pass` |
| d3 | `revise` | `pass` |
| d4 | `revise` | `revise` |

最终有效 validation warning 有 3 条：

| 维度 | Claim | 规则 | 问题 |
| --- | --- | --- | --- |
| d3 | `d3.c6` | V041 | interpretive claim 只有 1 个独立信源 |
| d3 | `d3.c16` | V040 | factual claim 没有 primary/secondary 质量来源 |
| d4 | `d4.c10` | V041 | interpretive claim 只有 1 个独立信源 |

### 11.2 FinalReview

FinalReview 输出：

```text
VERDICT: revise
```

两个硬伤：

1. AI/ML 场景矩阵写入 OpenCV，但当前 content unit 的 `evidence_subset` 没有对应 claim。
2. “公开生产案例不足”影响最终采用判断，却没有脚注，并混入未路由到该片段的具名材料。

当前 Policy 不解析 Review 或 FinalReview 的 verdict。节点只要产出非空 Markdown，attempt
就被记为 `succeeded`，因此 `revise` 仍会进入后续节点并最终标记 Run 为 `completed`。

最终判定：

```text
Graph execution:      PASS
Artifact pipeline:    PASS
Supplement loop:      PASS
Report rendering:     PASS
Content quality gate: FAIL
Overall product E2E:  FAIL
```

## 12. 主要运行问题

### P0：审核结论不参与路由

`Review/FinalReview` 目前只产生 Markdown 诊断，没有结构化 decision Artifact；Policy
也没有 `pass | revise | reject` 路由事实。因此执行完成和内容验收通过被混成同一个状态。

### P1：工具失败增加耗时和不确定性

34 个 Hermes session 最终全部成功，但轨迹存在 42 个错误结果，其中一次 d4 初研 helper
运行 300 秒后被终止。其他错误主要包括：

- 搜索 helper 的 Python 兼容或依赖问题；
- `rg` 把 `--disable-gil`、`-X` 识别为自身参数；
- 读取尚未生成的输出文件；
- helper 对读文件返回结构解析失败；
- ReportPlanner 自检失败后重写。

这些错误都被 Agent 通过替代路径恢复，没有造成 Node failure，但会增加 Wall time、API 调用
和信源覆盖的不确定性。

### P1：运行指标尚未成为 CLI 原生输出

本报告需要把 Run 文件、ACP 事件和 Hermes `state.db` 联合统计才能得到正确的活跃并集、
compacted 工具调用和 Token。CLI 当前没有直接产出 benchmark summary，后续不同测试之间
容易因统计口径不同而失去可比性。

## 13. 下一轮回归建议

下一轮仍按本报告口径记录，至少比较以下指标：

1. 总 Wall time、Agent 活跃并集、累计工作量和并行度；
2. 阶段级耗时、工具调用、错误结果、API 与 Token；
3. Research / Review 每个实例的耗时与工具调用；
4. active 与 compacted 工具记录是否都被计入；
5. Review `revise` 是否阻断 ReportPlanner；
6. FinalReview `revise` 是否阻断 Render；
7. Graph terminal state 与 content quality state 是否分开显示。

## 14. 证据位置

本次运行证据位于：

```text
runs/run-20260810T160940Z-ea25900801/
```

关键证据：

- `run.json`：固化的 RunContext、Graph、Policy、Prompt 和 Input Selector 快照；
- `journal.jsonl`：84 条权威工作流事件；
- `attempts/*/attempt-1/harness.json`：34 个 native session ID 与 Token usage；
- `attempts/*/attempt-1/acp-events.jsonl`：工具调用轨迹；
- `attempts/*/attempt-1/validation.json`：Validator 结果；
- `artifacts/*/attempt-1/`：正式不可变产物；
- `artifacts/finalreview-b4c11a00bb735b26/attempt-1/final_review.md`：最终审核；
- `artifacts/render-392d553705085e94/attempt-1/report.md`：最终报告；
- `~/.hermes/state.db`：session、API、Token 和含 compacted history 的工具结果。

`runs/` 为 gitignored 本地运行证据。本文可以进入仓库，但若要让其他人复算全部统计，
还需要将对应 Run 目录和 Hermes session 数据做脱敏归档。
