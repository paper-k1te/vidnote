# 选题调研：agent 工具赛道现状（2026-11-03）

目的：为「两个月内做出一个有真实使用者的开源项目，2027 年初申请 Codex for Open Source」选方向。

## 结论先行

**不存在空地。** 三个候选方向都已有领跑者或大量尝试，且都呈现同一个分布：头部 1~2 个，尾部几十个 0~5★ 的重复尝试。这说明：
- 需求是真的（否则不会有几十个人做同一件事）；
- 但**「做一个更好的 X」不是有效策略**，因为需求强度不足以支撑第 3、4 个玩家。

真正决定成败的是**分发**，不是点子。

## 赛道 A：Agent 配置/skill 迁移

| 项目 | ★ | 说明 |
|---|---|---|
| xhluca/session-migrate | 169 | 跨 18 个 harness 迁移会话 |
| iannuttall/source-agents | 123 | AGENTS.md ↔ CLAUDE.md 同步 |
| PanisHandsome/ai-rules-sync | 101 | 规则文件双向转换 |
| zuharz/ccode-to-codex | 76 | Claude skills/agents → Codex |
| m3252/swik | — | 配置迁移，可逆 + 备份 |

**致命因素**：OpenAI 官方在 `openai/skills` 内置 `migrate-to-codex`（含 `--plan` / `--doctor` / `--validate-target`，覆盖 CLAUDE.md、commands、skills、.mcp.json、subagents、hooks）；Anthropic 已在向 AGENTS.md 收敛。
→ **判定：赛道正在被厂商吸收，放弃。**

## 赛道 B：Agent 录制回放 / 确定性测试

| 项目 | ★ | 说明 |
|---|---|---|
| jwuthri-cloud/Tracely-ai | 1213 | trace-native CI/CD，含 replay，偏平台 |
| ATaC-team/ATaC | 299 | 录制回放 agent 轨迹，偏学术 |
| theagentplane/chronicle | 26 | 决策图录制回放 |
| llmtape / llm-cassette / agent-cassette 等 | 0~5 | 一打以上同类尝试，全部极小 |

**判定**：HTTP 层录制回放已被 vcrpy 类方案覆盖，增量价值薄；上层"轨迹契约"有 Tracely 占位。→ 除非有独特分发，否则不做。

## 赛道 C：Skill 质检 / MCP 一致性

| 项目 | ★ | 说明 |
|---|---|---|
| agent-sh/agnix | 467 | 全品类 linter + LSP（CLAUDE.md/AGENTS.md/SKILL.md/hooks/MCP），带 autofix |
| skillmds/skillmd | 192 | SKILL.md lint + search + install |
| mcp-assert | 小 | MCP 服务端 18 类断言，单 Go 二进制 |
| MCP 官方 conformance suite | — | 协议级一致性测试已存在 |

**判定**：linter 位置已被 agnix 占住；MCP 协议级一致性有官方套件。→ 只能做垂直切口，不做通用 linter。

## 选品标准（按重要性排序）

1. **分发**：你有没有一个别人没有的渠道，能在发布 48 小时内触达 1000 个目标用户？
2. **真实痛点**：目标用户是否已经在用丑陋的 workaround（脚本、手工、付费替代）？
3. **依赖形态**：能否成为别人 CI/依赖树里的一环（"被依赖"比 star 更能支撑申请材料）？
4. **维护成本**：是否会随外部服务改版而持续崩坏（如爬虫类）？
5. **可持续性**：你愿意做 2 年吗？申请只是副产品。

## 8 周节奏（模板）

| 周 | 目标 | 交付 |
|---|---|---|
| 1 | 选题验证 | 5 次用户访谈 + 一页 README 草稿，不写代码 |
| 2–3 | MVP | 能跑通的最小版本 + 30 秒 demo |
| 4 | 发布 | 一次集中 launch，进 2–3 个目标社区 |
| 5–6 | 迭代 | 按真实反馈修，收集使用证据（安装量、下游依赖、外部 issue） |
| 7 | 固化 | 文档、CI、发版流程、good first issue |
| 8 | 复盘 | 决定继续还是换向；整理申请材料 |

## 待定

- 用户的分发渠道（决定一切）
- 目标垂直领域
