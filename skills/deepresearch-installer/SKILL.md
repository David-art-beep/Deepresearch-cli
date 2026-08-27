---
name: deepresearch-installer
description: 为 Hermes、Codex 或 Claude Code ACP 安装、升级或修复 DeepResearch CLI 及其由 CLI 管理的 Camofox 浏览器运行时。当用户要求 Agent 在本机准备 DeepResearch CLI、Camofox 或两者时使用；仅运行已有且健康的研究工作流时不要使用。
---

# DeepResearch 安装器

在本机准备可用的 `deepresearch` 命令及其可选的 Camofox 代码级回退能力，并验证用户选择的 Hermes、Codex 或 Claude Code ACP Harness。Python CLI 与平台相关的浏览器运行时应分开安装：先从用户提供的来源安装 CLI，再由 CLI 把 Camofox 安装到自己的私有目录。

## 输入与授权

修改机器前先确定 CLI 来源。可以使用以下任一种来源：

- 包含 `pyproject.toml` 的本地 DeepResearch 源码目录；
- 本地 wheel 或源码分发包；
- 用户明确提供的 Git 地址或包仓库地址。

不得猜测仓库、分支、包索引、凭证或代理。如果没有可用的安装来源，向用户索取。

安装软件包和下载浏览器会修改用户环境并使用网络。可以先进行只读检查，但必须在执行这些修改前取得当前运行环境要求的授权。未经用户另行授权，不得安装或升级系统级 Python、Node.js、Hermes、Codex、Claude Code ACP Adapter、包管理器、Shell 或浏览器应用。

## 安装前检查

安装前检查以下项目，并准确报告失败项：

1. 识别操作系统和 CPU 架构。
2. 确认 Python 不低于 3.10。
3. 优先使用 `uv tool`；否则使用已有的隔离 Python 环境，不得安装到系统 Python。
4. 确定要使用的 Harness。用户明确指定时遵循其选择；否则优先识别当前 Agent 所属运行时。仍无法确定且存在多个候选时，询问用户要验证哪一个。Hermes 检查 `hermes`，Codex 检查 `codex`，Claude Code ACP 检查 `claude-agent-acp`。所选命令不存在时停止。本 Skill 不负责安装这些 Harness 或 Adapter。
5. 用户明确要求同时支持多个 Harness 时，分别确认对应命令存在，并在后续逐一验证。
6. 确认 Node.js 不低于 22，并且 npm 可用。Camofox 安装依赖这两项。
7. 确认目标文件系统至少有 1GiB 可用空间。Camofox 下载资源约 300MB，解压后的内核加 Node 依赖约占 750MB。

诊断过程中不得输出环境变量、令牌、npm 配置、Hermes Profile、Cookie 或其他凭证。

## 安装 CLI

优先使用隔离的工具安装：

```bash
uv tool install /绝对路径/deepresearch_cli-0.1.0-py3-none-any.whl
```

对于可信的本地源码目录，改为传入其绝对路径：

```bash
uv tool install /绝对路径/deepresearch-source
```

只有在用户明确要求升级或修复现有安装时才使用 `--force`；全新安装不加该参数。

如果没有 `uv tool`，创建或复用 DeepResearch 专用虚拟环境，并从同一来源安装。不得静默回退到全局 `pip install`。

安装后，解析并调用实际安装的可执行文件，不要使用源码仓库里的 `uv run`：

```bash
deepresearch --help
deepresearch doctor --harness hermes --json
# 或
deepresearch doctor --harness codex --json
# 或
deepresearch doctor --harness claude-code --json
```

只验证用户选择的 Harness；用户要求同时支持多个时，分别使用对应的 `--harness` 值执行一次。

如果 `doctor` 因所选 Harness 尚未配置模型、Provider 或登录状态而失败，将其记录为警告并继续安装 Camofox。不得改写已有 Harness 的 Profile、登录或 Provider 配置，也不得在聊天中索取密钥。最终明确告知用户：完成对应 Harness 配置前还不能运行研究任务。

## 安装并启动 Camofox

先检查现有私有运行时：

```bash
deepresearch browser status --json
```

默认目录是 `~/.deepresearch-cli/camofox`。除非用户提供其他路径，否则复用该目录。如果 `installed`、`engine_installed` 和 `version_matches` 都是 `true`，不要重复下载；否则执行：

```bash
deepresearch browser setup
```

然后启动并检查仅监听回环地址的服务：

```bash
deepresearch browser start
deepresearch browser status --json
```

只有状态同时满足以下条件，安装才算完成：

- `installed: true`；
- `engine_installed: true`；
- `version_matches: true`；
- `running: true`；
- `health.ok: true`。

不得把托管服务暴露到 `127.0.0.1` 以外，不得修改任何 Harness 的全局 MCP 配置，也不得在安装过程中打开可见浏览器。DeepResearch 只在研究命令使用 `--camofox-fallback` 时，由 Search MCP 的 `fetch_url` 在普通 HTTP 失败后执行代码控制的 Camofox 回退；Agent 不直接获得 Camofox 操作工具。

## 失败处理

- Node.js 低于 22：停止并准确报告检测到的版本。
- Camofox 下载中断：检查 `deepresearch browser status --json`；仅当内核不完整时重试一次 `browser setup`。
- 启动失败：读取状态返回的 `log_path`，只报告最小且相关的错误片段，不得泄露凭证。
- 9377 端口冲突：识别占用进程；未经授权不得终止进程，可以建议改用其他回环地址端口。
- 修复过程中不得删除现有 CLI、Camofox 目录、Profile、Cookie、Run 或输出，除非用户明确授权了准确目标。

结束时报告 CLI 可执行文件路径、已验证的 Harness、Camofox 目录、版本与状态、健康检查结果，以及用户下一步可以运行的命令。不得仅凭安装成功宣称反扒有效，也不得尝试绕过 CAPTCHA、身份验证、付费墙或访问控制。
