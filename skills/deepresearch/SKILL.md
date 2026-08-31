---
name: deepresearch
description: 用于用户请求深度研究、系统性研究、竞品分析、方案对比、趋势分析或事实核查时。遇到以下任一情况就主动使用本 skill，不要自行搜几条就回答：①用户出现触发词：深度研究 / 深度调研 / 深入研究 / 全面研究 / 系统研究 / 调研 / 调查 / 尽调 / 行业研究 / 市场研究 / 竞品分析 / 政策研究 / 技术研究 / 趋势研究 / 事实核查 / 写一份研究报告 / 调研报告 / 深度报告 / research / deep research；②请求需要跨多来源取证、多维度对比、交叉验证才能给出可靠结论；③用户要求产出报告、白皮书、行业分析或尽调文档；④话题涉及最新政策/市场/产品/价格/法规，需要系统核查。无核验要求的简单常识问答不使用。模糊或宽泛的"研究/了解一下 X"也优先触发。仅不用于：一句话摘要、已给定单一来源的整理、纯文字润色改写。
---

# DeepResearch

作为 DeepResearch CLI 的用户入口，负责环境预检、安装引导、参数确认、任务启动、进度告知和结果交付。
默认项目为 `https://github.com/David-art-beep/Deepresearch-cli`，正式安装包以该仓库的
[GitHub Releases](https://github.com/David-art-beep/Deepresearch-cli/releases) 为准。

## 预检与诊断

首次使用或出现故障时，按当前问题选择最少的只读检查，不要每次全部执行：

```bash
deepresearch --help
deepresearch doctor --harness <harness> --json
deepresearch sources list --json
deepresearch domains list --json
deepresearch browser status --json
deepresearch status <run-id> --json
deepresearch resume --help
deepresearch web --help
```

检查时确认 Node.js >= 22、Python >= 3.10、npm、`deepresearch` 和用户选择的 Harness 是否可用。
参数不确定时先查看对应的 `--help`，不要凭记忆猜测。

- CLI 或 Harness 缺失：先报告缺失项，不直接改用其他 Harness。
- Search 异常：只报告来源可用性和缺失的变量名。
- Camofox 不可用：仍可切换来源继续研究。
- Run 失败：保留运行记录，只在确认原进程已结束后恢复。

不得显示环境变量值、token、Cookie、npm 凭据或 Harness Profile 中的秘密。

## 安装或升级 CLI

安装会访问网络并修改用户级 npm 目录，执行前先取得当前环境要求的授权。

从 GitHub 最新 Release 中选择名称匹配
`david-art-beep-deepresearch-cli-*.tgz` 的资源，并使用其 `browser_download_url` 安装：

```bash
npm install -g <github-release-tgz-url>
deepresearch --help
```

不要默认改用 npm registry，除非包已公开发布且用户明确选择该渠道。
不要要求用户安装 uv，也不要向系统 Python 全局安装依赖。
如果仓库尚无可用 Release，如实说明；可以使用用户提供的本地 `.tgz`，但不得静默改用其他来源。

安装后初始化用户级 Search 配置：

```bash
deepresearch sources init
deepresearch sources list --json
```

配置文件位于 `~/.deepresearch-cli/search/.env`。公开来源无需 API key；需要扩展来源时，只告知应填写的变量名，
不索取或回显凭据。

## 准备 Harness

- Hermes：复用现有 Hermes 登录和模型配置。
- Codex：确认 `codex` 存在且已执行 `codex login`。
- Claude Code：CLI 内含适配层，但不包含外部 `claude-agent-acp`。缺失时，在授权后执行
  `npm install -g @agentclientprotocol/claude-agent-acp`，再由用户完成
  `claude-agent-acp --cli auth login`。
- OpenClaw：确认 `openclaw` 存在且 Gateway 正常。模型由 OpenClaw 配置选择，不传
  `--harness-model`。

如果 `doctor` 仅因模型、登录或 Provider 凭据未配置而失败，说明缺失配置，不替用户改写 Harness 全局配置。

## 准备 Camofox

Camofox 是普通网页抓取失败后的可选回退，基础 CLI 不包含浏览器文件。
用户希望启用时，先说明需额外下载数百 MB 资源，再在授权后执行：

```bash
deepresearch browser setup
deepresearch browser start
deepresearch browser status --json
```

用户选择启用时确认健康状态。Camofox 只访问公开网页，不用于绕过 CAPTCHA、登录、付费墙或访问控制。
未安装或不可用时不阻塞研究，CLI 会切换其他来源。只有用户明确要求时才传入 `--no-camofox-fallback`。

## 确认研究参数

开始前确认研究问题以及三个独立参数：

- 研究深度：`quick`、`normal` 或 `heavy`
- 报告形式：`brief` 或 `formal_report`
- 交付格式：`markdown`、`html`、`pdf` 或 `docx`

用户已给出的参数不要重复询问，只补齐缺失项。选择 DOCX 时提醒需要 Pandoc；选择 PDF 时提醒需要 Typst。
三项未确认完成前，不得启动可能长时间运行或产生费用的研究。

## 启动研究

Quick 使用前台 CLI：

```bash
deepresearch "<query>" \
  --mode quick \
  --report-format <brief|formal_report> \
  --output-format <markdown|html|pdf|docx> \
  --harness <hermes|codex|claude-code|openclaw> \
  --language zh-CN \
  --progress tools
```

Normal 和 Heavy 使用 Web 入口。在可持续读取输出、且启动后能将控制权返回给 Agent 的后台或持久终端会话中运行：

```bash
deepresearch web "<query>" \
  --mode <normal|heavy> \
  --report-format <brief|formal_report> \
  --output-format <markdown|html|pdf|docx> \
  --harness <hermes|codex|claude-code|openclaw> \
  --language zh-CN \
  --host 127.0.0.1 \
  --port 8765 \
  --progress tools
```

保持该进程运行，不要再启动第二份相同研究。等待 CLI 确认 Web 已开始监听后，立即告诉用户：

```text
研究已经启动，可打开 http://127.0.0.1:8765 查看实时进度。
```

不要等待整个研究完成后才回复用户。如果 Web 启动失败，报告启动错误，不要提供尚不可用的地址。

展示链接不等于强制打开浏览器；需要 GUI 操作时遵循当前环境授权。只有用户明确要求局域网访问时才使用
`--host 0.0.0.0`，并提醒运行轨迹和报告会对同网段可见。

## 完成、失败与恢复

- 成功：报告 `run_id`、运行状态和 `output/<run-id>/` 中的最终文件。
- 失败或中断：如实说明失败节点，并保留 `runs/<run-id>/`。
- 恢复：确认原进程已结束后，执行 `deepresearch resume <run-id> --harness <harness>`。

不把搜索命中或中间文件当作最终报告，不伪造完成状态，不在 CLI 安装目录保存用户运行记录。
