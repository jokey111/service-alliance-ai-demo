# it-repair-request · v1.0.0

## 输入与前提

登录员工明确填写设备、故障和地点。API 先展示确认卡，并生成绑定当前员工的短期确认令牌；用户确认后才能执行本 Skill。幂等键由 API 生成，不接受模型生成。

## SOP

1. 通过 MCP `tools/list` 验证 `create_it_repair_ticket` 可用。
2. 通过 MCP `tools/call` 提交已确认的字段和幂等键。
3. 仅在工具返回 `status=ok` 和工单号时告知提交成功。
4. 结果不明时保留相同幂等键并允许再次确认；服务端据此返回原工单，不重复创建。

## 失败状态

`invalid_input`、`tool_unavailable`、`forbidden_or_missing` 或工具超时均不得宣称提交成功。
