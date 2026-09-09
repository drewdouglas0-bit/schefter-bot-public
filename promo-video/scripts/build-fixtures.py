"""Generate public demo copy with the real formatter. No credentials or network."""
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# The formatter/recap only need in-memory state. Avoid loading the real .env.
sys.modules["schefter.config"] = NS()
from schefter import formatter
from schefter.features import recap

random.seed(5)
jake = NS(team_id=1, team_name="Jake's Rebuild", wins=0, losses=1)
maya = NS(team_id=2, team_name="Sunday Scaries", wins=1, losses=0)
warren = NS(name="Jaylen Warren", position="RB", proTeam="PIT")
ford = NS(name="Jerome Ford", position="RB", proTeam="CLE")
bench = [NS(name="Chris Olave", position="WR", proTeam="NO", points=28.1, slot_position="BE"),
         NS(name="Bench RB", position="RB", proTeam="", points=14.6, slot_position="BE")]
activity = NS(actions=[(jake, "WAIVER ADDED", warren, 31)])
waiver = formatter.format_activity(activity)
drop = formatter.format_activity(NS(actions=[(jake, "DROPPED", ford, 0)]))
box = NS(home_team=maya, away_team=jake, home_score=128.4, away_score=96.2,
         home_lineup=[], away_lineup=bench)
league = NS(current_week=2, year=2026, box_scores=lambda week: [box])
full_recap = recap.run(league, {"last_run": {}}, NS())[0]
lines = full_recap.splitlines()
recap_excerpt = "\n".join([lines[0], "", lines[2], "", next(x for x in lines if x.startswith("High scorer:")),
                              "", next(x for x in lines if "left 42.7" in x)])
fixture = {
    "disclosure": "Illustrative demo · fictional league events",
    "waiver": waiver,
    "drop": drop,
    "recapFull": full_recap,
    "recapExcerpt": recap_excerpt,
    "matchups": {"week": 1, "matchups": [{"home": "Sunday Scaries", "home_score": 128.4,
                                          "away": "Jake's Rebuild", "away_score": 96.2}]},
    "scriptedAnswers": {
        "drop": "Jake's Rebuild released RB Jerome Ford in a separate move, per ESPN.",
        "matchup": "Sunday Scaries leads Jake's Rebuild, 128.4-96.2 in Week 1, per ESPN."
    },
    "provenance": {
        "waiver": "schefter.formatter.format_activity, fictional fixture",
        "recap": "schefter.features.recap.run, excerpt from fictional fixture",
        "answers": "Scripted demo examples grounded in fixture; not live model output"
    }
}
target = ROOT / "promo-video/src/demo.json"
target.write_text(json.dumps(fixture, indent=2) + "\n")
print(f"Generated {target.relative_to(ROOT)} from real bot templates.")
print(waiver)
print(recap_excerpt)
