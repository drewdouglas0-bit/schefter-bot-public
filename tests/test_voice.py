import unittest
from types import SimpleNamespace
from unittest.mock import patch

from schefter import formatter, imessage, voice


def player(name, position="WR", team="NFL"):
    return SimpleNamespace(name=name, position=position, proTeam=team)


class VoiceTests(unittest.TestCase):
    def test_polish_removes_ai_openers_and_em_dashes(self):
        text = voice.polish("Absolutely! Here's the breakdown: Team One — signed a WR.")
        self.assertEqual(text, "Team One, signed a WR.")
        self.assertNotIn("—", text)

    def test_polish_preserves_normal_hyphens(self):
        self.assertEqual(voice.polish("A one-year deal."), "A one-year deal.")

    def test_polish_translates_markdown_for_plain_text_messages(self):
        text = voice.polish(
            "## Update\nHe has **no legitimate ADP**. "
            "[Justice.gov](https://www.justice.gov/story?utm_source=openai)"
        )
        self.assertEqual(
            text,
            "Update\nHe has NO LEGITIMATE ADP. "
            "Justice.gov (https://www.justice.gov/story?utm_source=openai)",
        )
        self.assertNotIn("**", text)
        self.assertNotIn("](", text)

    def test_markdown_never_survives_into_a_message(self):
        # Every one of these reached the group chat with literal ** in it.
        for raw in (
            "**Josh Allen** is out.",
            "**Josh Allen\nis out**",          # bold across a line break
            "**Josh Allen is out",             # truncated mid-emphasis
            "***Josh Allen*** is out.",
            "__Josh Allen__ is out.",
        ):
            polished = voice.polish(raw)
            self.assertNotIn("**", polished, raw)
            self.assertNotIn("__", polished, raw)
            self.assertIn("JOSH ALLEN", polished.upper())

    def test_single_marker_italics_are_stripped(self):
        self.assertEqual(voice.polish("_Josh Allen_ is out."), "Josh Allen is out.")
        self.assertEqual(voice.polish("*Josh Allen* is out."), "Josh Allen is out.")

    def test_emphasis_does_not_mangle_identifiers(self):
        text = "See agent_state.py and _private_var for details."
        self.assertEqual(voice.polish(text), text)

    def test_bullets_become_plain_dashes(self):
        self.assertEqual(voice.polish("* Josh Allen\n* Puka Nacua"), "- Josh Allen\n- Puka Nacua")

    def test_bold_link_does_not_uppercase_case_sensitive_url(self):
        text = voice.polish("**Read https://example.com/CaseSensitivePath**")
        self.assertEqual(text, "READ https://example.com/CaseSensitivePath")

    def test_message_parts_isolate_and_clean_links_for_rich_previews(self):
        parts = imessage.message_parts(
            "See [Justice.gov](https://www.justice.gov/story?utm_source=openai) "
            "and https://www.fantasypros.com/nfl/adp?utm_medium=chat."
        )
        self.assertEqual(
            parts,
            [
                "See Justice.gov and fantasypros.com.",
                "https://www.justice.gov/story",
                "https://www.fantasypros.com/nfl/adp",
            ],
        )

    def test_link_cleaning_preserves_non_tracking_query_encoding(self):
        parts = imessage.message_parts(
            "https://example.com/story?redirect=%2FNews%2FWeek+1&utm_source=openai"
        )
        self.assertEqual(
            parts[-1], "https://example.com/story?redirect=%2FNews%2FWeek+1"
        )

    def test_imessage_applies_final_output_cleanup(self):
        result = SimpleNamespace(returncode=0, stderr="")
        with patch.object(imessage.subprocess, "run", return_value=result) as send:
            imessage.send("Team One — signed a player.", "chat-1")

        self.assertEqual(send.call_args.args[0][-1], "Team One, signed a player.")

    def test_imessage_sends_link_separately_for_preview(self):
        result = SimpleNamespace(returncode=0, stderr="")
        with patch.object(imessage.subprocess, "run", return_value=result) as send:
            imessage.send(
                "Source: [ESPN](https://www.espn.com/nfl/story?utm_source=openai)",
                "chat-1",
            )

        sent_text = [call.args[0][-1] for call in send.call_args_list]
        self.assertEqual(sent_text, ["Source: ESPN", "https://www.espn.com/nfl/story"])

    def test_routine_add_leads_with_news_without_hype(self):
        team = SimpleNamespace(team_name="Team One")
        activity = SimpleNamespace(actions=[(team, "FA ADDED", player("Player A"), 0)])
        with patch.object(formatter.random, "choice", side_effect=lambda rows: rows[0]):
            result = formatter.format_activity(activity)

        self.assertEqual(result, "ESPN: Team One added WR Player A (NFL).")
        self.assertNotIn("BREAKING", result)
        self.assertNotIn("🚨", result)
        self.assertNotIn("—", result)

    def test_trade_reports_compensation_in_one_sentence(self):
        team_one = SimpleNamespace(team_name="Team One")
        team_two = SimpleNamespace(team_name="Team Two")
        actions = [
            (team_one, "TRADE_RECEIVED", player("Player A"), 0),
            (team_two, "TRADE_RECEIVED", player("Player B", "RB"), 0),
        ]
        with patch.object(formatter, "_src", return_value="per ESPN."):
            result = formatter._format_trade(actions)

        self.assertEqual(
            result,
            "Trade: Team One acquired WR Player A (NFL) from Team Two "
            "in exchange for RB Player B (NFL), per ESPN.",
        )


if __name__ == "__main__":
    unittest.main()
