"""Model proposals are constrained to allowed routes; record selection stays server-side."""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from apps.api.main import choose_route


class ModelRouteContractTest(unittest.TestCase):
    def test_valid_model_proposal(self) -> None:
        with patch("apps.api.main.configured", return_value=True), patch(
            "apps.api.main.completion", new=AsyncMock(return_value='{"route":"knowledge"}')
        ):
            selected, source = asyncio.run(choose_route("年假怎么申请", None))
        self.assertEqual((selected, source), ("knowledge", "zhipu-intent-router"))

    def test_invalid_model_proposal_falls_back(self) -> None:
        with patch("apps.api.main.configured", return_value=True), patch(
            "apps.api.main.completion", new=AsyncMock(return_value='{"route":"delete-all"}')
        ):
            selected, source = asyncio.run(choose_route("请假流程", None))
        self.assertEqual((selected, source), ("knowledge", "deterministic-fallback"))

    def test_selected_record_bypasses_model(self) -> None:
        with patch("apps.api.main.configured", return_value=True), patch(
            "apps.api.main.completion", new=AsyncMock()
        ) as model:
            selected, source = asyncio.run(choose_route("查询详情", "BX-2026-1023"))
        self.assertEqual((selected, source), ("reimbursement-status", "selected-record"))
        model.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
