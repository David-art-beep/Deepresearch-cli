# DeepResearch CLI q01–q10 Quick/Normal 测试报告

> 报告日期：2026-08-27  
> 测试范围：q01–q10，每个 Query 分别运行 Quick 和 Normal，共 20 个 Run  
> 执行环境：本机隔离 `HERMES_HOME`，Hermes Harness，Markdown 输出，`formal_report` 目标格式

## 1. 执行结论

本次将 2026-08-25 已完成的 q01–q03 Quick/Normal 历史结果，与
2026-08-26 完成的 q04–q10 Quick/Normal 当前链路结果合并统计。

- 20/20 Run 完成，成功率 100%；
- 没有 Run 失败、跳过或非零退出；
- 共执行 86 个 Agent attempt；
- 共发生 3,052 次工具调用，其中 69 次工具级失败，失败率约 2.26%；
- 工具级错误均被搜索降级、模型自修复或 API 瞬态重试吸收；
- 共统计到 817 个 Evidence URL；
- 所有 Run 的顺序耗时合计为 382.42 分钟，约 6 小时 22 分钟。

本报告评价的是执行可靠性、资源消耗和阶段耗时，不评价报告内容是否正确或达到业务验收标准。Quick/Normal 当前没有 Heavy 模式的 FinalReview 语义质量 verdict，因此 `completed` 只表示工作流成功交付报告。

## 2. 测试批次与可比性

| 批次 | Query | 日期 | Run ID 前缀 | 说明 |
| --- | --- | --- | --- | --- |
| 历史基线 | q01–q03 | 2026-08-25 | `bench-current-cli-3mode-local-*` | 本机隔离 Hermes；运行时和 Search 适配仍处于调整阶段 |
| 当前链路 | q04–q10 | 2026-08-26 | `bench-finalrepair-headless-*` | 本机隔离 Hermes；API stale 阈值固定为 300 秒，启用当前瞬态重试链路 |

两批使用相同的 Quick/Normal 拓扑和相同统计脚本，但并非完全相同的代码快照和运行时参数，因此：

- 合并结果适合做整体稳定性与容量画像；
- q01–q03 与 q04–q10 的绝对耗时不应被视为严格版本 A/B；
- q01 Quick 曾使用 90 秒 stale 阈值，q03 Quick 使用 240 秒阈值，q04–q10 使用 300 秒阈值；
- `search_provider_count=0` 不等于没有搜索。q01 Quick、q09 Quick 等 Run 使用了直接网页工具或未被 Search SQLite 完整投影的路径，仍然生成了 Evidence URL。

## 3. Query 范围

| Query | 类型 | 主题摘要 |
| --- | --- | --- |
| q01 | 宏观经济 | 联合国、IMF、世界银行对 2026 年全球增长预测比较 |
| q02 | 文化遗产 | 北京中轴线历史演变、15 处遗产构成与规划理念 |
| q03 | 金融市场 | 2005–2025 年全球及中国央行黄金购买趋势 |
| q04 | 软件工程 | 传统现代软件工程与 AI 原生组织比较 |
| q05 | 市场研究 | 2026 年全球 AI 生产力工具市场与北美运营策略 |
| q06 | 医疗器械 | 可穿戴设备的脑卒中风险监测与辅助预警 |
| q07 | AI 模型生态 | 中医 AI 大模型技术路线、治理与评测比较 |
| q08 | 跨境投资 | 中国企业在孟加拉国投资与工程施工 |
| q09 | 气候数据 | 8 国 GDP、CO₂ 排放、碳转移与能源转型 |
| q10 | 公司金融 | 英伟达财务、估值驱动、风险与投资情景 |

## 4. 汇总指标

| 模式 | 成功 | 中位耗时 | 平均耗时 | Agent attempt | 平均 Agent | 工具调用/失败 | 平均搜索 Provider | Search API 调用 | Evidence URL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Quick | 10/10 | 9.56 分钟 | 11.29 分钟 | 20 | 2.0 | 461/15 | 6.2 | 83 | 130 |
| Normal | 10/10 | 23.16 分钟 | 26.95 分钟 | 66 | 6.6 | 2,591/54 | 7.8 | 388 | 687 |
| 合计 | **20/20** | — | — | **86** | — | **3,052/69** | — | **471** | **817** |

Normal 相比 Quick 的主要增量来自 Plan 和并发多维 Research：

- 平均 Agent 从 2.0 增至 6.6；
- 工具调用总量约为 Quick 的 5.62 倍；
- Evidence URL 总量约为 Quick 的 5.28 倍；
- 中位耗时约为 Quick 的 2.42 倍，而不是按 Agent 数线性增长，说明 Research 并发有效压缩了墙钟时间。

## 5. 单 Run 结果

`工具/失败`中的失败是工具调用级错误，不是 Run 失败。`Provider`是 Search 持久层记录的 distinct provider 数。

| Query | 模式 | 状态 | 耗时（分） | Agent | 工具/失败 | Provider | Search API | Evidence URL |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| q01 | Quick | completed | 9.91 | 2 | 28/1 | 0 | 0 | 10 |
| q01 | Normal | completed | 24.47 | 5 | 153/1 | 4 | 4 | 25 |
| q02 | Quick | completed | 6.96 | 2 | 37/1 | 5 | 5 | 10 |
| q02 | Normal | completed | 20.75 | 7 | 213/7 | 6 | 58 | 49 |
| q03 | Quick | completed | 28.53 | 2 | 64/1 | 5 | 5 | 16 |
| q03 | Normal | completed | 65.84 | 7 | 298/10 | 6 | 20 | 64 |
| q04 | Quick | completed | 8.08 | 2 | 45/3 | 10 | 15 | 18 |
| q04 | Normal | completed | 20.87 | 7 | 297/5 | 10 | 63 | 100 |
| q05 | Quick | completed | 9.40 | 2 | 58/1 | 11 | 18 | 15 |
| q05 | Normal | completed | 23.07 | 7 | 314/4 | 13 | 40 | 102 |
| q06 | Quick | completed | 13.44 | 2 | 73/0 | 12 | 13 | 22 |
| q06 | Normal | completed | 22.84 | 7 | 334/5 | 14 | 58 | 123 |
| q07 | Quick | completed | 10.09 | 2 | 45/2 | 8 | 14 | 11 |
| q07 | Normal | completed | 24.57 | 7 | 339/7 | 9 | 84 | 60 |
| q08 | Quick | completed | 9.09 | 2 | 43/2 | 9 | 10 | 14 |
| q08 | Normal | completed | 27.16 | 6 | 243/4 | 9 | 31 | 75 |
| q09 | Quick | completed | 7.65 | 2 | 28/2 | 0 | 0 | 9 |
| q09 | Normal | completed | 16.74 | 6 | 111/6 | 4 | 16 | 30 |
| q10 | Quick | completed | 9.72 | 2 | 40/2 | 2 | 3 | 5 |
| q10 | Normal | completed | 23.25 | 7 | 289/5 | 3 | 14 | 59 |

## 6. 各阶段耗时与调用量

Active 时间按同一阶段并发实例的时间区间并集计算；累计 Agent 时间是所有实例耗时之和。

| 模式 | 阶段 | Run 数 | 中位 Active | 中位累计 Agent | 平均实例数 | 平均工具调用 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Quick | Research | 10 | 5.94 分钟 | 5.94 分钟 | 1.0 | 40.6 |
| Quick | ReportWriter | 10 | 2.65 分钟 | 2.65 分钟 | 1.0 | 5.5 |
| Quick | Render | 10 | 约 0 分钟 | 约 0 分钟 | 1.0 | 0.0 |
| Normal | Plan | 10 | 2.25 分钟 | 2.25 分钟 | 1.0 | 5.5 |
| Normal | Research | 10 | 14.71 分钟 | 46.04 分钟 | 4.4 | 241.1 |
| Normal | ReportWriter | 10 | 5.21 分钟 | 5.21 分钟 | 1.2 | 12.5 |
| Normal | Render | 10 | 约 0 分钟 | 约 0 分钟 | 1.0 | 0.0 |

Normal Research 的中位 Active 时间为 14.71 分钟，而中位累计 Agent 时间为 46.04 分钟，说明多个研究维度确实在并发运行。墙钟压缩比例约为 3.13 倍，和实际平均 4.4 个 Research 实例相符。

## 7. 长尾与异常分析

### 7.1 q03 是主要耗时长尾

q03 黄金市场数据分析明显高于其他 Query：

- Quick：28.53 分钟，其中 Research 20.50 分钟、ReportWriter 8.03 分钟；
- Normal：65.84 分钟，其中 Research Active 51.36 分钟、累计 Agent 105.81 分钟，ReportWriter 11.94 分钟；
- 其余 9 个 Quick 的耗时均不超过 13.44 分钟；
- 其余 9 个 Normal 的耗时均不超过 27.16 分钟。

主要原因是该 Query 同时要求 2005–2025 长时间序列、全球与中国口径对齐、关键转折点和市场影响，需要更多数据抽取、清洗与表格计算。q03 Quick 还触发过一次 240 秒 stale watchdog，连接被主动关闭后自动重试成功。

### 7.2 API stale 与 Broken pipe

本次 20 个成功 Run 中观察到两类典型事件：

- q01 Quick：旧配置下 90 秒 stale 阈值连续主动断开请求，日志表现为 `[Errno 32] Broken pipe`，第 3 次请求成功；
- q03 Quick：240 秒 stale 后主动断开并重试成功；
- q08 Normal ReportWriter：当前配置下先遇到两次 HTTP 500，随后一次请求静默满 300 秒被 watchdog 断开；重试成功输出 17,634 tokens 并写入 `draft.md`。

这些 Broken pipe 是 watchdog 强制关闭 stale TCP 连接后的表象，不等同于“上下文太长”。q08 Normal 的 stale 日志中上下文仅约 37.6k tokens，也证明它主要是上游请求无响应。

### 7.3 搜索后端降级

多项 Run 出现：

- 本机未安装 `ddgs`；
- Firecrawl/Exa 返回 HTTP 429；
- Exa keyless rescue 返回无法识别的 MCP response shape；
- 单个网页无法抽取或只返回部分批次结果。

Search 层会尝试 keyless rescue 或其他 provider；Agent 也会使用已成功返回的来源继续生成 Evidence。上述问题造成 69 次工具级失败，但没有造成 Run 失败。

### 7.4 数据处理自修复

q02、q03、q07、q08、q09、q10 中出现过裸 `python` 不存在、pandas 字段不匹配、临时解析脚本 Traceback 或补丁定位失败。Agent 通常在下一轮改用 `python3`、调整字段或替换处理方式，最终均完成产物。

这说明工具错误目前具有一定自愈能力，但裸 `python` 错误是可由提示或执行环境预配置消除的无效调用，应继续治理。

## 8. 稳定性判断

### 8.1 已验证能力

- Quick 和 Normal 在 10 类 Query 上均达到 100% 最终完成率；
- Normal 的多领域 Research 并发有效，累计 Agent 时间没有线性转化为墙钟时间；
- API HTTP 500、stale、Broken pipe 可以被瞬态重试吸收；
- 搜索 provider 限流和单来源失败不会直接击穿工作流；
- 确定性 Render 在全部 20 个 Run 中完成，没有成为性能瓶颈。

### 8.2 仍需关注

- q03 表明数据密集型 Query 仍可能形成 50 分钟以上的 Normal Research 长尾；
- 当前 300 秒 stale 阈值能降低误杀，但单次失败最多会先消耗 5 分钟，再进入重试；
- `ddgs` 缺失持续制造 warning 和无效调用，建议补依赖或明确关闭该后端；
- Search provider 统计对直接网页工具覆盖不完整，Provider=0 不能用于判断是否搜索；
- Quick/Normal 缺少 FinalReview verdict，本报告不能证明内容质量达标；
- 两批代码快照不同，后续正式对比应在同一 commit、同一 Hermes 配置和同一 API stale 阈值下重跑 q01–q10。

## 9. 建议的下一轮验收

1. 固定 commit、Hermes 版本、模型、`HERMES_HOME`、stale 阈值和搜索 provider 配置；
2. q01–q10 Quick/Normal 各重复至少 3 次，报告中位数、P90 和成功率置信区间；
3. 对 q03 单独增加数据型任务预算和长输出观测，区分搜索、计算和写作长尾；
4. 补齐 `ddgs` 或从工具路由中移除不可用 backend；
5. 为 Quick/Normal 增加轻量确定性质量指标，例如标题合同、引用合法性、引用覆盖率和报告非空；
6. 若要比较模式质量，引入同一套离线内容评分或人工盲评，不使用 Evidence URL 数量代替质量。

## 10. 数据来源与统计口径

历史 q01–q03 明细：

- `benchmarks/results-local/runs.csv`
- `benchmarks/results-local/stages.csv`
- `benchmarks/results-local/tools.csv`
- `runs/bench-current-cli-3mode-local-q{01..03}-{quick,normal}-r01/`

当前 q04–q10 明细：

- `output/runs.csv`
- `output/stages.csv`
- `output/tools.csv`
- `benchmarks/results-local/runner-state.json`
- `runs/bench-finalrepair-headless-q{04..10}-{quick,normal}-r01/`

统计定义：

- 总耗时：`run.json.created_at` 到 `run_finished.recorded_at`；
- Agent 数：Node Spec 中 `kind=agent` 的实际 attempt 数，Script Node 不计入；
- 工具调用：ACP 投影中唯一 `toolCallId` 的调用数；
- 工具失败：工具调用的最终状态为 failed，不等于节点或 Run 失败；
- Search provider：本 Run Search SQLite 中实际调用或缓存复用的 distinct provider；
- Evidence URL：正式 Artifact JSON 中出现的唯一 HTTP(S) URL；
- 阶段 Active：同阶段并发实例执行区间的并集；
- 阶段累计 Agent：该阶段全部 Agent 实例耗时之和。
