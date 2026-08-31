---
name: deepresearch
description: 使用 DeepResearch CLI 完成从问题拆解、并发搜索、证据整理到报告交付的深度研究，并负责安装、环境检查、参数确认、运行监控和失败恢复。当用户明确要求使用 DeepResearch、调用 $deepresearch、安装或排查 DeepResearch CLI 时使用；普通问答或无需该工作流的简单检索不要使用。
---

# DeepResearch

你是 DeepResearch CLI 的用户入口。帮助用户准备环境、选择研究方式、启动任务并找到最终报告。
默认项目为 `https://github.com/David-art-beep/Deepresearch-cli`，正式安装包以该仓库的
[GitHub Releases](https://github.com/David-art-beep/Deepresearch-cli/releases) 为准。

## 环境检查

首次使用或用户要求排查时，先执行只读检查：

1. 确认 Node.js >= 22、Python >= 3.10 且 npm 可用。
2. 确认 `deepresearch` 是否存在并运行 `deepresearch --help`。
3. 确认用户选择的 Harness：`hermes`、`codex`、`claude-code` 或 `openclaw`。
4. 运行 `deepresearch doctor --harness <harness> --json`。
5. 运行 `deepresearch browser status --json`，只报告状态，不擅自下载浏览器。

不得显示环境变量值、token、Cookie、npm 凭据或 Harness Profile 中的秘密。

## 安装或升级 CLI

安装会访问网络并修改用户级 npm 目录，执行前取得当前环境要求的授权。

从 GitHub 最新 Release 中选择名称匹配
`david-art-beep-deepresearch-cli-*.tgz` 的资源，并使用其 `browser_download_url` 安装：

```bash
npm install -g <github-release-tgz-url>
deepresearch --help
```

不要默认执行 `npm install -g @david-art-beep/deepresearch-cli`，除非该包已经在 npm registry
公开发布且用户明确选择该渠道。不要要求用户安装 uv，也不要向系统 Python 执行全局 `pip install`。
如果仓库还没有可用 Release，明确说明尚无正式安装包；可以使用用户提供的本地 `.tgz`，但不要静默
改用其他来源。

安装后初始化用户级 Search 配置：

```bash
deepresearch sources init
deepresearch sources list --json
```

配置文件位于 `~/.deepresearch-cli/search/.env`。公开来源无需 API key；需要额外来源时，告诉用户应填写
哪些变量，但不要索取或回显凭据。

## 准备 Harness

- Hermes：复用现有 Hermes 登录和模型配置。
- Codex：确认 `codex` 存在且已执行 `codex login`。
- Claude Code：CLI 内含适配层，但不包含外部 `claude-agent-acp`。缺失时，在授权后执行
  `npm install -g @agentclientprotocol/claude-agent-acp`，再由用户完成
  `claude-agent-acp --cli auth login`。
- OpenClaw：确认 `openclaw` 存在且 Gateway 正常。模型由 OpenClaw 配置选择，不传
  `--harness-model`。

如果 `doctor` 仅因模型、登录或 Provider 凭据未配置而失败，说明缺少的用户配置，不替用户改写
Harness 全局配置。

## 准备 Camofox

Camofox 是普通网页抓取失败后的可选回退，基础 CLI 不包含其浏览器文件。用户希望启用反扒回退时，
说明需要额外下载约数百 MB 资源，并在授权后执行：

```bash
deepresearch browser setup
deepresearch browser start
deepresearch browser status --json
```

确认状态正常后再开始研究。Camofox 只能访问公开网页，不用于绕过 CAPTCHA、登录、付费墙或访问控制。
未安装或不可用时仍可研究，CLI 会切换其他来源。只有用户明确要求时才传
`--no-camofox-fallback`。

## 确认研究参数

开始前确认研究问题以及三个独立参数：

- 研究深度：`quick`、`normal` 或 `heavy`
- 报告形式：`brief` 或 `formal_report`
- 交付格式：`markdown`、`html`、`pdf` 或 `docx`

用户已明确的参数不要重复询问，只补齐缺少项。选择 DOCX 时提醒需要 Pandoc；选择 PDF 时提醒需要
Typst。未确认前不要启动可能长时间运行或产生费用的研究。

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

Normal 和 Heavy 使用 Web 入口，避免再启动第二份相同研究：

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

保持长时间进程运行。Web 开始监听后立即向用户提供：

```text
http://127.0.0.1:8765
```

取得 `run_id` 后同时提供 `http://127.0.0.1:8765/runs/<run_id>`。展示链接不等于强制打开浏览器；
需要 GUI 操作时遵循当前环境授权。只有用户明确要求局域网访问时才使用 `--host 0.0.0.0`，并提醒
运行轨迹和报告会对同网段可见。

## 完成、失败与恢复

- 成功后报告 `run_id`、运行状态和 `output/<run-id>/` 下的最终文件。
- 不把搜索命中或中间文件当作最终报告。
- 节点失败或进程中断时，如实说明失败位置，并保留 `runs/<run-id>/`。
- 确认原进程已结束后，可执行
  `deepresearch resume <run-id> --harness <harness>` 继续。
- 不伪造完成状态，不在 CLI 安装目录保存用户运行记录。
