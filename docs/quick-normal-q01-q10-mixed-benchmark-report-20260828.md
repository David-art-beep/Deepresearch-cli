# DeepResearch CLI q01–q10 Quick/Normal 混合批次测试报告

> 报告日期：2026-08-28
> 测试范围：q01–q10 Quick 共 10 个 Run，q01–q10 Normal 共 10 个 Run
> 交付配置：Hermes Harness、Markdown、`formal_report`

## 1. 执行结论

- 20/20 Run 完成，Run 成功率 100%。
- 共执行 86 个 Agent attempt、3,163 次工具调用。
- 59 次工具调用最终标记为失败，工具级失败率约 1.87%，未造成 Run 失败。
- 统计到 632 次 Search Provider API 调用和 820 个 Evidence URL。
- 20 个 Run 顺序墙钟耗时合计 314.64 分钟，约 5 小时 15 分钟。
- 最新 q01–q03 Normal 均在 18 分钟内完成，没有 Research 超时或节点失败。
- q03 Normal 的 ReportWriter 首次产物被确定性引用校验拒绝，随后使用新 attempt 修复成功，证明 `repairable → 定向修复` 闭环有效。

本报告评估执行可靠性、资源消耗、检索规模和阶段耗时。Quick/Normal 没有 Heavy FinalReview verdict，因此 `completed` 只代表成功交付，不代表内容已通过业务质量验收。

## 2. 测试批次与可比性

| 批次 | Query/模式 | 时间 | Run ID | 说明 |
| --- | --- | --- | --- | --- |
| 历史基线 | q01–q03 Quick | 2026-08-25 | `bench-current-cli-3mode-local-*` | 早期本机隔离 Hermes 结果 |
| 历史当前链路 | q04–q10 Quick/Normal | 2026-08-26 | `bench-finalrepair-headless-*` | 同一批次连续运行 |
| 最新当前链路 | q01–q03 Normal | 2026-08-28 | `run-*` | 从 Web 入口启动，采用当前 Workflow 和 Search MCP |

这是混合批次报告，适合用于当前整体稳定性与容量画像，但不是严格的 Quick/Normal A/B 实验。三批 Run 的代码快照、Hermes 运行时与超时策略存在差异。

## 3. Query 范围

| Query | 类型 | 主题摘要 |
| --- | --- | --- |
| q01 | 宏观经济 | 联合国、IMF、世界银行 2026 年全球增长预测比较 |
| q02 | 文化遗产 | 北京中轴线历史、15 处遗产构成与规划理念 |
| q03 | 金融市场 | 2005–2025 年全球及中国央行黄金购买趋势 |
| q04 | 软件工程 | 传统现代软件工程与 AI 原生组织比较 |
| q05 | 市场研究 | 2026 年全球 AI 生产力工具市场与北美策略 |
| q06 | 医疗器械 | 可穿戴设备的脑卒中风险监测与预警 |
| q07 | AI 模型生态 | 中医 AI 大模型技术路线、治理与评测 |
| q08 | 跨境投资 | 中国企业在孟加拉国投资与工程施工 |
| q09 | 气候数据 | 8 国 GDP、CO₂排放、碳转移与能源转型 |
| q10 | 公司金融 | 英伟达财务、估值驱动、风险与投资情景 |

## 4. 汇总指标

| 模式 | 成功 | 中位耗时 | P90 | 平均耗时 | Agent attempt | 平均 Agent | 工具/失败 | Search API | Evidence URL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Quick | 10/10 | 9.56 分钟 | 14.95 分钟 | 11.29 分钟 | 20 | 2.0 | 461/15 | 83 | 130 |
| Normal | 10/10 | 21.86 分钟 | 24.82 分钟 | 20.18 分钟 | 66 | 6.6 | 2,702/44 | 549 | 690 |
| 合计 | **20/20** | — | — | 15.73 分钟 | **86** | — | **3,163/59** | **632** | **820** |

Normal 相比 Quick：

- 中位墙钟耗时约为 2.29 倍；
- 平均 Agent attempt 约为 3.30 倍；
- 平均工具调用约为 5.86 倍；
- 平均 Evidence URL 约为 5.31 倍。

## 5. 单 Run 结果

`工具/失败`中的失败是工具调用级错误，不是 Run 失败。`Provider/API`是 Search 持久层中实际调用或复用的 distinct Provider 数及 API 调用数。

| Query | 模式 | 状态 | 耗时（分） | Agent | 工具/失败 | Provider/API | Raw/Unique/Fetched | Evidence URL |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| q01 | Quick | completed | 9.91 | 2 | 28/1 | 0/0 | 0/0/14 | 10 |
| q01 | Normal | completed | 12.34 | 6 | 216/2 | 2/28 | 212/141/55 | 34 |
| q02 | Quick | completed | 6.96 | 2 | 37/1 | 5/5 | 40/40/12 | 10 |
| q02 | Normal | completed | 13.22 | 6 | 256/4 | 7/125 | 698/497/22 | 41 |
| q03 | Quick | completed | 28.53 | 2 | 64/1 | 5/5 | 55/55/24 | 16 |
| q03 | Normal | completed | 17.71 | 7 | 303/2 | 6/90 | 449/363/68 | 66 |
| q04 | Quick | completed | 8.08 | 2 | 45/3 | 10/15 | 82/72/21 | 18 |
| q04 | Normal | completed | 20.87 | 7 | 297/5 | 10/63 | 459/346/117 | 100 |
| q05 | Quick | completed | 9.40 | 2 | 58/1 | 11/18 | 131/130/25 | 15 |
| q05 | Normal | completed | 23.07 | 7 | 314/4 | 13/40 | 204/142/140 | 102 |
| q06 | Quick | completed | 13.44 | 2 | 73/0 | 12/13 | 78/77/41 | 22 |
| q06 | Normal | completed | 22.84 | 7 | 334/5 | 14/58 | 385/348/177 | 123 |
| q07 | Quick | completed | 10.09 | 2 | 45/2 | 8/14 | 84/76/17 | 11 |
| q07 | Normal | completed | 24.57 | 7 | 339/7 | 9/84 | 494/394/112 | 60 |
| q08 | Quick | completed | 9.09 | 2 | 43/2 | 9/10 | 72/72/22 | 14 |
| q08 | Normal | completed | 27.16 | 6 | 243/4 | 9/31 | 156/152/117 | 75 |
| q09 | Quick | completed | 7.65 | 2 | 28/2 | 0/0 | 0/0/12 | 9 |
| q09 | Normal | completed | 16.74 | 6 | 111/6 | 4/16 | 182/166/26 | 30 |
| q10 | Quick | completed | 9.72 | 2 | 40/2 | 2/3 | 21/21/10 | 5 |
| q10 | Normal | completed | 23.25 | 7 | 289/5 | 3/14 | 101/50/107 | 59 |

## 6. 各阶段耗时与调用量

Active 时间是同阶段并发实例的时间区间并集；累计 Agent 时间是该阶段所有实例耗时之和。

| 模式 | 阶段 | Run 数 | 中位 Active | 中位累计 Agent | 平均实例数 | 平均工具调用 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Quick | Research | 10 | 5.94 分钟 | 5.94 分钟 | 1.0 | 40.6 |
| Quick | ReportWriter | 10 | 2.65 分钟 | 2.65 分钟 | 1.0 | 5.5 |
| Quick | Render | 10 | 约 0 分钟 | 约 0 分钟 | 1.0 | 0.0 |
| Normal | Plan | 10 | 1.97 分钟 | 1.97 分钟 | 1.0 | 5.5 |
| Normal | Research | 10 | 13.10 分钟 | 39.20 分钟 | 4.4 | 252.5 |
| Normal | ReportWriter | 10 | 4.46 分钟 | 4.46 分钟 | 1.2 | 12.2 |
| Normal | Render | 10 | 约 0 分钟 | 约 0 分钟 | 1.0 | 0.0 |

Normal Research 的中位累计 Agent 时间为 39.20 分钟，Active 只有 13.10 分钟，约实现 2.99 倍的墙钟压缩。这与平均 4.4 个并发 Research 实例相符。

## 7. 最新 q01–q03 Normal 结果

| Query | 耗时 | Research 实例 | Agent attempt | 工具/失败 | 校验告警 | 结果 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| q01 | 12.34 分钟 | 4 | 6 | 216/2 | 10 | 直接完成 |
| q02 | 13.22 分钟 | 4 | 6 | 256/4 | 4 | 直接完成 |
| q03 | 17.71 分钟 | 4 | 7 | 303/2 | 9 | ReportWriter 修复 1 次后完成 |

q03 ReportWriter 首次候选稿引用了未经 Evidence 路由的 `d2_s13`、`d2_s14`、`d3_s20`。确定性校验将 attempt 标记为 `repairable`，第二个 attempt 修复后成功通过并交付。

与 2026-08-25 的历史 Normal 结果相比，墙钟耗时变化为：

| Query | 历史 Normal | 最新 Normal | 变化 |
| --- | ---: | ---: | ---: |
| q01 | 24.47 分钟 | 12.34 分钟 | -49.6% |
| q02 | 20.75 分钟 | 13.22 分钟 | -36.3% |
| q03 | 65.84 分钟 | 17.71 分钟 | -73.1% |

三条 Query 的阶段耗时拆解如下：

| 阶段 | 历史 q01–q03 合计 | 最新 q01–q03 合计 | 节省 | 占总降幅 |
| --- | ---: | ---: | ---: | ---: |
| Plan | 7.86 分钟 | 4.91 分钟 | 2.95 分钟 | 4% |
| Research Active | 74.24 分钟 | 27.47 分钟 | 46.77 分钟 | 69% |
| ReportWriter | 28.96 分钟 | 10.89 分钟 | 18.07 分钟 | 27% |
| 合计 | 111.06 分钟 | 43.27 分钟 | 67.79 分钟 | 100% |

### 7.1 主要原因：旧 q03 Research 异常长尾消失

q03 单条减少 48.13 分钟，占三条 Query 总节省时间的约 71%。旧 q03 Research Active 为
51.36 分钟、累计 Agent 为 105.81 分钟；最新结果分别降至 10.13 和 34.40 分钟。

旧 q03 的一个 Research 产物仅因 `topic_tag` 以数字开头被 `V027` 拒绝，例如
`2010_2015_disclosure_shift`、`2009_disclosure_channels`。这个格式问题引发了约 26.6 分钟的完整
Research 修复 attempt，并与首轮慢实例一起形成主要长尾。最新 q03 的四个 Research 维度全部首轮成功，
没有 Research 级重跑。

### 7.2 Search MCP 将更多检索压缩到更短墙钟时间

最新结果不是通过少搜索换取速度：

| Query | 历史 Search API | 最新 Search API | 历史工具调用 | 最新工具调用 |
| --- | ---: | ---: | ---: | ---: |
| q01 | 4 | 28 | 153 | 216 |
| q02 | 58 | 125 | 213 | 256 |
| q03 | 20 | 90 | 298 | 303 |

新链路在工具调用相近或更多、Search API 显著更多的情况下，Research 墙钟耗时仍明显下降。这与
Search MCP 在 Domain 内批量并发 Provider、Research 维度并发、SQLite 统一去重/缓存/分页的实现一致，
减少了模型逐条发起搜索的串行往返。

### 7.3 旧批次的 stale 与 Broken pipe 等待未再出现

旧 q01 出现过多次 90 秒 stale connection kill 及关联的 Broken pipe/API 重试；旧 q03 出现过
150 秒 stale connection kill。最新 q01–q03 日志中没有检测到 stale、Broken pipe 或模型请求超时。
这部分减少了无效等待和请求重建，但它只是降幅的一部分，不能单独解释 q03 的 48.13 分钟收缩。

### 7.4 ReportWriter 产物生成和修复更快

| Query | 历史 ReportWriter | 最新 ReportWriter |
| --- | ---: | ---: |
| q01 | 10.83 分钟，1 attempt | 2.66 分钟，1 attempt |
| q02 | 6.19 分钟，2 attempts | 2.60 分钟，1 attempt |
| q03 | 11.94 分钟，1 attempt | 5.63 分钟，2 attempts |

最新 q03 虽然仍发生一次引用修复，但确定性校验直接给出了具体非法引用 key，第二个 attempt 能够定向修复。
当前 Evidence 路由和输入结构更规整，同时当日 API 延迟和缓存命中也可能更好。新旧批次均使用 `gpt-5.5`，
因此这不是更换模型造成的。

### 7.5 可排除的解释

- 不是因为 Agent 数减少：历史三条和最新三条都是 19 个 Agent attempt。
- 不是因为 Evidence 规模明显缩小：历史合计 138 个 Evidence URL，最新合计 141 个。
- `research: 1500` 只是新 Run 的硬上限，三条 Run 均未触发，不会使节点主动提前完成。
- Stitcher 和 FinalReview 改造只影响 Heavy，不属于这次 Normal 降耗的直接原因。

这一变化是跨日期、跨代码快照的观测，可以说明最新链路的实际耗时已明显收敛，但不能单独归因于某一项代码修改。

## 8. 失败、修复与质量信号

### 8.1 Run 和节点

- 20 个 Run 都没有最终失败。
- 最新 q01–q03 Normal 都没有 Research 超时。
- q03 Normal 发生 1 次 ReportWriter `repairable`，定向修复后成功。
- 所有 Render 节点均成功，确定性交付未成为性能或稳定性瓶颈。

### 8.2 工具级失败

59 次工具失败中：

- 58 次属于 `execute`，主要是临时 Python/数据处理命令失败；
- 1 次属于 Fetch/Extract；
- 工具失败都被 Agent 替代命令、重试、搜索降级或产物修复吸收。

早期批次日志中还出现过 API stale、HTTP 500、`[Errno 32] Broken pipe`、搜索限流和裸 `python` 不存在。这些是历史链路的已知降级事件，在本次选定的 20 个 Run 中均未造成最终失败。

### 8.3 确定性校验告警

共记录 46 条非阻断校验告警：

- `V041` 37 条：解释性 Claim 没有达到两个独立来源；
- `V040` 9 条：事实性 Claim 缺少 primary/secondary 级来源。

这些告警证明 Python 引用与 Evidence 校验正在运行，同时也表明“工作流完成”不等于所有 Claim 都有最佳证据覆盖。

## 9. Search 观测

- Quick 合计 83 次 Search API，Normal 合计 549 次。
- Normal 平均使用 7.7 个 Search Provider，Quick 平均 6.2 个。
- q02 Normal 的 Search 规模最大之一：125 API、698 Raw、497 Unique。
- q03 Normal 实际只使用 `academic` 和 `general_web` Domain，底层涉及 6 个 Provider。这暴露了宏观官方数据和大宗商品专业 Domain 的覆盖缺口。
- q01/q09 Quick 的 Provider 为 0 不等于未搜索；早期 Run 使用了没有完整写入 Search SQLite 的直接网页工具。

`Fetched` 仍存在口径限制：Hermes 将动态 MCP `fetch_url` 上报为 `kind=other`，并且实时 ACP 事件目前在 Agent 返回后才批量持久化。因此 Fetched 适合作为参考值，不适合在修复前用于严格模式比较。


## 10. 数据来源与统计口径

选定 Run：

- q01–q03 Quick：`runs/bench-current-cli-3mode-local-q{01..03}-quick-r01/`
- q01 Normal：`runs/run-1c06a613a78d4302b6db/`
- q02 Normal：`runs/run-a1185945fbf046748243/`
- q03 Normal：`runs/run-2c35e6db8a174041b6c2/`
- q04–q10 Quick/Normal：`runs/bench-finalrepair-headless-q{04..10}-{quick,normal}-r01/`

统计定义：

- 总耗时：`run.json.created_at` 到 `run_finished.recorded_at`；
- Agent 数：Node Spec 中 `kind=agent` 的实际 attempt 数，Script Node 不计入；
- 工具调用：ACP 投影中唯一 `toolCallId` 的 `tool_call` 数；
- 工具失败：工具调用的最终状态为 `failed`，不等于节点或 Run 失败；
- Search Provider：Search SQLite 中实际调用或缓存复用的 distinct Provider；
- Evidence URL：正式 Artifact JSON 中出现的唯一 HTTP(S) URL；
- 阶段 Active：同阶段并发实例执行区间的并集；
- 阶段累计 Agent：该阶段全部 Agent 实例耗时之和；
- Token：本批 Run 的 `harness.json.usage` 未提供可统一汇总的有效值，本报告不作推测。
