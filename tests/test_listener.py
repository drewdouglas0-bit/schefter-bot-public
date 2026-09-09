import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from schefter import listener


def event(text="Schefter, latest moves?", *, guid="message-1", chat="chat-1", mine=False):
    return {
        "type": "new-message",
        "data": {
            "guid": guid,
            "text": text,
            "isFromMe": mine,
            "handle": {"address": "+15551234567"},
            "chats": [{"guid": chat}],
        },
    }


class ListenerTests(unittest.TestCase):
    def test_parse_new_message(self):
        message = listener.parse_event(event())
        self.assertEqual(message.message_id, "message-1")
        self.assertEqual(message.chat_id, "chat-1")
        self.assertEqual(message.sender, "+15551234567")

    def test_ignores_own_message(self):
        self.assertIsNone(listener.parse_event(event(mine=True)))

    def test_trigger_matches_anywhere_and_is_case_insensitive(self):
        with patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            # Leading, the original form.
            self.assertEqual(listener.invoked_question("@SCHEFTER: who won?"), "who won?")
            self.assertEqual(listener.invoked_question("Schefter - latest moves"), "latest moves")
            # Mid-message: people address it this way just as often.
            self.assertEqual(
                listener.invoked_question("Hey schefter who is projected to win?"),
                "who is projected to win?",
            )
            # Trailing: the question is what came before the name.
            self.assertEqual(
                listener.invoked_question("what do you think schefter"), "what do you think"
            )
            self.assertEqual(
                listener.invoked_question("so what about that trade schefter?"),
                "so what about that trade",
            )
            # A bare mention is still addressed; agent.answer turns it into help.
            self.assertEqual(listener.invoked_question("schefter"), "")

    def test_trigger_requires_a_whole_word(self):
        with patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            self.assertIsNone(listener.invoked_question("no mention here"))
            self.assertIsNone(listener.invoked_question("schefterbot is broken"))
            self.assertIsNone(listener.invoked_question("ask the schefters about it"))

    def test_naming_the_bot_is_not_addressing_it(self):
        """Synthetic examples of discussing the bot without addressing it."""
        with patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            for text in (
                "Has everybody saved schefter as a contact",
                "If schefter's messages do not load try reconnecting",
                "Can everybody add the schefter bot as a contact",
                "according to schefter",
                "Schefter's messages should arrive shortly",
                "we think schefter is offline",
                "has schefter replied yet",
            ):
                self.assertIsNone(listener.invoked_question(text), text)

    def test_a_request_attached_to_the_name_still_counts(self):
        with patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            for text in (
                "Hey schefter who is projected to win?",
                "yo schefter what are the standings",
                "schefter make a poll for ppr or half ppr",
                "what do you think schefter",
                "so what about that trade schefter?",
            ):
                self.assertIsNotNone(listener.invoked_question(text), text)

    @patch.object(listener.imessage, "send")
    @patch.object(listener.agent_state, "append_exchange")
    @patch.object(listener.agent_state, "history", return_value=[])
    @patch.object(listener.agent_state, "claim", return_value=True)
    @patch.object(listener.agent, "answer", return_value="League answer")
    def test_process_sends_gated_reply(self, answer, claim, history, append, send):
        with patch.object(listener.config, "CHAT_ID", "chat-1"), \
             patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            self.assertEqual(listener.process(event()), "replied")
        answer.assert_called_once_with("latest moves?", [], actor="+15551234567")
        send.assert_called_once_with("League answer", "chat-1")
        append.assert_called_once()

    @patch.object(listener.imessage, "send")
    @patch.object(listener.agent_state, "claim", return_value=True)
    @patch.object(listener.trades, "bare_response", return_value="Trade ab12cd34 accepted.")
    def test_process_allows_unambiguous_bare_trade_response(self, bare, claim, send):
        with patch.object(listener.config, "CHAT_ID", "chat-1"), \
             patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            self.assertEqual(listener.process(event("Yes")), "replied-trade")
        bare.assert_called_once_with("+15551234567", "Yes")
        send.assert_called_once_with("Trade ab12cd34 accepted.", "chat-1")

    @patch.object(listener.imessage, "send")
    @patch.object(listener.agent_state, "claim", return_value=True)
    @patch.object(listener.polls, "record_vote")
    @patch.object(listener.polls, "parse_vote", return_value=1)
    def test_bare_vote_is_recorded_silently(self, parse, record, claim, send):
        with patch.object(listener.config, "CHAT_ID", "chat-1"), \
             patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            self.assertEqual(listener.process(event("2")), "recorded-vote")
        record.assert_called_once_with("+15551234567", 1)
        send.assert_not_called()  # 14 voters must not produce 14 confirmations

    @patch.object(listener.imessage, "send")
    @patch.object(listener.agent_state, "claim", return_value=True)
    @patch.object(listener.trades, "bare_response", return_value="Trade ab12cd34 accepted.")
    @patch.object(listener.polls, "parse_vote", return_value=None)
    def test_non_vote_still_reaches_the_trade_handler(self, parse, bare, claim, send):
        with patch.object(listener.config, "CHAT_ID", "chat-1"), \
             patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            self.assertEqual(listener.process(event("Yes")), "replied-trade")
        bare.assert_called_once_with("+15551234567", "Yes")

    @patch.object(listener.agent_state, "claim")
    def test_process_ignores_other_chat(self, claim):
        with patch.object(listener.config, "CHAT_ID", "different"), \
             patch.object(listener.config, "AGENT_TRIGGER", "schefter"):
            self.assertEqual(listener.process(event()), "ignored-chat")
        claim.assert_not_called()

    def test_http_webhook_requires_secret_and_enqueues(self):
        class FakeWorker:
            def __init__(self):
                self.payloads = []

            def submit(self, payload):
                self.payloads.append(payload)
                return True

        worker = FakeWorker()
        server = ThreadingHTTPServer(("127.0.0.1", 0), listener.handler(worker))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_address[1]
        body = json.dumps(event()).encode()
        try:
            with patch.object(listener.config, "AGENT_WEBHOOK_SECRET", "test-secret"):
                bad = urllib.request.Request(
                    f"http://127.0.0.1:{port}/webhook?token=wrong",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(bad)
                self.assertEqual(error.exception.code, 401)

                good = urllib.request.Request(
                    f"http://127.0.0.1:{port}/webhook?token=test-secret",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(good) as response:
                    self.assertEqual(response.status, 202)
            self.assertEqual(worker.payloads, [event()])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
