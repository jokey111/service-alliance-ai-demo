# 12345 客服联盟 · FDE 求职 Demo

基于**合成业务数据**的企业智能客服原型。演示员工自助查询、IT 报修、人工坐席、工单流转、质检复核及可追溯的 Skill/MCP 调用。

> 这是求职作品，不是腾讯产品或真实企业系统。演示身份可由访客自由切换，所有账号和单据均为虚构。

## 当前可运行能力

| 模块 | 行为 | 证据 |
| --- | --- | --- |
| 智能服务 | 报销进度多单据选择、详情查询；报销流程演示回答；人工转接 | 会话、单据归属校验、运行轨迹 |
| 知识检索 | 九类合成知识按关键词召回，过滤未发布/过期版本；配置模型后可基于检索原文生成带引用的答复 | 文档 ID、版本、生效状态、可展开原文 |
| Agent 路由 | 配置标准智谱 API Key 后，GLM 选择允许的意图；无 Key 时使用规则回退 | `route.source` 与模型名称写入轨迹 |
| 报销 Skill | 独立 SOP 执行代码，通过 MCP `tools/list` 和 `tools/call` 访问业务服务 | `reimbursement-status` v1.0.0 |
| IT 报修 Skill | 填写、预览、明确确认、MCP 创建工单、相同确认令牌幂等重试 | `it-repair-request` v1.0.0 |
| 坐席与工单 | 转人工保留会话摘要；坐席按状态机受理、解决、关闭 | 持久化工单 |
| 质检 | 关闭工单后生成规则草稿；质检员确认或要求补证 | 规则版本、证据、复核结果 |
| 质检分析 Agent | 只读制定查询计划，通过 MCP 汇总指标并抽样工单证据；模型配置后可提出待验证排查方向 | 统计口径、样本 ID、限制说明和轨迹 |
| 固定回归评测 | 十条案例检查意图、否定词、过期知识和数据边界 | 管理页结果与评测轨迹 |

**尚未实现：**向量检索与混合重排、历史趋势归因、实时流式输出、真实企业系统接入和模型回答质量的人工标注评测。当前知识检索是透明的关键词召回；配置标准模型 API Key 后才执行基于检索原文的模型生成。质检分析只针对少量合成工单做统计与抽样，不能证明不合格率变化。知识文案不能作为实际制度使用。

## 架构

```text
浏览器 ── Caddy ── React/Vite
              └── /api ── FastAPI ── PostgreSQL（本地可用 SQLite）
                            ├── 智谱标准模型 API（配置后）
                            └── 可执行 Skill ── MCP client ── 私网 MCP server ── 合成业务数据
```

MCP 是独立进程。它不暴露公网端口。业务数据由服务端登录身份限定；模型只能提议意图，不能指定任意员工或改写工具返回的状态。
模型调用默认限制为每分钟 12 次（单 API 进程）；超过限额时路由和知识回答回退到确定性路径。公网部署还应通过云平台设置费用告警。

## 本地运行（Windows PowerShell）

需要 Python 3.12+、Node.js 22+。在仓库根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt
Copy-Item apps\api\.env.example apps\api\.env
cd apps\web
npm ci
cd ..\..
```

分别打开三个终端，在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m apps.business_mcp.server
cd apps\web; npm run dev
```

访问 `http://localhost:5173`。不填模型 Key 时，页面会明确显示“模型待配置”，仍可验证 Skill/MCP/业务闭环。填入**标准模型 API Key** 并重启 API 后，意图路由会调用 GLM。`glm-5.3-flash` 是默认模型，可在 `.env` 中调整。

运行端到端冒烟测试（API 与 MCP 启动后）：

```powershell
.\.venv\Scripts\python.exe tests\smoke.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_*.py
cd apps\web; npm run build
```

## 公网部署

准备一台安装 Docker Compose 的 Linux 主机、解析到该主机的域名，以及**智谱标准模型 API Key**：

1. 将代码复制到主机，执行 `cp .env.example .env`，设置 `SITE_ADDRESS=你的域名`、强随机字母数字 `POSTGRES_PASSWORD`、`ZHIPU_API_KEY`。
2. 在防火墙放行 80/443；数据库、API、MCP 无主机端口映射。
3. 执行 `docker compose up -d --build`。Caddy 根据域名申请并续期 HTTPS 证书。
4. 检查 `https://你的域名/api/health` 的 `model_configured` 为 `true`，再按下方演示脚本走一遍全链路。

当前开发机没有 Docker，Compose 启动尚未实测。公网发布前还应在目标主机验证模型出站连接、域名证书、容器重启与备份。
推送到 GitHub 后，`.github/workflows/ci.yml` 会在每次 push 和 PR 中构建前端、检查 Compose 配置、验证模型路由边界并运行端到端冒烟测试。

## 面试演示脚本（约 5 分钟）

1. 以员工身份问“我的报销怎么还没到？”；在两张本人单据中选一张，打开轨迹看 `Skill → MCP tools/list → tools/call`。
2. 问“查同事报销进度”，展示后端拒绝。
3. 进入 IT 报修，填写故障并预览，点击确认后获得工单号；同一令牌再次提交仍返回原工单。
4. 在对话中转人工；切换坐席，查看带会话摘要的工单，受理、填写处理结果并关闭。
5. 切换质检员，查看事实/流程/态度三维草稿并提交复核意见。说明哪些判断必须人工确认。
6. 在“异常分析 Agent”中生成只读草稿，查看 MCP 统计与抽样轨迹，以及“无法判断趋势”的限制说明。
7. 以管理员身份打开“知识与评测”，对比当前有效与过期文档，运行十条固定案例并检查评测轨迹。

## 技术与产品说明

- [完整设计方案](12345客服联盟_FDE求职Demo重设计方案.md) 记录目标架构和后续路线；其中一些目标能力尚未落地，以本 README 的“当前可运行能力”为准。
- 智谱官方对 Coding Plan Key 的使用范围有限制，且与标准模型 API Key 分开管理。公网服务应使用标准 API Key，并只放在服务器环境变量中，不提交到 GitHub：[Coding Plan 使用说明](https://docs.bigmodel.cn/cn/coding-plan/usage-notes)、[API Key 管理说明](https://docs.bigmodel.cn/cn/coding-plan/notice/api-key-management)。
- 本仓库根目录原先还有 PRD、课件、原静态 Demo 等工作资料；`.gitignore` 排除这些材料。公开前请再次核对 `git status`，只提交本项目代码、合成数据说明与设计文档。
