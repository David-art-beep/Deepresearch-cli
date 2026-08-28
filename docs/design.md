# DeepResearch 配置运行时设计

更新日期：2026-08-13

## 1. 设计目标

运行时要同时满足两类使用者：

- 基础用户只选择 `quick | normal | heavy` 和 `markdown | html`。
- Agent 或高级用户可以用一个简单 YAML 重排、重复或加入已经注册的能力节点。

拓扑必须只有一个事实来源：按顺序排列的 `steps`。节点输入输出只在 `config/nodes/*.yaml` 中声明，不能把节点定义、fan-out、跳转表达式或 Policy 再复制进 Workflow YAML。

本实现不保留旧 Graph Runtime。`workflow/`、`executors/`、Policy 和 Input Selector 已删除；新 CLI 不提供旧 `run` 子命令别名。历史 Manifest 不迁移。

## 2. 配置模型

### 2.1 Workflow

```yaml
version: 1
name: normal
steps:
  - plan
  - research
  - report-writer
  - render
timeouts:
  plan: 300
  research: 1500
  report-writer: 420
result: report
```

必填字段固定为 `version`、`name`、`steps`、`result`，仅允许增加可选的 `timeouts`。
`timeouts` 仅适用于 Agent 节点，使用秒为单位，值必须有限且大于零。Node ID 为该类节点提供统一预算；
同一 Workflow 内重复出现的同类节点使用相同超时，不接受 `research-2` 这类按轮次配置。不同模式的
Workflow 仍可以为同一 Node 设置不同预算。编译后的 timeout 写入 Manifest；执行时优先使用它，
未配置的 Agent 节点才回退到 `--node-timeout-seconds`。确定性 Script 节点不设置超时，也不使用
CLI 的统一兜底；为 Script 节点配置 Workflow timeout 会在编译时直接报错。

编译器按 YAML 顺序为重复节点生成稳定 Step ID：第一次 `research` 是 `research`，第二次是 `research-2`。每个输入端口自动绑定到之前最近的兼容输出，不提供 `from`、条件表达式或转译 DSL。

交付格式不是另一套研究流程。`--output-format html` 在最后自动追加 `md-html`；
`--output-format pdf` 追加 `md-pdf`；`--output-format docx` 追加
`md-docx`。如果自定义 Workflow 已以所需节点结尾则不重复追加。

### 2.2 Node 配置

一份 Node YAML 是一个运行能力的注册单位。内置配置统一放在仓库根目录：

```text
config/
├── workflows/
│   ├── quick.yaml
│   ├── normal.yaml
│   └── heavy.yaml
└── nodes/
    ├── research.yaml
    ├── render.yaml
    └── md-html.yaml
```

Word 与 PDF 的内置模板是静态资产，分别位于
`assets/report-templates/word/reference.docx` 和
`assets/report-templates/pdf/report.typ`。Node YAML 通过 `asset:` 引用它们；
Registry 在创建 Run 时将文本或 base64 编码的二进制内容写入 Node Spec 快照。

Node Spec 只定义：

- `id` 和 `kind: agent | script`；
- Agent 的 `prompt` 或内置 Prompt key；
- Script 的 `command`；
- 输入端口；
- 输出端口；
- 可选的封存前 `materializer`、单 Validator、顺序 Validator 列表和静态资源；`validator` 与 `validators` 互斥。

`materializer` 只用于从正式语义产物确定性生成 batch 任务、索引或证据子集。执行顺序固定为
节点主体 → Materializer → 冻结候选 → Validator → 发布；Validator 不承担生成职责，也不能修改候选。

自定义节点的相对脚本、Prompt 和资源在创建 Run 时写入 Node Spec 快照；
文本保持 UTF-8，二进制资源使用带版本标记的 base64。节点层不支持 `skill`
字段，也不扫描外部 Skill 目录。

### 2.3 Search Source 配置

多源搜索注册表位于独立的根目录 `search/`，不写死在 MCP Python 代码中：

```text
search/
├── .env
├── .env.example
├── providers/
│   └── <provider>.py
└── sources/
    └── <provider>.yaml
```

MCP 启动时严格加载每一份 `sources/*.yaml`，并可选加载 `domains/*.yaml`。一份 Source 文件声明脚本、
参数模板、结果语义、超时、并发、模块依赖以及该脚本可见的环境变量；一份 Domain 文件声明研究操作及
其相关 Source。Research 通过 Domain/Operation 发起并发扇出，Source 级工具保留兼容。新增 Source 或
调整领域组合不修改 Driver、Harness 或 MCP tool schema；非法、重名、未知字段和悬空 Source 引用在
Research Session 启动前失败。

`.env` 是本机运行配置并由根目录 `.gitignore` 排除；`.env.example` 随源码和安装包分发。脚本是受信任本地代码，SearchService 仍以无 shell 的参数数组启动它，并只透传该 source 声明的环境变量。

### 2.4 端口

输入端口：

```yaml
evidence:
  type: evidence
  media_type: application/json
  mode: one | all | each
  required: true
```

- `one`：读取同 scope 的最新 state；找不到时读取全局 state。
- `all`：读取该 Artifact type 的全部当前 state。
- `each`：以上游最近兼容 Step 的 Artifact scope 为实例集合，并在同 scope 读取该输入。

输出端口：

```yaml
evidence:
  path: evidence.json
  type: evidence
  media_type: application/json
  mode: state | batch
  primary: false
  required: true
```

- `state`：输出一个文件，并成为同类型、同 scope 的最新值。
- `batch`：`path` 必须包含 glob `*`；每个匹配文件形成一个 Artifact，并从文件名提取 scope key。

控制面只验证声明、路径、文件存在性、非空、hash 和只读发布边界。业务结构由节点可选 Validator 负责；不再由一套全局严格 schema 阻止任意新能力接入。

业务 Validator 的硬错误必须能回溯到具体消费端：下游字段读取、引用解析、
scope 匹配、派生结果一致性或文件安全。单纯的内容数量、推荐枚举、标题措辞和
未被消费的扩展字段不得成为 Repair 条件。

## 3. 编译与调度

编译流程：

1. 读取严格 Workflow YAML。
2. 从 Node Registry 解析每个 Node ID。
3. 根据 HTML、PDF 或 DOCX 交付格式追加对应转换节点。
4. 为重复节点分配 Step ID。
5. 对每个输入端口，从先前输出中选择最近的 `type + media_type` 兼容生产者。
6. 必需的 `one/each` 输入没有生产者时拒绝编译。
7. 确认最终存在与 `result` 及目标格式匹配的 primary output。

Driver 只做顺序调度：

1. 找到第一个尚未完成的 Step。
2. 无 `each` 输入时产生一个全局实例。
3. 有 `each` 输入时，从直接源 Step 的 Artifact scope 计算实例集合。
4. 空 batch 产生零实例，整个 Step 被自然跳过。
5. 每个实例选择端口输入，并在并发上限内交给统一 NodeRunner。
6. 全部 Step 完成后写 `run_finished` 并导出 primary result。

因此 Heavy 中的第二轮补研没有条件分支。SupplementPlanner 的 `research-tasks` batch 为空时，第二个 Research、Review、Perspective 都没有 scope，会自然跳过；batch 非空时，同一份 YAML 自动执行第二轮。

## 4. 统一 Node Context

Agent Prompt 与 Script 环境看到完全相同的 Context：

```json
{
  "run": {
    "id": "run-...",
    "query": "...",
    "language": "zh-CN",
    "mode": "heavy",
    "output_format": "html"
  },
  "step": {
    "id": "research-2",
    "node": "research",
    "instance": "research-2-...",
    "attempt": 1
  },
  "scope": {"dimension-id": "d1"},
  "inputs": {
    "task": [{
      "port": "research-tasks",
      "type": "research-task",
      "media_type": "application/json",
      "path": "/absolute/artifact/path",
      "sha256": "sha256:...",
      "scope": {"dimension-id": "d1"},
      "mode": "batch",
      "step_id": "supplement-planner",
      "instance_id": "..."
    }]
  },
  "outputs": {
    "evidence": {
      "path": "/absolute/staging/evidence.json",
      "type": "evidence",
      "media_type": "application/json",
      "mode": "state"
    }
  }
}
```

Agent Context 直接附在 Prompt 后；Script 通过 `DEEPRESEARCH_NODE_CONTEXT` 获得 JSON 文件路径。节点不得自行选择下一跳、修改 Journal 或直接发布 Artifact。

## 5. NodeRunner 与发布边界

Agent 和 Script 共用以下生命周期：

1. 创建 attempt staging 与 diagnostics。
2. 写入统一 Context，并物化快照内脚本和 Validator。
3. Agent 通过 Harness 执行；Script 以 Context 环境变量执行。
4. 排除 `_runtime/` 后冻结 staging 为私有 candidate。
5. 封存 candidate 并记录全文件 hash。
6. 只匹配 Node Spec 声明的输出。
7. 在只读 candidate 上按声明顺序执行一个或多个 Validator。
8. 再次计算 hash，Validator 修改任何文件都失败。
9. 只原子发布匹配且验证通过的文件。
10. Journal 记录完整 ArtifactRef。

Agent 正常返回但 Validator 拒绝时允许一次新 attempt；第二次失败为 terminal。Script 不调用模型修复，首次失败即 terminal。Harness、文件系统、发布或 Validator 基础设施错误也不触发模型修复。

## 6. Artifact 与当前状态

ArtifactRef 固定字段为：

```text
port, type, media_type, path, sha256, scope, mode, step_id, instance_id
```

Journal 中的 step input 必须引用更早成功提交的 Artifact；path 必须位于 `artifacts/`，hash 必须与实际文件一致。任何篡改都会阻止 status、resume 和后续 Journal 写入。

当前 state 不是单独文件，而是按 Journal 顺序折叠 `mode: state` Artifact 得到 `(type, scope) -> latest Artifact`。batch Artifact 只驱动 fan-out，不覆盖 state。

内置 `heavy` 工作流额外从同一份 Projection 计算进度快照。阶段权重固定，fan-out
节点的完成比例按实际 scope 数量计算；`report-writer` 的分母来自
`report-planner` 发布的 `content-task` batch。进度不是新的持久化状态，因此不会
与 Journal 分叉，resume 和 status 都能得到相同结果。quick、normal 和自定义
工作流不生成该快照。

## 7. Manifest 与恢复

新 Manifest：

```json
{
  "schema_version": "2",
  "runtime": "config-workflow",
  "run_id": "run-...",
  "context": {},
  "workflow": {},
  "nodes": [],
  "definition_hash": "sha256:..."
}
```

`workflow` 是编译结果；`nodes` 是本 Run 实际使用的完整 Node Spec 快照。`definition_hash` 覆盖二者。resume 只使用快照，不重新编译本机 YAML。

Loader 只接受上述 schema/runtime。旧 Graph Manifest 明确报错，不存在兼容转换器或双运行时分支。

Journal 只有三种事件：

- `step_started`
- `step_finished`
- `run_finished`

`repairable` 和 `interrupted` 是 attempt outcome，不需要额外路由事件。进程在 active attempt 中断后，resume 先记录 `interrupted`，再创建下一 attempt。

## 8. 结果导出

`runs/` 是运行状态与中间文件目录，不是用户结果目录。完成时 Driver 根据 Workflow 的 `result_type + result_media_type` 找到最后一个 primary Artifact，校验 hash 后原子复制到：

```text
output/<run-id>/<source-file-name>
```

Markdown 输出为 `report.md`。HTML 输出同时导出 `report.html` 和 Markdown 源报告，并在 CLI 摘要中返回两条路径。

## 9. CLI

基础研究：

```bash
deepresearch "query" --mode quick --report-format brief --output-format markdown --harness hermes
deepresearch "query" --mode heavy --report-format formal_report --output-format html --harness hermes
```

高级工作流：

```bash
deepresearch "query" --workflow ./flow.yaml --nodes-dir ./nodes --mode heavy --report-format formal_report --harness hermes
```

节点发现与单节点执行：

```bash
deepresearch nodes list --nodes-dir ./nodes --json
deepresearch nodes describe my-node --nodes-dir ./nodes --json
deepresearch node run md-html --input report=./report.md --harness hermes
```

持久化命令：

```bash
deepresearch status <run-id> --json
deepresearch resume <run-id> --harness hermes
```

生产 CLI 暴露 Hermes ACP、Codex ACP、Claude Code ACP 和兼容用 Codex Exec Harness，不暴露 Stub Harness。
四者都实现 `BackendFactory -> AttemptRuntime -> AgentExecutionResult` 合同，每个 attempt 使用独立进程。
Hermes 原生提供 ACP；Codex ACP Bridge 将 ACP Session/Prompt 映射到 Codex App Server 的
Thread/Turn，并把流式事件映射回 ACP；Claude Code 通过
`@agentclientprotocol/claude-agent-acp` 将 Claude Agent SDK 暴露为 stdio ACP Agent。
三种 ACP Harness 都通过 `session/new` 注入 Research 专用 Search MCP；`codex-exec` 继续解析
`codex exec --json` JSONL，作为回退。

## 10. 内置能力

内置 Workflow：

- Quick：`research, report-writer, render`
- Normal：`plan, research, report-writer, render`
- Heavy：`scout, plan, research, review, perspective, supplement-planner, research, review, perspective, report-planner, report-writer, stitcher, final-review-diagnostic, final-repair, final-review-recheck, render`。Diagnostic 的确定性 materializer 直接生成 unit 修复任务；Recheck 的受信任 preparer 先重新拼接并锁定终稿。首次 FinalReview 通过时修复与复审步骤为零实例；若为 `revise`，只执行一次定向 unit 修复与一次复审。

内置 Node YAML：Scout、Plan、Research、Review、Perspective、SupplementPlanner、ReportPlanner、ReportWriter、Stitcher、FinalReview、Render 和 md-html。Stitcher 是确定性 Script，负责按 outline 拼接正文并执行 render contract、引用和标题检查，不再调用模型润色。

Render 是 Script 节点；md-html 是普通 Agent 节点。它原来依赖的 HTML Skill 已迁移为 `prompts/v0.1/md-html.md`，运行时不存在 Skill 加载分支。业务 Prompt 从 Prompt Bundle 加载后写入 Node Spec 快照，但 Prompt Assembler 不再参与运行时。

## 11. 扩展规则

新增能力时：

1. 在 `config/nodes/` 增加 Node YAML，声明最小输入输出。
2. 用 `nodes describe` 检查加载结果。
3. 把节点 ID 插入 Workflow `steps`。
4. 写一个真实 NodeRunner 测试，验证输入文件读取和输出发布。
5. 若更改既有端口合同，必须新建 Run；不为旧 Manifest 增加分支。

禁止：

- 在 Driver 中按 Node ID 写业务 `if/else`；
- 在 Workflow YAML 中复制 Node Spec；
- 引入另一套跳转表达式；
- 让 Validator 修改候选文件；
- 把 attempts diagnostics 当成正式 Artifact；
- 为旧 Graph Run 增加兼容入口。
