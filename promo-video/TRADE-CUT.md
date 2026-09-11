# 25-second trade cut (v3)

Same fixed phone, colors, contact photo, and group layout as the approved clean
v2. Exactly 750 frames at 30 fps. Nine messages, quicker arrivals, no music,
logos, titles, stadium, year label, or end card. Previous exports are preserved.

Jake claims Warren for $31. Maya offers Olave for Warren, Jake replies Yes,
the bot reports submission, and the group reacts. All league activity and
human dialogue are fictional; this is a staged product demonstration, not a
recording of an actual group chat. The saved contact is Adam Schefter as
requested, but the bot is independent and not affiliated with or endorsed by him.

## Scenario verification

`scripts/build-trade-fixture.py` runs the real `trades.create`,
`trades.bare_response`, `espn_trade.execute`, and `_post` with fictional rosters
and HTTP mocks. Configuration is injected before import: no real .env, league,
trade state, contact address, or credential is loaded. State is temporary.

Verified: proposal starts pending; no provider calls before consent; proposer
and bystander cannot accept; recipient Yes triggers TRADE_PROPOSAL followed by
TRADE_ACCEPT; execution is recorded as submitted; repeated Yes cannot resubmit.
The acceptance bubble is verbatim bot output. The offer summary and human
messages are scripted, grounded in the verified proposal—not captured LLM output.
The waiver bubble is the real formatter output for a fictional activity.

This verifies the local trade workflow, **not a live ESPN integration test** or
final roster settlement. ESPN submission still depends on actual configuration,
credentials, permissions, and league rules in a real deployment.

## Audio

Reads the native send and receive recordings already installed on this Mac:

- IMDaemonCore.framework: `Sent Message.aiff`
- ToneLibrary.framework: `AlertTones/ReceivedMessage.caf`

The audio builder preserves their pitch and speed, places them on the same
frame timeline as the bubbles, and leaves silence between arrivals. Only Drew's
outgoing blue bubbles use the send sound. Peak headroom is checked. Sound sources
and the rendered WAV are not added to Git. Override `IMESSAGE_SENT_SOUND` and
`IMESSAGE_RECEIVED_SOUND` to use other permitted recordings on another machine.

Apple system sounds are third-party material, **not MIT or CC-licensed by this
project**. Availability on a Mac does not establish permission to redistribute
them. Native-audio exports are local review copies; resolve audio permissions or
substitute cleared effects before public distribution. The published release is
silent.

## Rebuild

With the bot's Python dependencies active, FFmpeg installed, and Chrome available:

```bash
npm run fixtures:trade
npm run audio:trade
npm run check
npm run stills:trade
npm run render:trade
npm run render:trade:feed
```

To test a different local bot checkout, pass its path to the fixture script:
`python3 scripts/build-trade-fixture.py --bot-root /path/to/schefter-bot`.

Outputs:

- `out/schefter-bot-vertical-trade-v3.mp4`: 1080×1920.
- `out/schefter-bot-linkedin-trade-v3.mp4`: 1080×1350.
- `out/trade-v3-audio-report.json`: sound event timing and measured peak.

## Photo attribution

Adam Schefter 2022, All-Pro Reels / Joe Glorioso. Cropped by Wikimedia Commons
contributors including Righanred; displayed here as a circular contact avatar.

Source: https://commons.wikimedia.org/wiki/File:Adam_Schefter_2022_(cropped)_(cropped).jpg

License: CC BY-SA 2.0, https://creativecommons.org/licenses/by-sa/2.0/.
Photo and visual adaptation retain those terms; Apple audio is excluded from
that grant. Source code remains MIT, font remains OFL. Keep the attribution
and unofficial-demo disclosure with any shared version; neither implies endorsement.
