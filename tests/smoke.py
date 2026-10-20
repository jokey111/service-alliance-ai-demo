"""Run against local API and MCP services: python tests/smoke.py."""
from __future__ import annotations

import httpx


def main() -> None:
    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=25)

    def login(identity: str) -> dict:
        response = client.post("/api/auth/demo", json={"identity": identity})
        response.raise_for_status()
        return {"Authorization": "Bearer " + response.json()["token"]}

    employee = login("user")
    agent = login("agent")
    qc = login("qc")

    first = client.post("/api/chat", headers=employee, json={"text": "我的报销进度到哪了"})
    assert first.status_code == 200, first.text
    first = first.json()
    assert first["status"] == "selection_required", first
    assert len(first["evidence"]["items"]) == 2
    selected_id = first["evidence"]["items"][0]["id"]
    detail = client.post("/api/chat", headers=employee, json={"text": "查这张单据", "conversation_id": first["conversation_id"], "reimbursement_id": selected_id}).json()
    assert detail["status"] == "ok", detail
    assert detail["evidence"]["item"]["id"] == selected_id
    assert any(step["kind"] == "mcp_call" for step in client.get("/api/traces/" + detail["trace_id"], headers=employee).json()["steps"])

    denied = client.post("/api/chat", headers=employee, json={"text": "查同事报销进度"})
    assert denied.status_code == 403, denied.text
    other = client.get("/api/conversations/" + first["conversation_id"], headers=agent)
    assert other.status_code == 404, other.text

    prepare = client.post("/api/it-repair/prepare", headers=employee, json={
        "device": "测试笔记本", "issue": "无法连接测试 Wi-Fi", "location": "测试办公区",
    })
    assert prepare.status_code == 200, prepare.text
    token = prepare.json()["confirmation_token"]
    blocked = client.post("/api/it-repair/confirm", headers=agent, json={"confirmation_token": token})
    assert blocked.status_code == 403, blocked.text
    created = client.post("/api/it-repair/confirm", headers=employee, json={"confirmation_token": token}).json()
    assert created["status"] == "ok" and not created["duplicate"], created
    repeated = client.post("/api/it-repair/confirm", headers=employee, json={"confirmation_token": token}).json()
    assert repeated["ticket_id"] == created["ticket_id"] and repeated["duplicate"], repeated

    handoff = client.post("/api/handoffs", headers=employee, json={"conversation_id": first["conversation_id"]})
    assert handoff.status_code == 200, handoff.text
    ticket_id = handoff.json()["id"]
    for status, resolution in (("processing", None), ("resolved", "已联系员工，核实并说明财务复核节点。"), ("closed", None)):
        response = client.patch("/api/tickets/" + ticket_id, headers=agent, json={"status": status, "resolution": resolution})
        assert response.status_code == 200, response.text
    reports = client.get("/api/qc-reports", headers=qc).json()
    report = next(item for item in reports if item["ticket_id"] == ticket_id)
    reviewed = client.post("/api/qc-reports/" + report["id"] + "/review", headers=qc,
                           json={"decision": "needs_evidence", "note": "请补充业务回执证据"})
    assert reviewed.status_code == 200, reviewed.text
    analysis = client.post("/api/qc-analysis", headers=qc, json={"category": "报销服务"})
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["metrics"]["ticket_count"] >= 1
    assert "不能推断" in analysis.json()["limitation"]
    print("PASS: reimbursement MCP, ownership, IT repair idempotency, handoff, ticket, QC, QC analysis")


if __name__ == "__main__":
    main()
