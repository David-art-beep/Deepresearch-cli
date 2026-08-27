# Research 多源搜索 MCP

## 1. 目标与边界

多源搜索 MCP 把原来分散在多个 Skill 中、返回格式各异的搜索脚本收敛为 Research Agent
可调用的一组统一工具。它解决的是“如何一次调度多个搜索源，并让这些调用实际返回的候选保持可读取”的
问题，不替代 Research Agent 的检索决策、内容筛选和证据核验。

职责划分如下：

| 环节 | 负责人 | 说明 |
| --- | --- | --- |
| 判断需要哪些信源 | Research Agent + Domain Registry | Agent 选择相关 Domain/Operation，Registry 展开其声明的 Source |
| 为不同信源改写 query | Research Agent | 提交领域 query，必要时用 `source_queries` 覆盖个别 Source |
| 批量调度与并发控制 | 搜索 MCP | 并发执行所选 Operation 下全部相关 Source |
| 格式归一化、去重、持久化 | 搜索 MCP | 保留来源信息，并把异构返回转成统一可分页条目 |
| 筛选候选结果 | Research Agent | 分页查看结果，按需要读取单条详情 |
| 读取并核验原文 | Search MCP `fetch_url` + Research Agent | 代码先执行普通 HTTP，必要时单次 Camofox 回退；Agent 核验返回正文 |
| 写入正式 Evidence | Research Agent | 只有节点业务产物通过 Validator 后才进入 Workflow State |

因此，“批量”表示一次提交多个相关 Domain/Operation，而不是把同一 query 无脑广播到整个注册表。
Source 只会在所选 Operation 声明它时执行；首轮结果不足时，Agent 可以调整领域、操作或 query。

当前内置 Domain 为 `academic`、`financial_market`、`corporate_disclosure`、
`software_engineering`、`ai_model_ecosystem`、`social_community`、`video_media` 和
`general_web`。`general_web` 当前只有 Wikipedia 定向发现，不应被理解成完整通用网页搜索。

## 2. 接入位置

搜索 MCP 是 Harness 层提供给 Research 节点的运行时能力，但是否使用、何时使用仍由 Research
Agent 决定：

1. CLI 在启动 `run` 或 `resume` 时解析搜索 MCP 的运行前配置。
2. 第一个 Research attempt 到来时，Harness 为整个 run 懒启动一个 Search Coordinator；
   `resume` 会重新启动进程并打开同一个 `runs/<run-id>/search/search.sqlite3`。
3. 每个 Research NodeInstance attempt 仍创建独立 Agent 进程和 Session；Harness 只向该
   Session 注入一个轻量 stdio MCP 代理，由代理通过带 token 的 localhost 通道访问 Coordinator。
4. Plan、Review、ReportWriter 等节点不会收到这组工具。
5. Coordinator 统一维护 run 级全局/Domain/Source 并发限制、熔断状态、去重索引和执行缓存；
   同一个 provider/query 即使由并行 d1–d5 提交，也只会执行一次外部请求。
6. 每个代理使用 attempt namespace。执行结果可在 run 内复用，但分页、详情与异步 batch
   只能读取本 namespace 的 discovery，Research 实例之间不会混入模型可见结果。
7. Research attempt 结束时删除代理 lease；run 结束或中止时删除 Coordinator lease 并关闭
   进程。父 CLI 异常消失时 watchdog 也会回收 Coordinator。
8. Research 最终把核验后的信息写入节点合同规定的 Evidence 文件；下游仍只通过 ArtifactRef
   接收正式业务产物。

这种接入不会修改 `~/.hermes` 中的全局 MCP 配置。每次 Session 使用独立服务名和独立存储
边界；Heavy 并发 Research 实例不共享 Agent 进程和模型可见结果，但共享受控的搜索执行与持久层。
MCP 的启用状态和本机路径属于 Execution Session 配置，不写入可恢复的 Workflow State；
resume 可以重新选择这些运行参数，而不会改变已经发布的 Artifact。

## 3. 工具合同

### `list_search_domains`

返回 Domain、Operation、相关 Source、可用状态和调度策略，是 Research 的首选能力目录。

### `start_domain_search`

异步创建领域搜索批次。每个领域请求被展开成相关 Source Job，并受全局、Domain 和 Source 并发限制。
工具立即返回 `batch_id`，避免慢 Source 占满一次 MCP 调用时限。

### `get_search_batch`

查询领域批次的 `running|succeeded|partial_success|failed` 状态。完成后使用同一个 `batch_id` 分页读取结果。

### `list_search_sources`（兼容/诊断）

返回本次 Session 可用的 provider，以及每个 provider 的能力、query 语义和可用状态。Agent
应先读取该目录，再决定本轮所需信源，避免在 Prompt 中长期复制一份容易漂移的信源清单。

### `batch_search`（兼容/诊断）

一次提交多组搜索请求。每组请求至少包含：

```json
{
  "provider": "academic",
  "query": "retrieval augmented generation evaluation benchmark",
  "evidence_target": "RAG 系统的公开评测基准与指标",
  "intent": "寻找论文原文和可复核的实验结论"
}
```

- `provider`：由 `list_search_sources` 返回的信源标识；
- `query`：Agent 针对该信源改写后的查询，不是固定复用用户原始问题；
- `evidence_target`：本次搜索要填补的具体证据目标；
- `intent`：结果筛选意图，便于后续追踪为什么发起这次搜索。

MCP 会严格校验请求，把同一次调用中相同 provider/query 的多个不同研究目标合并为一次外部执行，
同时为每个目标分别保留 discovery provenance。此前已经 `ok` 或 `empty` 的 exact pair 不再消耗
外部配额，而是把既有候选重新关联到当前 batch；`failed`、`partial`、`timed_out` 等未完成 pair
允许重试。不同 pair 并发运行，单个 provider 失败不会抹掉其他 provider 已取得的结果。返回值包含
批次标识、各请求状态、有界首屏和 cursor；不会把所有诊断响应一次性塞进模型上下文。

### `search_results`

分页读取已经归一化并持久化的 discovery occurrence。Agent 可以按 `batch_id` 或 provider 过滤，
并使用 `cursor` 和 `limit` 继续读取，直到 `next_cursor` 为空。同一个 canonical candidate 可能因
不同 provider、query 或研究目标出现多次：它们共享 `hit_id`，但各有 `discovery_id`。

这里的 cursor 只遍历 provider 本次调用在上游返回上限内实际返回并落盘的记录；默认每个 provider
请求最多保留 20 条（上限可配置到 50，`academic` 会分别查询其两个子源）。它不是上游平台的翻页
cursor，`next_cursor=null` 只表示当前持久化集合已经读完，不表示整个外部平台已被穷尽。

### `get_search_hit`

可以传 `hit_id` 或 `discovery_id`。前者读取去重后的 canonical candidate 和有界 provenance 列表；
后者读取某一次具体 provider/query 命中的来源字段与有界 `raw_item`。详情仍受 MCP 传输预算约束，
用于判断是否值得打开原文，不是网页正文，也不代表内容已被核验。

### `fetch_url`

读取一个由搜索得到的公开 HTTP(S) HTML URL。这个工具将回退策略固化在代码中：

1. 总是先执行普通 HTTP，并逐跳校验重定向目标；
2. 只有 403、明确反自动化挑战、JavaScript 空壳或传输失败允许 Camofox；
3. 同一 Research attempt 内，同一个规范化 URL 最多回退一次；
4. Camofox 只执行 create、snapshot、close，且通过 `finally` 保证关闭标签页；
5. 429、登录、CAPTCHA、付费墙、其他访问控制和 PDF 不使用浏览器重试；
6. 拒绝带凭据 URL，以及指向本机、私网、链路本地或保留地址的目标。

返回值明确区分 `retrieval=http|camofox`、`final_url`、`fallback`、正文和失败原因。Agent 不会
获得 Camofox 的 click、type、Cookie 导入等原始操作工具。PDF 返回
`pdf_requires_document_reader`，由 Research 改用文件/文档读取能力。

## 4. 执行、归一化与去重

`batch_search` 收到请求后按以下顺序工作：

1. 校验 provider、query、evidence target、intent 和批次大小；只去掉完全相同的逻辑请求。
2. 按 provider/query 组织外部执行：同批不同目标共用一次执行，已完成 pair 复用既有 candidate，
   未完成 pair 可以重试。
3. 按 provider 的并发约束执行脚本，并受统一批次时限和单信源时限保护。
4. 解析各 Skill 脚本的 JSON 返回（URL、摘要和来源字段可能位于不同层级），将原始 payload 与
   stdout/stderr 以有界形式写入 provider diagnostics。
5. 分别写 canonical hit 与 discovery occurrence：前者代表去重后的候选，后者保留 provider、query、
   batch、evidence target、intent 和该来源自己的字段。
6. 优先按 DOI、arXiv/Paper ID 等稳定标识去重，其次按规范化 URL；只有没有稳定标识或 URL 时才按
   来源内标题兜底。去重不会删除其他 provider 的 discovery provenance。
7. 追加写入请求、provider 执行记录、canonical hits、discoveries 和 batch 记录，并返回有界首屏。

并发有三层约束：run 级全局 worker 上限防止多个批次占满本机资源；Domain 限制约束领域扇出；
provider 级限制用于保护有严格速率限制的接口。认证缺失、401/403 等硬失败可以在当前 run 中
临时禁用对应 provider，避免并行 Agent 反复调用注定失败的信源；429 或临时网络错误不会永久禁用，
Agent 仍可稍后调整策略重试。

## 5. 为什么既落盘又提供分页

将所有结果直接返回给模型会迅速膨胀上下文；只返回首屏又会让已经取得的后续记录事实上不可见。
这里采用“有界采集、全部落盘、按需读取”的结构：

- 每次 provider 调用有明确的结果数和输出字节上限，避免单次搜索无限膨胀；
- provider payload、stdout/stderr 和单条 raw item 以有界形式保留，用于追溯脚本行为；
- canonical hit、discovery occurrence、请求和批次写入 run 级 SQLite WAL；事务提交后的记录可由
  `resume` 继续读取；
- `batch_search` 返回足以判断方向的首屏摘要；
- `search_results` 让 Agent 分页遍历本次 provider 调用已返回并持久化的全部 discovery；
- `get_search_hit` 只在候选值得深入时提供有界的 canonical 或 source-specific 详情。

这些搜索文件不是 Workflow 的正式业务中间件，也不会把正文复制进 State。State 仍只保存
已通过节点合同发布的 ArtifactRef。搜索数据库位于
`runs/<run-id>/search/search.sqlite3`，Coordinator stderr 位于同目录，供轨迹分析、失败诊断和
结果复核使用；attempt 目录只保留代理 lease 等短生命周期文件。

## 6. 原文读取仍是必需步骤

归一化结果中的 title、snippet 和 metadata 只用于发现与筛选。它们可能来自搜索引擎摘要、
接口截断文本或第三方索引，不能自动满足 Evidence 的可核验性要求。

Research Agent 应当：

1. 用分页与详情工具筛出高价值候选；
2. 对 HTML 候选 URL 使用 Search MCP 的 `fetch_url`；PDF 等文档使用对应文件读取能力；
3. 检查来源身份、发布时间、正文上下文和结论适用范围；
4. 只有在读到支持性正文后，才把知识点和引用写入 Evidence Artifact。

因此，MCP 降低了多信源搜索的调度成本和上下文浪费，并确定性执行反扒回退，但没有制造“搜索结果
等于证据”的捷径。

### Web 进度与统计口径

Run 级 Coordinator 会把 Domain 计划、Source 开始/完成、外部执行和缓存复用写入 SQLite
`telemetry`。Web 快照直接只读该数据库，因此 Research 节点尚未结束时也能展示 Domain 完成度、
正在运行的 Source、每个 Source 的调用次数和端到端耗时。SSE 使用 telemetry 版本作为刷新标记，
不必等待 Workflow Journal 产生下一条节点事件。

统计口径如下：

- **API 调用**：实际启动 provider 进程的次数；配置不可用、排队超时和缓存复用不计入。
- **Source 耗时**：一次 provider job 从可用性检查到结果归一化完成的墙钟时间，显示总计、平均值和最大值。
- **缓存复用**：没有再次执行外部 provider、而是复用了同一 run 中已完成 provider/query 的次数；
  不是被复用的 hit 条数。
- **Raw**：实际外部调用成功解析并进入归一化阶段的候选条数之和；缓存回放不重复增加 Raw。
- **Unique**：当前 run 搜索库中的 canonical hit 数，按稳定 ID、规范 URL 和标题规则去重。
- **Fetched**：Agent 工具轨迹中已完成的正文 fetch/browser 调用数；能从工具标题提取 URL 时按 URL
  去重，否则按 tool call 去重。只持久化工具类型、标题、状态和 ID，不保存工具输入正文或返回正文。
- **Evidence**：各维度最新 Evidence Artifact 中去重后的 HTTP(S) 来源 URL 数。

漏斗依次显示 `Unique / Raw`、`Fetched / Unique`、`Evidence / Fetched`。分母为零时比例显示为空。
Fetched 依赖 Harness 提供的工具进度事件；某个 Harness 不上报 fetch 或标题中不含 URL 时，该数字是
保守观测值，Evidence 可能高于 Fetched，系统不会为了让比例好看而截断真实计数。

## 7. CLI 配置

MCP 服务本身随本仓库安装，搜索源则由一个独立目录注册。默认目录是仓库或安装包中的 `search/`：

```text
search/
├── .env                 # 本机值，Git 忽略
├── .env.example         # 可提交模板
├── providers/           # 内置搜索实现
│   ├── academic/        # 学术聚合入口及其本地子实现
│   ├── github_issues.py
│   ├── github_repositories.py
│   └── ...              # 每个 provider 一个可执行入口文件
└── sources/
    ├── academic.yaml
    ├── github_repositories.yaml
    └── ...              # 每个 provider 一个文件
```

MCP 启动时扫描全部 `sources/*.yaml`，不存在 Python 侧固定 provider catalog。每个文件声明 source 名称、
脚本、`{query}` / `{limit}` 参数模板、Agent 选择提示、结果语义、并发、超时、Python 模块和需要传给
脚本的环境变量。文件名必须等于 `name`；增加一份合法 YAML 就注册一个新 provider。

内置搜索脚本全部随本仓库放在 `search/providers/`，不依赖外部 Skill 仓库或脚本根目录环境变量。
`search/.env` 只保存各 provider 声明的 API token、cookie 和 user-agent。source 的 `script` 默认指向
注册目录内的相对 Python 文件，也可以为自定义注册表配置任意绝对路径或 `${NAME}` 路径变量。
`doctor` 会检查本次目录中每一份 source YAML、脚本、必需模块，并要求至少一条 source 可运行。
它不对 API 做真实兼容测试。source 脚本由 `--search-provider-python` 以本机
权限执行，没有 OS 沙箱，因此只能注册固定版本且可信的代码。

Hermes 进程还必须包含其 MCP client 依赖。若所安装的 Hermes distribution 没有随包提供 MCP
支持，需要在 Hermes 自己的 Python 环境中安装与本仓库锁定的 `mcp==1.26.0` 和
`starlette==1.0.1`；这与 `--search-provider-python` 指向的脚本运行环境是两个不同边界。

`doctor`、`run` 和 `resume` 接受以下运行前参数：

| 参数 | 含义 |
| --- | --- |
| `--search-mcp` | 启用 Research 搜索 MCP，默认启用 |
| `--no-search-mcp` | 仅对本次 Execution Session 禁用 |
| `--search-dir PATH` | 指定包含 `.env` 和 `sources/*.yaml` 的搜索注册目录 |
| `--search-provider-python PATH` | 指定运行 provider 脚本的 Python 解释器 |
| `--search-provider-limit N` | 每个选中 provider 请求的最大结果数，范围 1–50，默认 20 |

`sources list` 和 `sources describe <name>` 不启动 Hermes，直接加载同一目录并检查 source、脚本和
Python 模块，适合在新增 YAML 后做配置预检。

示例：

```bash
uv run deepresearch doctor \
  --harness hermes \
  --search-dir ./search \
  --search-provider-python /path/to/python \
  --json

uv run deepresearch "比较不同 RAG 评测框架" \
  --language zh-CN \
  --mode heavy \
  --report-format formal_report \
  --output-format markdown \
  --harness hermes \
  --search-dir ./search \
  --search-provider-python /path/to/python \
  --runs-dir ./runs
```

`list_search_sources.available` 根据本次目录发现的 source、脚本、必需 Python 模块、必需凭据和当前 Session
熔断状态计算；它是静态/Session 内可用性，不是外部网络或 API 健康检查。真实可用性只有执行后才能
确认。

配置优先级为：MCP 父进程环境 > 当前 Hermes profile `.env` > 搜索注册目录 `.env`。source YAML
中的 `${NAME}` 可用于脚本路径；`required_env` 和 `optional_env` 同时构成该脚本的环境变量白名单。
每个脚本子进程只获得自己声明的变量、代理变量和安全基础环境，不把其他 source 的 token、注册目录
路径或 MCP 内部路径整体透传。v0.1 不直接解析 Hermes 的 `.op.env`、外部 secret source 或 managed
scope；只配置在这些机制中、但没有进入上述三种来源的值不会自动传给 MCP。

## 8. 故障语义

- 请求格式错误：整个工具调用返回明确的 validation error，不执行含糊请求。
- 单信源无结果：记录为空结果，其他信源继续完成。
- 单信源超时或异常：记录该请求失败，保留同批次其他成功结果。
- 批次超过总时限：停止尚未完成的子进程，并返回已完成结果和超时状态。
- 已完成的重复 provider/query：返回 `reused_completed`，不重复消耗外部配额，并把既有候选关联到
  当前 batch；失败、部分成功或超时的 pair 仍允许重试。
- MCP 无法启动或注册：Harness 将其视为运行能力故障；不会偷偷退化成“工具不存在但继续跑”。
- Research 正常结束、超时或取消：Harness 删除 attempt lease；搜索服务终止活跃 provider 进程树，
  stdio MCP 的 lease watchdog 随后结束本 attempt 的 MCP 进程。lease 是进程清理用的协作式存活
  信号，不是持久化取消状态、ACP cancel 的替代品，也不代表 CLI 已实现 `cancel` 命令。

这些状态都面向后续决策：Agent 可以换 query、换 provider、缩小目标，或在可用信息足够时
停止搜索，而不是被迫固定轮数或固定信源数量。
