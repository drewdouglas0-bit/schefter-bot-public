import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from schefter import agent_state


class AgentStateTests(unittest.TestCase):
    def test_claim_deduplicates_and_history_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(agent_state.config, "AGENT_STATE_FILE", Path(directory) / "state.json"), \
             patch.object(agent_state.config, "AGENT_HISTORY_SIZE", 2):
            self.assertTrue(agent_state.claim("one"))
            self.assertFalse(agent_state.claim("one"))
            for index in range(4):
                agent_state.append_exchange("chat", "member", f"q{index}", f"a{index}")
            messages = agent_state.history("chat")
            self.assertEqual(len(messages), 4)
            self.assertEqual(messages[0]["content"], "member: q2")


if __name__ == "__main__":
    unittest.main()
