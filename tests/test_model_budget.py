"""The public demo must stop model requests after its daily budget is reached."""
from __future__ import annotations

import asyncio
import unittest
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

from apps.api import glm


class ModelBudgetTest(unittest.TestCase):
    def test_selected_model_reaches_upstream_request(self) -> None:
        response = MagicMock()
        response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
        with (
            patch.object(glm, "API_KEY", "test-only-key"),
            patch.object(glm, "CALL_TIMES", deque()),
            patch.object(glm, "DAY_CALL_TIMES", deque()),
            patch.object(glm.httpx, "AsyncClient") as client,
        ):
            post = AsyncMock(return_value=response)
            client.return_value.__aenter__.return_value.post = post
            result = asyncio.run(glm.completion([{"role": "user", "content": "test"}], model="glm-5.3"))
            self.assertEqual(post.await_args.kwargs["json"]["model"], "glm-5.3")
        self.assertEqual(result, "OK")

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
