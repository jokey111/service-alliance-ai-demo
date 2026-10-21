"""The public demo must stop model requests after its daily budget is reached."""
from __future__ import annotations

import asyncio
import unittest
from collections import deque
from unittest.mock import patch

from apps.api import glm


class ModelBudgetTest(unittest.TestCase):
    def test_daily_limit_blocks_upstream_request(self) -> None:
        with (
            patch.object(glm, "API_KEY", "test-only-key"),
            patch.object(glm, "MAX_CALLS_PER_DAY", 1),
            patch.object(glm, "CALL_TIMES", deque()),
            patch.object(glm, "DAY_CALL_TIMES", deque([99.0])),
            patch.object(glm.time, "monotonic", return_value=100.0),
            patch.object(glm.httpx, "AsyncClient") as client,
        ):
            result = asyncio.run(glm.completion([{"role": "user", "content": "test"}]))
        self.assertIsNone(result)
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
