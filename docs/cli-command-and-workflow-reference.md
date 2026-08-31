# DeepResearch CLI 完整命令与工作流节点说明

> 适用版本：`deepresearch-cli 0.1.0`
> 整理日期：2026-08-31
> 依据：当前 `src/deepresearch_cli/cli.py`、`config/workflows/*.yaml` 与 `config/nodes/*.yaml`

## 1. 四组相互独立的选择

| 选项 | 可选值 | 控制内容 |
|---|---|---|
| `--mode` | `quick`、`normal`、`heavy` | 研究深度、工作流节点和节点业务行为 |
| `--report-format` | `brief`、`formal_report` | 简报或正式报告的写作形式 |
| `--output-format` | `markdown`、`html`、`pdf`、`docx` | 最终交付文件容器 |
| `--harness` | `hermes`、`codex`、`claude-code`、`openclaw`、`codex-exec` | 实际执行 Agent 的后端；前四项统一走 ACP，`codex-exec` 仅作兼容 |

这四项不能互相替代。例如 `heavy + brief + pdf + hermes` 表示：使用 Heavy 研究链路，写成简报，
最终转成 PDF，并由 Hermes 执行 Agent 节点。

用户 query 明确指定报告目录、章节、顺序或承载结构时，以 query 为准；内容模板只用于补充覆盖检查，
不会覆盖用户结构。

## 2. 命令总览

```text
deepresearch research             启动研究；通常省略 research
deepresearch doctor               检查节点注册和 Agent Harness
deepresearch status               查看持久化 Run 状态
deepresearch resume               从未完成节点继续 Run
deepresearch nodes list           列出节点
deepresearch nodes describe       查看节点完整定义
deepresearch node run             单独运行一个节点
deepresearch sources list         列出搜索来源
deepresearch sources describe     查看一个搜索来源
deepresearch domains list         列出搜索领域
deepresearch domains describe     查看一个搜索领域
deepresearch browser setup        安装 Camofox 及浏览器内核
deepresearch browser start        启动 Camofox
deepresearch browser status       查看 Camofox 状态
deepresearch browser stop         停止 Camofox
deepresearch web                  启动本地 Web 进度控制台
```

安装还会提供 `deepresearch-search-mcp`，但它是由运行时为 Research Session 自动启动的内部 stdio
MCP Server，依赖运行时注入的环境变量，不是普通用户直接执行的命令。

## 3. 启动研究

### 3.1 标准语法

```bash
deepresearch research '研究问题' \
  --mode normal \
  --report-format formal_report \
  --output-format markdown \
  --harness hermes
```

`research` 可以省略，推荐日常使用下面的形式：

```bash
deepresearch '研究问题' \
  --mode normal \
  --report-format formal_report \
  --output-format markdown \
  --harness hermes
```

若首个参数不是已注册子命令，根解析器会自动把它当作研究 query，并在前面补上 `research`。
如果 query 本身刚好是 `status`、`web` 等子命令名，必须显式写 `deepresearch research 'status' ...`，
避免被解释成子命令。

### 3.2 三种模式示例

```bash
# Quick
deepresearch '研究问题' \
  --mode quick \
  --report-format brief \
  --output-format markdown \
  --harness hermes

# Normal
deepresearch '研究问题' \
  --mode normal \
  --report-format formal_report \
  --output-format markdown \
  --harness hermes

# Heavy
deepresearch '研究问题' \
  --mode heavy \
  --report-format formal_report \
  --output-format markdown \
  --harness hermes
```

### 3.3 研究命令完整参数

```text
deepresearch [research] QUERY
  [--language LANGUAGE]
  [--mode quick|normal|heavy]
  [--workflow PATH]
  [--report-format brief|formal_report]
  [--output-format markdown|html|pdf|docx]
  [--harness hermes|codex|claude-code|openclaw|codex-exec]
  [--harness-profile PROFILE]
  [--harness-command COMMAND]
  [--harness-model MODEL]
  [--node-timeout-seconds SECONDS | --no-node-timeout]
  [--max-concurrency N]
  [--max-steps N]
  [--progress auto|tools|off]
  [--no-search-mcp]
  [--search-dir PATH]
  [--search-provider-python PATH]
  [--search-provider-limit 1..50]
  [--camofox-fallback | --no-camofox-fallback]
  [--camofox-home PATH]
  [--camofox-base-url URL]
  [--runs-dir PATH]
  [--output-dir PATH]
  [--nodes-dir PATH]...
  [--json]
```

常用参数含义：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--language` | `zh-CN` | Agent 产物语言 |
| `--mode` | 内置流程为 `normal` | 自定义 Workflow 未传 mode 时也使用 Normal 节点行为 |
| `--output-format` | `markdown` | 最终输出格式 |
| `--report-format` | 无 | 交互终端会询问；脚本和 CI 必须显式传入 |
| `--node-timeout-seconds` | `900` | 仅作为没有 Workflow 专用超时的 Agent 节点兜底 |
| `--max-concurrency` | `4` | 同一步骤中不同 scope/维度的最大并发数 |
| `--max-steps` | 无限制 | 本次最多调度的节点实例数；用于分段执行和测试 |
| `--progress` | `auto` | `tools` 显示工具级轨迹，`off` 关闭终端进度 |
| Search MCP | 开启 | `--no-search-mcp` 完全关闭当前内置搜索 MCP |
| `--search-provider-limit` | `20` | 单次 Provider 返回候选数量上限，合法范围 1–50 |
| Camofox fallback | 开启 | 仅 Search MCP 开启时生效；普通 HTTP 失败后才回退 |
| `--runs-dir` | `./runs` | Manifest、Journal、Attempt 和 Artifact 的持久化目录 |
| `--output-dir` | `./output` | 最终报告导出目录 |

`--run-id` 也是研究命令支持的隐藏参数，供 benchmark、自动化测试和需要固定 Run ID 的场景使用：

```bash
deepresearch '研究问题' \
  --run-id q01-normal-r01 \
  --mode normal \
  --report-format formal_report \
  --harness hermes
```

### 3.4 自定义 Workflow

```bash
deepresearch '研究问题' \
  --workflow ./my-workflow.yaml \
  --mode normal \
  --report-format formal_report \
  --output-format markdown \
  --harness hermes
```

`--workflow` 控制节点拓扑，`--mode` 控制节点内部的业务行为。两者可以组合。

## 4. 状态、恢复与环境检查

完整语法：

```text
deepresearch doctor
  --harness hermes|codex|claude-code|openclaw|codex-exec
  [通用 Harness/Search/Camofox 参数]
  [--runs-dir PATH] [--output-dir PATH] [--nodes-dir PATH]... [--json]

deepresearch status RUN_ID
  [--runs-dir PATH] [--output-dir PATH] [--nodes-dir PATH]... [--json]

deepresearch resume RUN_ID
  --harness hermes|codex|claude-code|openclaw|codex-exec
  [--max-steps N]
  [通用 Harness/Search/Camofox 参数]
  [--runs-dir PATH] [--output-dir PATH] [--nodes-dir PATH]... [--json]
```

```bash
# 检查 Hermes
deepresearch doctor --harness hermes --json

# 检查 Codex
deepresearch doctor --harness codex --json

# 检查 Claude Code
deepresearch doctor --harness claude-code --json

# 检查 OpenClaw Gateway 与 ACP
deepresearch doctor --harness openclaw --json

# 查看运行
deepresearch status RUN_ID
deepresearch status RUN_ID --json

# 恢复运行
deepresearch resume RUN_ID --harness hermes

# 只继续有限数量的节点实例
deepresearch resume RUN_ID --harness hermes --max-steps 3
```

`resume` 读取 Run 创建时固化的 Workflow 和 Node 快照，从未成功的节点实例继续；它不会用当前仓库的
新配置偷偷替换旧 Run 定义。

## 5. 节点发现和单节点执行

完整发现语法：

```text
deepresearch nodes list
  [--runs-dir PATH] [--output-dir PATH] [--nodes-dir PATH]... [--json]

deepresearch nodes describe NODE_ID
  [--runs-dir PATH] [--output-dir PATH] [--nodes-dir PATH]... [--json]
```

```bash
deepresearch nodes list
deepresearch nodes list --json

deepresearch nodes describe research
deepresearch nodes describe research --json

deepresearch node run NODE_ID \
  --query '单节点测试问题' \
  --harness hermes \
  --input PORT=/absolute/path/to/input.json
```

单节点执行的完整结构：

```text
deepresearch node run NODE_ID
  [--input PORT=PATH]...
  [--query QUERY]
  [--language LANGUAGE]
  [通用 Harness/Search/Camofox 参数]
  [--runs-dir PATH]
  [--output-dir PATH]
  [--nodes-dir PATH]...
  [--json]
```

`--input` 可以重复，但 Port 名不能重复；输入必须是存在的普通文件，不能是符号链接。

## 6. 搜索来源和领域

完整语法：

```text
deepresearch sources list
  [--search-dir PATH] [--search-provider-python PATH] [--json]
deepresearch sources describe SOURCE_NAME
  [--search-dir PATH] [--search-provider-python PATH] [--json]

deepresearch domains list
  [--search-dir PATH] [--search-provider-python PATH] [--json]
deepresearch domains describe DOMAIN_NAME
  [--search-dir PATH] [--search-provider-python PATH] [--json]
```

```bash
deepresearch sources list
deepresearch sources list --json
deepresearch sources describe academic_openalex --json

deepresearch domains list
deepresearch domains list --json
deepresearch domains describe academic --json
```

两组命令都支持：

```text
--search-dir PATH
--search-provider-python PATH
--json
```

- Source 是具体 Provider，例如 OpenAlex、Crossref、DuckDuckGo、GitHub Repositories。
- Domain 是面向 Agent 的搜索能力分组，例如 `academic`、`general_web`、
  `corporate_disclosure`、`financial_market`。
- Research Agent 先选择与证据目标相关的 Domain 和 operation；Search MCP 再由代码把一次领域调用
  并发展开到该 operation 配置的多个 Source。

## 7. Camofox 浏览器管理

```bash
deepresearch browser setup
deepresearch browser start
deepresearch browser status
deepresearch browser stop
```

完整参数：

```text
deepresearch browser setup [--home PATH] [--base-url URL] [--npm-command COMMAND] [--json]
deepresearch browser start [--home PATH] [--base-url URL] [--json]
deepresearch browser status [--home PATH] [--base-url URL] [--json]
deepresearch browser stop [--home PATH] [--base-url URL] [--json]
```

默认安装目录是 `~/.deepresearch-cli/camofox`，默认服务地址是
`http://127.0.0.1:9377`。Research 的 `fetch_url` 永远先执行普通 HTTP；只有出现反自动化挑战、
403、JavaScript 空壳或传输失败时才尝试一次 Camofox。未安装或未启动时会返回明确失败，Research
应切换来源，而不是让整个工作流阻塞。

## 8. Web 控制台

### 8.1 只启动控制台

```bash
deepresearch web
```

默认访问：<http://127.0.0.1:8765>

### 8.2 启动控制台并立即开始研究

```bash
deepresearch web '研究问题' \
  --mode normal \
  --report-format formal_report \
  --output-format markdown \
  --harness hermes
```

有启动 query 时，根地址会进入该次运行；没有 query 时显示创建任务页面。

Web 命令支持研究命令的大部分 Harness、Search、Camofox、目录和并发参数，另外支持：

```text
--host HOST    默认 127.0.0.1
--port PORT    默认 8765，范围 1–65535
```

完整结构：

```text
deepresearch web [QUERY]
  [--language LANGUAGE]
  [--mode quick|normal|heavy]
  [--report-format brief|formal_report]
  [--output-format markdown|html|pdf|docx]
  [--host HOST] [--port PORT]
  [--harness hermes|codex|claude-code|openclaw|codex-exec]
  [通用 Harness/Search/Camofox 参数]
  [--runs-dir PATH] [--output-dir PATH] [--nodes-dir PATH]... [--json]
```

Web 默认模式是 `heavy`；普通命令行研究默认模式是 `normal`。

## 9. 输出文件

```text
runs/<run-id>/
  manifest.json                 Run 请求、Workflow 与 Node 快照
  journal.jsonl                 追加式状态事件
  attempts/...                 每个节点实例的执行目录、日志和候选产物
  artifacts/...                已提交产物

output/<run-id>/
  report.md                    Markdown 主报告或其他格式的源报告
  report.html                  HTML 输出
  report.pdf                   PDF 输出
  report.docx                  DOCX 输出
```

## 10. 三种模式的实际节点链路

### 10.1 Quick

```text
research
  → report-writer
  → render
  → [md-html | md-pdf | md-docx，按输出格式可选追加]
```

特点：

- 没有 Scout 和 Plan。
- Research 直接针对原 query 执行一次全局检索，产生一份 Evidence。
- Report Writer 使用 `quick_synthesis`，读取全部 Evidence 一次写完整报告。
- 适合快速事实调研、简报和链路 smoke test。

### 10.2 Normal

```text
plan
  → research × N 个 dimension（并发）
  → report-writer
  → render
  → [md-html | md-pdf | md-docx，按输出格式可选追加]
```

特点：

- Plan 把 query 拆成研究维度，并由确定性 Materializer 生成 `research-task`。
- 每个 dimension 启动一个独立 Research 节点实例，受 `--max-concurrency` 限制并发。
- Report Writer 不再按章节拆分，而是读取所有维度 Evidence 一次写完整报告。
- 适合大多数正式调研：比 Quick 覆盖完整，比 Heavy 链路短。

### 10.3 Heavy

```text
scout
  → plan
  → research × N（第一轮，并发）
  → review × N
  → perspective × N
  → supplement-planner × N
  → research × M（补研，按需并发）
  → review × M
  → perspective × M
  → report-planner
  → report-writer × K 个 content unit（并发）
  → stitcher（确定性代码）
  → final-review-diagnostic
      ├─ pass ───────────────────────────────┐
      └─ revise → final-repair × R（并发）   │
                   → final-review-recheck    │
  → render（确定性代码）←────────────────────┘
  → [md-html | md-pdf | md-docx，按输出格式可选追加]
```

其中：

- `N` 是 Plan 生成的初始研究维度数。
- `M` 是 Supplement Planner 实际生成的补研任务数；没有补研任务时第二轮相关实例自动跳过。
- `K` 是 Report Planner 生成的内容单元数。
- `R` 是 Final Review 点名需要修复的内容单元数。
- 同一步骤的多个 scope 实例并发执行，上限由 `--max-concurrency` 控制；不同步骤之间仍按 Workflow
  顺序推进。

首次 Final Review 为 `pass` 时，不产生 repair/recheck task，`final-repair` 与
`final-review-recheck` 自动跳过。首次为 `revise` 时只允许一次定向修复；复审仍为 `revise` 会使
工作流失败，不会无限循环。

## 11. 每个节点做什么、输入和输出是什么

### 11.1 研究与规划节点

| 节点 | 类型 | 作用 | 主要输入 | 主要输出 |
|---|---|---|---|---|
| `scout` | Agent | Heavy 正式规划前做轻量领域扫描，补齐实体、术语、候选分区和来源入口；不回答问题、不决定报告结构 | 原 query 和运行上下文 | `briefing.json` (`briefing`) |
| `plan` | Agent + 确定性 Materializer | 把 query/briefing 转成覆盖模型、研究维度、关键问题和来源计划；代码按维度生成任务 | 可选 `briefing` | `plan.json` (`research-plan`)；`research-tasks/*.json` (`research-task`) |
| `research` | Agent | 按一个研究任务搜索、读取正文、提取 claims/source/冲突/缺口，产出结构化证据；补研时合并已有 Evidence | 可选 `task`、`plan`、已有 `evidence`、`supplement-plan` | `evidence.json`；可选完成态 `supplement-plan.completed.json` |
| `review` | Agent | 审查单个维度 Evidence 的来源质量、claim 支撑、完整性和引用边界；只做审计，不作为正式证据 | 一个 `evidence`；可选 `plan` | `review.md` |
| `perspective` | Agent | 按 Plan 中的 lenses 检查单维度 Evidence 的覆盖缺口、反例和遗漏视角 | 一个 `evidence`；可选 `plan` | `perspective.md` |
| `supplement-planner` | Agent + 确定性 Materializer | 聚合当前维度的 Evidence、Review 和 Perspective，把问题二分为需要补研与延期项，并按需生成补研任务 | `perspective`、`plan`、一个 `evidence`、一个 `review` | `supplement-plan.json`；可选 `research-tasks/*.json` |

### 11.2 报告规划与写作节点

| 节点 | 类型 | 作用 | 主要输入 | 主要输出 |
|---|---|---|---|---|
| `report-planner` | Agent + 确定性 Materializer | Heavy 根据 query 和全部 Evidence 决定文章组织、content units、每个 unit 的 render-contract 与证据边界；代码派生内容任务 | `plan`、全部 `evidence` | `outline.json`；`content_units/*.evidence_subset.json` |
| `report-writer` | Agent | Quick/Normal 时一次写整篇；Heavy 时每个 content unit 单独写，并严格遵守该 unit 的证据子集和 render-contract | 可选 `content-task`、可选 `outline`、全部或路由后的 `evidence` | `draft.md` (`report-draft`) |
| `stitcher` | Script | 按 Outline 顺序确定性拼接 Heavy 的 content-unit 草稿，并执行标题、结构、render-contract、引用键与 claim-source 路由检查 | `outline`、全部 `drafts`、全部 `evidence` | `stitched.md` (`stitched-report`) |

`stitcher` 不再依赖模型阅读全文后“凭感觉”拼接。它通过 Python 稳定检查：

- content unit 是否齐全、唯一并按顺序出现；
- 标题是否符合 `show_heading`；
- 表格、列表和二级结构是否符合 render-contract；
- 引用键是否来自合法 Source ID；
- routed claim 是否在合法 element 中获得引用；
- 是否泄漏 claim ID、脚注定义或参考文献章。

### 11.3 Final Review 与一次定向修复

| 节点 | 类型 | 作用 | 主要输入 | 主要输出 |
|---|---|---|---|---|
| `final-review-diagnostic` | Agent + 确定性 Materializer | 首次审查 stitched 成品是否直接回答 query、兑现 Outline、遵守 Evidence 和引用边界；`revise` 时解析稳定的 `REPAIR_TARGET` | stitched report、plan、全部 evidence、outline、drafts 和审计材料 | `final-review.md`、`decision.json`、可选 `repair-tasks` 和一个 `recheck-task` |
| `final-repair` | Agent | 每个实例只修复一个被点名 content unit，不重新搜索、不改 Outline、不跨 Evidence 边界 | `repair-task`、对应 `content-task`、首次 Review、outline、原 draft | `repaired-draft.md` |
| `final-review-recheck` | 确定性 Preparer + Agent | Preparer 先用修复稿替换对应原稿并重新确定性拼接；Agent 再执行唯一一次复审 | 一个 recheck gate、plan、evidence、outline、原 drafts、repairs 和审计材料 | 新 `stitched.md`、新 `final-review.md` |
| `final-review` | Agent | 通用最终审查节点定义 | stitched report、plan、evidence、outline、drafts 和审计材料 | `final-review.md` |

`final-review` 已注册，可供自定义 Workflow 或单节点执行；三个内置模式当前不直接引用它。Heavy 使用
带修复任务 Materializer 的 `final-review-diagnostic` 和带重拼 Preparer 的
`final-review-recheck`。

### 11.4 渲染与文件转换节点

| 节点 | 类型 | 作用 | 主要输入 | 主要输出 |
|---|---|---|---|---|
| `render` | Script | 从 draft/stitched 和全部 Evidence 确定性生成 Markdown，解析合法引用，生成脚注与参考文献，按标记插入目录 | `report-draft` 或 `stitched-report`；全部 `evidence` | `report.md` (`report`) |
| `md-html` | Agent | 把最终 Markdown 转成 HTML 并校验 HTML 报告 | `report.md` | `report.html` |
| `md-pdf` | Script | 使用内置 Typst 视觉模板把 Markdown 转成 PDF | `report.md`、`report.typ` | `report.pdf` |
| `md-docx` | Script | 使用内置 Word reference template 把 Markdown 转成可编辑 DOCX | `report.md`、`reference.docx` | `report.docx` |

格式节点由编译器自动追加：

| `--output-format` | `render` 后追加节点 | 最终主产物 |
|---|---|---|
| `markdown` | 无 | `report.md` |
| `html` | `md-html` | `report.html`，同时保留 `report.md` |
| `pdf` | `md-pdf` | `report.pdf`，同时保留 `report.md` |
| `docx` | `md-docx` | `report.docx`，同时保留 `report.md` |

## 12. 各模式节点超时

单位均为秒。这里只列 Agent 节点；确定性 Script 节点不设置 Workflow 超时。

| 节点 | Quick | Normal | Heavy |
|---|---:|---:|---:|
| `scout` | — | — | 300 |
| `plan` | — | 300 | 300 |
| `research` | 1500 | 1500 | 1500 |
| `review` | — | — | 300 |
| `perspective` | — | — | 300 |
| `supplement-planner` | — | — | 240 |
| `report-planner` | — | — | 300 |
| `report-writer` | 300 | 420 | 600 |
| `final-review-diagnostic` | — | — | 420 |
| `final-repair` | — | — | 420 |
| `final-review-recheck` | — | — | 420 |
| `md-html` | 900 | 1200 | 1800 |

同一 Workflow 中重复出现的同类节点使用统一 Node ID 超时，因此 Heavy 的两轮 `research` 都是
1500 秒，两轮 `review` 都是 300 秒，两轮 `perspective` 都是 300 秒。

`--node-timeout-seconds` 只为 Workflow 没有声明超时的 Agent 节点提供兜底；
`--no-node-timeout` 只关闭这个兜底，不会移除表中已声明的超时。

## 13. 模式选择建议

| 场景 | 推荐模式 |
|---|---|
| 验证 CLI、快速回答、短简报 | Quick |
| 一般正式调研、多维度搜索、控制耗时 | Normal |
| 高风险决策、复杂跨领域问题、需要补研和最终修复闭环 | Heavy |

如果只是要正式报告，不代表必须使用 Heavy。`formal_report` 控制写作形式，`mode` 控制研究链路；
大多数日常正式报告可先使用 `normal + formal_report`。
