# 🏀 NBA Live Tracker

A Streamlit dashboard that tracks live NBA games with auto-refreshing scores,
team logos, player headshots, top scorer leaders, and an **AI voice announcer**
(via ElevenLabs) that calls out every made shot, foul, turnover, and timeout
as it happens.

The New York Knicks game is pinned to the top with a ⭐.

## Features

- Auto-refresh every 15 seconds
- All live games shown, Knicks pinned first
- Team logos and player headshots from the NBA CDN
- Top 5 scoring leaders per team (pts / reb / ast)
- ElevenLabs voice announcer for live play-by-play
- Toggles: master auto-announce on/off, Knicks-only audio
- Manual "🎙️ Announce" button per game for a score recap

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your ElevenLabs API key
streamlit run app.py
```

Then open http://localhost:8501.

## Environment

- `ELEVENLABS_API_KEY` — get one at https://elevenlabs.io/app/settings/api-keys

If the key is missing the app still works; only the voice announcer is disabled.

## Notes

- Browsers may block autoplay until you click anywhere on the page once.
- NBA API has no auth; the only secret is the ElevenLabs key.
