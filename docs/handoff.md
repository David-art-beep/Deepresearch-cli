# DeepResearch 配置运行时交接

更新日期：2026-08-13
开发分支：`agent/deepresearch-config-workflows`

## 当前状态

CLI 已切换为唯一的配置运行时：

- Quick、Normal、Heavy 是根目录 `config/workflows/*.yaml`。
- Agent 与 Script 共用 Node Spec、统一 Context、Artifact 发布和恢复逻辑。
- `--output-format html` 自动追加 md-html；`pdf` 自动追加 md-pdf；
  `docx` 自动追加 md-docx。
- `runs/` 保存状态与中间文件；最终结果导出到 `output/<run-id>/`。
- Manifest 是 schema 2 / config-workflow；旧 Run 明确拒绝。
- 旧 `workflow/`、`executors/`、Graph、Policy、Input Selector 和 Prompt Assembler 已删除。

## 用户入口

```bash
deepresearch "研究问题" --mode quick --report-format brief --output-format markdown --harness hermes
deepresearch "研究问题" --mode heavy --report-format formal_report --output-format html --harness hermes
deepresearch "研究问题" --workflow ./flow.yaml --nodes-dir ./nodes --mode heavy --report-format formal_report --harness hermes

deepresearch status <run-id> --json
deepresearch resume <run-id> --harness hermes

deepresearch nodes list --json
deepresearch nodes describe md-html --json
deepresearch node run md-html --input report=./report.md --harness hermes
```

不存在旧 `deepresearch run ...` 兼容别名。

## 主要代码入口

| 修改类型 | 入口 |
| --- | --- |
| Workflow YAML 加载 | `config/workflows.py` |
| 顺序编译与端口绑定 | `config/compiler.py` |
| Node/Workflow/Artifact 模型 | `config/models.py` |
| 根目录 Node YAML 加载 | `config/registry.py` |
| 顺序、fan-out、resume、结果导出 | `driver.py` |
| Agent/Script 统一执行与发布 | `node_runner.py` |
| Manifest、Journal、Artifact 安全边界 | `persistence/store.py` |
| Hermes/Codex/Claude Code 生命周期 | `harness/` |
| CLI 命令编排 | `cli.py`、`service.py` |
| Search MCP、run 级 Coordinator 与 SQLite WAL | `src/deepresearch_cli/search/`、`harness/search_coordinator.py` |
| 用户可配置搜索源、`.env` | 根目录 `search/` |

Driver 里不应出现根据具体 Node ID 决定跳转或输入的分支。新增能力优先增加 Node YAML；新增流程只修改 YAML。

## Artifact 合同

正式 ArtifactRef 只包含：

```text
port, type, media_type, path, sha256, scope, mode, step_id, instance_id
```

输入模式是 `one | all | each`；输出模式是 `state | batch`。运行时只检查声明、路径、非空、hash 与发布边界，节点 Validator 负责必要的最小业务结构。

统一模型上下文只有：

```text
run / step / scope / inputs / outputs
```

Script 用 `DEEPRESEARCH_NODE_CONTEXT` 读取同一结构。

## Heavy 第二轮

Heavy YAML 直接重复：

```text
research → review → perspective → supplement-planner
→ research → review → perspective
```

SupplementPlanner 的 batch 为空时，第二组 Step 没有 scope，自动跳过；非空时按 batch scope 执行。这不是 Driver 的补研特例。

## HTML

md-html 是普通 Agent 节点，不再嵌套或加载 Skill：

```text
config/nodes/md-html.yaml
prompts/v0.1/md-html.md
src/deepresearch_cli/node_validators/md_html.py
```

它接收一个 Markdown `report` Artifact，输出 `plan.md` 与 primary `report.html`。HTML Run 同时导出 HTML 和 Markdown 源报告。

## 恢复与不兼容边界

Run 创建时快照编译后的 Workflow 和本 Run 使用的完整 Node Spec。自定义节点的相对 Prompt、脚本、Validator 与资源进入快照；resume 不重新读取本机当前 YAML。

以下内容直接报错：

- `schema_version` 不是 `2`；
- `runtime` 不是 `config-workflow`；
- Workflow/Node 快照摘要不匹配；
- Artifact 文件缺失、路径逃逸或 hash 改变；
- Journal 非连续、重复 event ID 或输入引用尚未提交的 Artifact。

不要增加旧 Run 转换器、旧 Driver 构造参数或 CLI alias。

## 测试

```bash
uv run pytest
uv build
```

普通 suite 覆盖：YAML 编译、重复节点、空/非空补研 batch、端口 fan-out、并发、resume、一次 Agent repair、HTML 导出、Script/Agent Node YAML、Artifact 篡改和旧 Manifest 拒绝。

真实 Hermes/Codex/Claude Code smoke test 默认跳过，显式运行可能产生费用：

```bash
DEEPRESEARCH_LIVE_HERMES=1 \
  uv run pytest tests/test_live_hermes_acceptance.py -m live_hermes -s

DEEPRESEARCH_LIVE_CODEX=1 \
  uv run pytest tests/test_live_codex_acceptance.py -m live_codex -s

DEEPRESEARCH_LIVE_CLAUDE=1 \
  uv run pytest tests/test_live_claude_acceptance.py -m live_claude -s
```

普通测试通过不等于模型质量或搜索 provider 凭据已经验收。

## 已知边界

- completed 表示配置步骤执行完成，不表示 FinalReview 给出质量通过结论。
- failed Run 目前不能 reopen/fork。
- Hermes 本地文件工具没有额外 OS 沙箱；端口白名单不等于系统隔离。
- Codex 默认通过 ACP Bridge 调用 `codex app-server`，使用 `workspaceWrite` 沙箱、非交互审批和进程级超时终止；`codex-exec` 保留为兼容回退，真实验收需要本机已完成 `codex login`。
- Claude Code 通过 `@agentclientprotocol/claude-agent-acp` 接入；真实验收需要 Node.js 22+、已安装 Adapter，并已完成 Claude Code 登录或配置受支持的 Provider 环境。
- 内置 Search 脚本已迁入根目录 `search/providers/`，不再依赖外部 SenseNova-Skills；凭据由
  `search/.env` 配置。搜索层现有 8 个 `search/domains/*.yaml` 领域配置和独立 Source 注册：学术聚合
  中隐藏的 OpenAlex、Crossref、arXiv、Semantic Scholar、PubMed、Google Scholar、Wikipedia 已拆成
  单独 Source。Research 优先使用 `list_search_domains`、`start_domain_search`、`get_search_batch`，
  Source 级旧工具保留兼容。P3 已改为 Run 级共享 Coordinator/SQLite WAL：各 Research attempt
  使用独立 stdio 代理和 namespace，共享全局并发、熔断、去重与已完成 provider/query 执行；
  `resume` 会重开同一数据库。
- P4 已把 Domain/Source telemetry 接入 Web：页面实时显示 Domain 完成度、Source 调用和耗时、API
  调用、缓存复用及 Raw/Unique/Fetched/Evidence 漏斗。Fetched 来自有界 ACP 工具进度投影，
  Evidence 来自正式 Artifact，不保存 fetch 返回正文。
