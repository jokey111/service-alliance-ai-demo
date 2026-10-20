# 报销进度查询 Skill

版本：1.0.0。适用对象：已登录员工查询本人报销单。输入为服务端注入的 `actor_id`，可选 `reimbursement_id`。

执行器先通过 MCP `list_my_reimbursements` 查询授权列表。多条记录时返回选择卡，不擅自决定单据；员工选定后通过 `get_reimbursement_detail` 再查详情。两次工具调用都校验归属。没有记录、权限拒绝、工具失败各返回独立状态。回复只能使用工具返回的状态、节点和下一步。
