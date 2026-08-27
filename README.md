# DeepResearch CLI

DeepResearch CLI 是一套配置优先、可持久化、可恢复的研究工作流运行时。Quick、Normal、Heavy 都是普通 YAML；新增节点通过独立 Node YAML 注册，不需要修改 Driver，也没有 Graph、Policy、Input Selector 或隐藏跳转语法。

当前实现是破坏式新合同：CLI 只创建和读取 `schema_version: "2"`、`runtime: config-workflow` 的 Run。旧 Run 不读取、不迁移、不能 resume。

## 快速使用

```bash
uv sync --extra dev
uv run deepresearch doctor --harness hermes --json
# 也可使用已登录的 Codex CLI
uv run deepresearch doctor --harness codex --json
# 或使用 Claude Code 的 ACP Adapter
uv run deepresearch doctor --harness claude-code --json

uv run deepresearch "研究问题" \
  --mode heavy \
  --report-format brief \
  --output-format markdown \
  --harness hermes

uv run deepresearch "研究问题" \
  --mode heavy \
  --report-format formal_report \
  --output-format html \
  --harness hermes

uv run deepresearch "研究问题" \
  --mode heavy \
  --report-format formal_report \
  --output-format pdf \
  --harness hermes

uv run deepresearch "研究问题" \
  --mode heavy \
  --report-format formal_report \
  --output-format docx \
  --harness hermes
```

运行成功后，中间状态保存在 `runs/<run-id>/`，最终文件单独导出到：

```text
output/<run-id>/report.md
output/<run-id>/report.html   # --output-format html 时
output/<run-id>/report.pdf    # --output-format pdf 时
output/<run-id>/report.docx   # --output-format docx 时
```

JSON 输出中的 `result.path` 与普通文本中的 `result_path` 都指向 `output/` 下的最终文件；HTML、PDF 和 DOCX 结果还返回 Markdown 源报告的 `source_report_path`。

`--mode`、`--report-format` 和 `--output-format` 分别控制不同事情：

- `--mode quick|normal|heavy`：研究流程的深度和节点拓扑。
- `--report-format brief|formal_report`：写作形式。交互式 CLI 未传该参数时会
  弹出菜单让用户选择；脚本、管道和 CI 等非交互环境必须显式传入。Web 启动页中为无默认值的必选项。
- `--output-format markdown|html|pdf|docx`：最终文件容器。

正式报告会根据 query 从 `assets/report-templates/content/templates.yaml` 选择一个内容模板。
Heavy 模式由 Report Planner 选择后写入 Outline，Writer 直接执行；Quick/Normal 由 Writer 选择一次。
用户在 query 中明确指定的目录、章节和顺序优先；内容模板只用于补充覆盖检查和证据组织参考，
不会覆盖或重排用户结构，也不影响 PDF/Word 的独立视觉模板。

```bash
uv run deepresearch status <run-id> --runs-dir ./runs --output-dir ./output --json

uv run deepresearch resume <run-id> \
  --harness hermes \
  --runs-dir ./runs \
  --output-dir ./output
```

### Web 研究进度控制台

启动本地控制台：

```bash
uv run deepresearch web
```

然后访问 <http://127.0.0.1:8765>，输入研究问题并选择研究模式、报告形式和交付格式。默认只监听
本机地址，不会把控制台暴露到局域网。需要改目录或端口时：

```bash
uv run deepresearch web \
  --port 9000 \
  --runs-dir ./runs \
  --output-dir ./output
```

也可以在启动 Web 服务时直接传入研究参数，跳过填写页面并立即开始：

```bash
uv run deepresearch web "分析 2026 年企业级 AI Agent 平台的竞争格局" \
  --mode heavy \
  --report-format formal_report \
  --output-format pdf \
  --language zh-CN \
  --harness hermes
```

启动后访问根地址会自动进入这次运行的进度页。其余执行参数也可以直接使用，例如
`--harness-profile`、`--max-concurrency`、`--node-timeout-seconds` 和
`--no-search-mcp`。不传研究问题时仍然显示原来的新建任务页面。

Quick、Normal 和 Heavy 都可以使用 Web 控制台。页面会按当前模式的实际节点显示总体完成度、
研究阶段、研究维度、证据/来源数量、章节写作状态和活动流；Normal 不会显示 Heavy 独有的
Review、Perspective 或分章节规划节点。进度不是计时器或模型猜测，而是从已提交到 Journal 的节点与章节实例
实时重建；浏览器用 SSE 接收更新。刷新页面后，数据仍可从 Manifest、Journal 和
Artifact 恢复。服务重启后，打开原运行地址并点击“恢复此运行”即可继续。

Heavy 的 `report-planner` 产出内容任务后，页面才知道准确的写作章节总数；并行的
`report-writer` 实例按真实完成顺序更新。Normal 和 Quick 没有分章节 Planner，页面改为按其
实际工作流节点计算进度。命令行的 `status --json` 仍只为 Heavy 返回细粒度 `progress`
对象；Web 会为所有模式补充浏览器所需的工作流进度。

## 工作流 YAML

工作流包含四个必填字段和一个可选的 `timeouts` 字段，不引入另一门流程语言：

```yaml
version: 1
name: quick
steps:
  - research
  - report-writer
  - render
timeouts:
  research: 480
  report-writer: 300
result: report
```

`steps` 就是执行顺序，`timeouts` 的单位是秒，并且只用于 Agent 节点。确定性 Script 节点直接执行，
不接受 Workflow 超时，也不使用 CLI 超时兜底。Agent 超时可以按 Node ID 配置；重复节点还可以用编译后的
Step ID 单独覆盖，例如 `research` 作用于第一轮并作为后续同类节点的默认值，`research-2` 只覆盖
第二轮。Workflow 超时优先于 `--node-timeout-seconds`；CLI 参数只为没有配置的 Agent 节点提供兜底。
`--no-node-timeout` 只关闭这个兜底，不会移除 Workflow 已声明的节点预算。
重复节点表示再次执行。例如补研后再次 Review 和 Perspective，只需这样写：

```yaml
version: 1
name: custom-heavy
steps:
  - scout
  - plan
  - research
  - review
  - perspective
  - supplement-planner
  - research
  - review
  - perspective
  - report-planner
  - report-writer
  - stitcher
  - final-review-diagnostic
  - final-repair
  - final-review-recheck
  - render
timeouts:
  research: 1140
  research-2: 900
  report-writer: 600
result: report
```

运行自定义流程：

```bash
uv run deepresearch "研究问题" \
  --workflow ./my-workflow.yaml \
  --mode normal \
  --report-format formal_report \
  --output-format markdown \
  --harness hermes
```

`--workflow` 决定执行哪些节点和顺序，`--mode` 决定 Plan 等节点采用 `quick`、`normal` 还是 `heavy` 业务合同；两者可以组合。自定义 Workflow 未显式传 `--mode` 时默认使用 `normal`。

仓库内的 [`examples/custom-workflow/`](examples/custom-workflow/) 提供了一套可直接运行的完整示例：它注册自定义 Script Node，把 Plan 阶段产物扩展为 8 个独立 Research 任务，再以 `--max-concurrency 8` 执行完整研究和报告链路。

所有内置配置统一位于仓库根目录 `config/`：流程在 `config/workflows/`，节点在 `config/nodes/`。编译器根据 `--output-format` 自动追加 `md-html`、`md-pdf` 或 `md-docx`；工作流本身不用为不同交付格式维护多份拓扑。

## Node 配置

一个节点对应一份 YAML，文件名等于节点 ID。Agent 节点声明 Prompt 和输入输出端口；Prompt、脚本和 Validator 可以作为同目录的相对文件：

```text
my-nodes/
├── summarize.yaml
├── summarize.md
└── summarize-validate.py
```

```yaml
version: 1
id: summarize
kind: agent
prompt: summarize.md
inputs:
  evidence:
    type: evidence
    media_type: application/json
    mode: all
outputs:
  report:
    path: report.md
    type: report
    media_type: text/markdown
    mode: state
    primary: true
validator: [python, ./summarize-validate.py]
```

一个节点需要依次校验多个不同业务产物时使用 `validators`，其中每一项都是独立命令；
`validator` 与 `validators` 不能同时声明：

```yaml
validators:
  - [python, resource:validate_evidence.py, --node-context]
  - [python, resource:validate_supplement_plan.py, --node-context]
```

每种 JSON 只维护一个正式结构 Validator。Node YAML 应直接引用这份 Validator；节点级额外检查
只检查跨文件数量、文件名或工作流状态，不得复制 JSON 字段规则。

Validator 采用消费者驱动边界：只将下游实际读取的字段、类型、ID 引用、
scope 归属、派生一致性和文件安全作为硬错误。不影响消费的扩展字段、内容数量、
表达方式和质量建议不得触发 Repair；质量信号应记为 warning。Runtime 自有字段
与会改变派生语义的冲突字段仍必须拒绝。

当 batch 文件或索引可以从正式 JSON 确定性生成时，使用可选 `materializer`。它在 Agent/Script
完成后、候选产物封存前运行，可以写入派生输出；随后正式 Validator 对正式 JSON 和所有派生文件
一起做只读校验：

```yaml
materializer: [python, ./derive-tasks.py]
validator: [python, ./validate-plan.py, --node-context]
```

Script 节点只需把 `kind` 改为 `script` 并声明命令：

```yaml
version: 1
id: post-process
kind: script
command: [python, ./post-process.py]
inputs:
  report:
    type: report
    media_type: text/markdown
    mode: one
outputs:
  report:
    path: report.md
    type: report
    media_type: text/markdown
    mode: state
    primary: true
```

命令通过 `DEEPRESEARCH_NODE_CONTEXT` 读取统一 JSON Context。自定义节点的相对 Prompt、脚本、Materializer 和 Validator 会随 Node Spec 快照写入 Run，不依赖 resume 时的源码文件。节点运行时不支持 `skill:` 或 `--skills-dir`；`md-html` 已迁移为普通 Agent 节点，其 Prompt 位于 `prompts/v0.1/md-html.md`。

注册和检查自定义节点：

```bash
uv run deepresearch nodes list --nodes-dir ./my-nodes --json
uv run deepresearch nodes describe summarize --nodes-dir ./my-nodes --json
```

在工作流中直接把 `summarize` 写入 `steps`，并在运行时增加 `--nodes-dir ./my-nodes`。也可以单独执行一个节点：

```bash
uv run deepresearch node run md-html \
  --input report=./report.md \
  --harness hermes \
  --no-search-mcp \
  --node-timeout-seconds 1800
```

`md-html` 会先设计页面，再分块写入和复核单文件 HTML；长报告通常需要超过
默认的 600 秒。单独转换已有 Markdown 时不需要搜索 MCP，建议使用上面的
30 分钟节点超时。

Agent 节点需要 Harness；Script-only 单节点命令不启动 Hermes，`--harness` 可以省略。

### Word 与 PDF 转换节点

内置 `md-docx` Script Node 使用 Pandoc 把 Markdown 报告转换为可编辑的
Word 文档；内置 `md-pdf` Script Node 使用 Pandoc/Typst 把同一份 Markdown
报告排版为 PDF。转换器会把 Markdown 的第一个一级标题作为封面标题，并自动
生成封面、日期和两级目录；原始 Markdown 不需要额外添加 YAML 元数据。这两个
节点可以单独执行：

```bash
# macOS 安装 DOCX 转换器
brew install pandoc

# 安装 PDF 转换器
brew install typst

uv run deepresearch node run md-docx --input report=./report.md
uv run deepresearch node run md-pdf --input report=./report.md

# 同时生成 Word 和 PDF
uv run python scripts/convert_report.py ./report.md --output-dir ./output
```

可以通过 `DEEPRESEARCH_PANDOC` 指定 Pandoc 可执行文件；通过
`DEEPRESEARCH_DOCX_REFERENCE` 覆盖内置的
[`assets/report-templates/word/reference.docx`](assets/report-templates/word/reference.docx)，
控制 Word 的字体、标题、页边距和页眉页脚。研究命令使用 `--output-format docx` 时会在
`render` 后自动追加 `md-docx`；使用 `--output-format pdf` 时会自动追加
`md-pdf`。PDF 不经过 HTML，因此网页动画和交互不会影响文档排版。转换节点
也可以像上面这样单独执行。通过 `DEEPRESEARCH_PDF_TEMPLATE` 可以覆盖内置的
[`assets/report-templates/pdf/report.typ`](assets/report-templates/pdf/report.typ)，
通过 `DEEPRESEARCH_TYPST` 可以指定 Typst 可执行文件。文本和二进制模板都会
随 Node Spec 快照进入 Run，后续 resume 不依赖当前 assets 文件。

内置模板面向中文研究报告优化：PDF 使用独立封面、静态目录、页眉页脚以及适合
宽表格的紧凑表格样式；Word 使用可编辑样式、带真实页码的标准动态目录、表头
底色和斑马纹。Word 的封面、目录和正文分页位于目录域外，更新整个目录不会改变
三者的分页关系。Word 与 PDF 各自维护模板，不共享版式实现。

## 最小 Artifact 传递规则

运行时不理解 Claims、Evidence 或报告正文的业务 schema，只处理节点声明的端口：

- 输入通过 `type + media_type` 与之前最近的兼容输出连接。
- `one` 读取当前 scope 的一个最新 state；`all` 读取该类型所有当前 state；`each` 为上游 batch 的每个 scope 创建一个节点实例。
- `state` 输出覆盖同类型、同 scope 的当前值；`batch` 输出用 glob 产生零到多个带 scope 的 Artifact。
- `required: true` 只检查文件是否存在、非空且路径安全；节点自己的 Validator 可以增加业务检查。
- `validator` 执行一条命令；`validators` 按声明顺序执行多条命令，两者互斥。
- `materializer` 在封存前生成机械派生文件；失败时与 Agent Validator 一样可触发一次修复 attempt。
- Validator 只能读取已封存候选文件，修改候选会被拒绝；多条 Validator 的 warning 会合并记录。
- Agent Validator 失败默认允许一次新的 attempt 修复；Script Validator 失败直接终止。节点可用
  `repair_on_validation_failure: false` 关闭无意义的审核重试。

每个 Agent 只接收一个统一 Context：

```json
{
  "run": {"id": "...", "query": "...", "language": "zh-CN", "mode": "heavy", "output_format": "html"},
  "step": {"id": "research-2", "node": "research", "instance": "...", "attempt": 1},
  "scope": {"dimension-id": "d1"},
  "inputs": {"task": [{"type": "research-task", "path": "/absolute/read-only/path"}]},
  "outputs": {"evidence": {"type": "evidence", "path": "/absolute/staging/evidence.json"}}
}
```

节点只能读取声明的输入，并把结果写入声明的输出路径。Driver 只负责顺序、scope、attempt、发布与恢复，不包含节点名称分支。

## 持久化边界

```text
runs/<run-id>/
├── run.json          # 不可变：请求、编译后的 workflow、完整 Node Spec 快照和摘要
├── journal.jsonl     # 追加式：step_started / step_finished / run_finished
├── artifacts/        # 已封存、校验并发布的正式 Artifact
└── attempts/         # staging、模型轨迹、stderr、validator diagnostics
```

`status` 和 `resume` 只从 Manifest、Journal 与 Artifact 重建状态。`attempts/` 可以用于诊断，但不是工作流状态。完成后的报告复制到 `output/`，因此用户不需要进入 `runs/.../artifacts/...` 寻找最终结果。

## Harness 与搜索

生产 CLI 支持 `hermes`、`codex` 和 `claude-code` 三种 ACP Harness。Hermes 直接运行原生 ACP Agent；
Codex 通过 `codex-acp-bridge` 将 ACP 映射到 `codex app-server`；Claude Code 使用 ACP 官方组织维护的
`@agentclientprotocol/claude-agent-acp`。每个 Agent attempt 都使用独立进程，
`--max-concurrency` 控制同时运行的 attempt 数。旧的 `codex exec --json` 适配保留为
`--harness codex-exec`，用于兼容和故障回退。Research attempt 默认获得独立的 stdio 搜索 MCP
代理；同一 run 的代理共享一个 Search Coordinator 和 SQLite WAL，并通过 namespace 隔离可见结果，
不会修改任一 Harness 的全局 MCP 配置。

Codex 先完成登录，再运行：

```bash
codex login

uv run deepresearch "研究问题" \
  --mode heavy \
  --report-format formal_report \
  --harness codex \
  --search-dir ./search
```

可选的 `--harness-profile`、`--harness-model` 和 `--harness-command`
分别选择 Codex profile、模型和可执行文件。不传 profile 时，DeepResearch 使用
Codex App Server 的默认配置并复用已保存的登录状态。

Claude Code ACP Adapter 需要 Node.js 22 或更高版本。安装 Adapter 并复用 Claude Code 登录：

```bash
npm install -g @agentclientprotocol/claude-agent-acp
claude-agent-acp --cli auth login

uv run deepresearch "研究问题" \
  --mode heavy \
  --report-format formal_report \
  --harness claude-code \
  --search-dir ./search
```

在 `claude-code` Harness 下，`--harness-command` 指向 `claude-agent-acp` 可执行文件，
`--harness-model` 设置 Claude 模型，`--harness-profile` 指定 `CLAUDE_CONFIG_DIR`。已有的
`ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN`、Bedrock 或 Vertex 环境配置也会被 Adapter 继承。

搜索能力也是用户配置。仓库根目录 [`search/`](search/) 是一个完整注册表：本机凭据放在被 Git 忽略的
`search/.env`，`search/sources/*.yaml` 每个文件注册一个底层 Source，`search/domains/*.yaml` 把
Source 按研究任务组合成 Domain/Operation。Research 通常选择所有相关 Domain，由 MCP 并发调用各
Operation 声明的 Source；旧的 Source 级 `batch_search` 继续保留。增加 Source 或调整领域路由不需要
修改 Python 固定 catalog。

```bash
cp search/.env.example search/.env
# 按需填写 search/.env 中各搜索源的凭据

uv run deepresearch sources list --search-dir ./search --json
uv run deepresearch sources describe academic --search-dir ./search --json
uv run deepresearch domains list --search-dir ./search --json
uv run deepresearch domains describe academic --search-dir ./search --json
```

使用内置或自定义注册表：

```bash
uv run deepresearch "研究问题" \
  --mode heavy \
  --report-format formal_report \
  --harness hermes \
  --search-dir ./search \
  --search-provider-python /path/to/python
```

完整搜索合同见 [`docs/search-mcp.md`](docs/search-mcp.md)。

### Camofox 代码级回退（可选）

Research 的 Search MCP 提供统一 `fetch_url`：代码固定先执行普通 HTTP，只有遇到 403、明确
反自动化挑战、JavaScript 空壳或传输失败时，才通过 Camofox REST 执行一次
create/snapshot/close 回退。Agent 不再获得原始 Camofox 操作工具，也不能自行选择 click、type 或
Cookie 导入。该能力不替代搜索，也不修改任何 Harness 的全局配置。

CLI 管理固定版本的 Camofox REST server 和 Camoufox 内核。首次 setup 需要 Node.js 22+，会
下载约 300MB 的资源；解压后的内核和 Node 依赖合计约占用 750MB 磁盘空间：

```bash
uv run deepresearch browser setup
uv run deepresearch browser start
uv run deepresearch browser status

uv run deepresearch "研究问题" \
  --mode heavy \
  --report-format formal_report \
  --harness hermes \
  --camofox-fallback
```

默认安装目录是 `~/.deepresearch-cli/camofox`，服务只绑定 `127.0.0.1:9377`，并关闭 Camofox
崩溃遥测。可用 `--home` 管理另一套安装，Research 对应传入 `--camofox-home`。停止 CLI 管理的
服务：

```bash
uv run deepresearch browser stop
```

每个 Research attempt 使用独立的 Camofox 用户与 Session 标识。代码禁止私网目标、同一 URL
重复回退和 429 浏览器重试，并在成功、失败、超时或 CAPTCHA 情况下都执行标签页关闭。不允许登录、
导入 Cookie、填写表单或绕过 CAPTCHA、付费墙和访问控制。Camofox 未安装或服务不可用时返回明确
失败原因，Research 必须切换来源，不阻塞 Evidence 产物。`--camofox-fallback` 依赖默认启用的 Search
MCP，不能与 `--no-search-mcp` 同时使用。

### Agent 自动安装 Skill

仓库提供独立的 [`deepresearch-installer`](skills/deepresearch-installer/SKILL.md) Skill。它用于让
Hermes、Codex 或 Claude Code Agent 检查本机环境，并在得到必要授权后安装 CLI、下载和启动 Camofox、执行
所选 Harness 的检查与 Camofox 健康检查。
Skill 不包含平台相关浏览器运行文件；这些文件仍由 Agent 调用 `deepresearch browser setup`
下载到 CLI 私有目录。

同一个 Skill 目录兼容 Hermes、Codex 与 Claude Code ACP。发布到 Hermes Skill 注册表：

```bash
hermes skills publish ./skills/deepresearch-installer \
  --to github \
  --repo <owner>/<skills-repo>
```

发布后，用户可通过注册表标识或指向 `SKILL.md` 的 HTTPS 地址安装，再对 Agent 说：

```text
使用 $deepresearch-installer，从默认仓库 https://github.com/David-art-beep/Deepresearch-cli
安装 DeepResearch CLI 和 Camofox，
并验证 Hermes（也可以选择 Codex、Claude Code ACP，或同时验证多个 Harness）。
```

Codex 与 Claude Code 可安装同一个 `skills/deepresearch-installer/` 目录，无需维护另一份 Skill。

## 验证

```bash
uv run pytest
uv build
```

普通测试使用确定性 Stub，不调用模型。真实 Hermes、Codex、Claude Code smoke test 为显式门禁，可能产生网络调用和费用：

```bash
DEEPRESEARCH_LIVE_HERMES=1 \
  uv run pytest tests/test_live_hermes_acceptance.py -m live_hermes -s

DEEPRESEARCH_LIVE_CODEX=1 \
  uv run pytest tests/test_live_codex_acceptance.py -m live_codex -s

DEEPRESEARCH_LIVE_CLAUDE=1 \
  uv run pytest tests/test_live_claude_acceptance.py -m live_claude -s
```

实现细节和扩展约束见 [`docs/design.md`](docs/design.md)，当前交接信息见 [`docs/handoff.md`](docs/handoff.md)。
