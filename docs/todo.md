# DeepResearch CLI 后续 TODO

更新日期：2026-08-13

## 已完成

- [x] 用单一配置运行时替换旧 Graph/Policy/Input Selector。
- [x] Quick、Normal、Heavy 改为简单 YAML Step 列表。
- [x] Agent/Script Node YAML 与统一 Context。
- [x] `one/all/each` 输入和 `state/batch` 输出合同。
- [x] Heavy 通过重复 YAML 节点实现可选第二轮 Research/Review/Perspective。
- [x] `--output-format html` 自动追加内置 md-html Agent 节点。
- [x] 最终结果导出到 `output/<run-id>/`。
- [x] schema 2 Manifest、Node/Workflow 快照、旧 Run 拒绝。
- [x] Hermes per-attempt 进程与 Research Search MCP。
- [x] Search provider 独立目录、逐源 YAML 自动注册与目录级 `.env`。
- [x] Run 级 Search Coordinator、SQLite WAL、attempt namespace 与 resume 复用。
- [x] Web Domain/Source 搜索进度、调用耗时、缓存统计与证据转化漏斗。

## P0

- [ ] 用真实 Hermes 分别验收 Quick Markdown、Heavy Markdown 和 Heavy HTML。
- [ ] 检查真实 Agent 是否稳定遵守统一 Context 中的输入输出路径。
- [ ] 为 Review/FinalReview 增加结构化质量结果，区分 completed 与 quality passed。
- [ ] 验证内置 md-html 节点的真实页面质量和大报告上下文上限。

## P1

- [ ] failed Run 的显式 retry/fork。
- [ ] `runs list/cancel/export/clean`。
- [ ] 节点与工具耗时、等待时间、错误分类和用量指标。
- [ ] Agent-facing CLI 使用说明，只描述 CLI/Workflow/Node YAML 用法，不复制流程实现。
- [x] Script-only 单节点命令不启动 Hermes。
- [ ] 支持 Node 配置及其代码资产的版本化分发与来源签名。

## P2

- [ ] 第二个真实 Harness Adapter。
- [ ] Search provider 上游分页、跨 Run 缓存、TTL 和配额治理。
- [ ] CI、版本 tag、changelog 和 `--version`。
- [ ] Run 归档与显式离线迁移工具；运行时本身仍不增加旧合同兼容分支。

详细边界见 [`design.md`](design.md)，交接入口见 [`handoff.md`](handoff.md)。
