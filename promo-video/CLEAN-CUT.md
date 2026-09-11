# Phone-only revision

39 seconds, one fixed phone on a flat #efeeeb background. No stadium, branding,
headlines, year label, diagrams, CTA, or music. The older v1 film is preserved.

The phone proportions, narrow graphite bezel, display spacing, pale surfaces,
rounded controls, blue/gray bubbles, and quiet continuous scrolling follow the
provided Instinct reference. All interface elements are newly drawn in code.
Group participants remain visible so this reads as a group conversation, not a DM.

The bot's saved contact is displayed as **Adam Schefter**, with a real contact
photo, as requested. This is an independent bot demo, not messages authored by
Adam Schefter and not an endorsement. No actual contacts or bot configuration
are changed by the video source. Group events, human messages, and model replies
remain scripted; waiver and recap copy is checked against the real formatter fixture.

## Rebuild

```bash
npm run audio:clean
npm run check
npm run stills:clean
npm run render:clean
npm run render:clean:feed
```

- `out/schefter-bot-vertical-clean-v2.mp4`: 1080×1920, closest to the reference.
- `out/schefter-bot-linkedin-clean-v2.mp4`: 1080×1350, centered feed alternative.

The 12 short, original synthesized sent/received effects use the same frame
timeline as the chat. The spaces between arrivals are digital silence. No Apple
audio recordings are used. No bot typing indicator is simulated.

## Photo attribution and video license

Contact photo: **All-Pro Reels / Joe Glorioso**, "Adam Schefter 2022".
The source was cropped by Wikimedia Commons contributors, including Righanred.
This composition displays the photograph in a circular avatar.

Source: https://commons.wikimedia.org/wiki/File:Adam_Schefter_2022_(cropped)_(cropped).jpg

License: **Creative Commons Attribution-ShareAlike 2.0 Generic**
https://creativecommons.org/licenses/by-sa/2.0/

The clean-v2 video and the avatar adaptation are offered under CC BY-SA 2.0.
Original source code remains MIT licensed; bundled fonts retain their OFL terms.
The photo license does not imply endorsement or grant personality/trademark rights.
Keep the attribution and unofficial-demo disclosure with any shared video. Both
are also embedded in the MP4 metadata. No Instinct source assets are redistributed.

This revision is a local review copy. The already-published v1 GitHub release has
not been replaced.
