import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from nba_api.live.nba.endpoints import boxscore, playbyplay, scoreboard
from streamlit_autorefresh import st_autorefresh

load_dotenv(Path.home() / ".env")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "pNInz6obpgDQGcFmaJgB"  # Adam

LOGO_URL = "https://cdn.nba.com/logos/nba/{tid}/global/L/logo.svg"
HEADSHOT_URL = "https://cdn.nba.com/headshots/nba/latest/260x190/{pid}.png"

st.set_page_config(page_title="NBA Live Tracker", layout="wide")
st_autorefresh(interval=15_000, key="refresh")

st.title("🏀 NBA Live Tracker")

st.session_state.setdefault("last_action", {})  # gameId -> last actionNumber announced
st.session_state.setdefault("auto_announce", True)
st.session_state.setdefault("knicks_only_audio", False)
st.session_state.setdefault("audio_queue", [])

c1, c2 = st.columns(2)
st.session_state.auto_announce = c1.toggle("🔊 Auto-announce live plays", value=st.session_state.auto_announce)
st.session_state.knicks_only_audio = c2.toggle("⭐ Knicks-only audio", value=st.session_state.knicks_only_audio)

games = scoreboard.ScoreBoard().get_dict()['scoreboard']['games']
if not games:
    st.info("No games scheduled.")
    st.stop()

knicks_games = [g for g in games if "Knicks" in (g['homeTeam']['teamName'], g['awayTeam']['teamName'])]
ordered = knicks_games + [g for g in games if g not in knicks_games]


ABBREV = [
    ("3PT", "three pointer"), ("2PT", "two pointer"), ("FT", "free throw"),
    ("AST", "assist"), ("REB", "rebound"), ("BLK", "block"), ("STL", "steal"),
    ("TO", "turnover"), ("PF", "personal foul"), ("OOB", "out of bounds"),
    ("Q1", "first quarter"), ("Q2", "second quarter"),
    ("Q3", "third quarter"), ("Q4", "fourth quarter"),
    ("OT", "overtime"), ("pts", "points"), ("reb", "rebounds"), ("ast", "assists"),
]

def expand(text: str) -> str:
    import re
    for short, long in ABBREV:
        text = re.sub(rf"\b{re.escape(short)}\b", long, text, flags=re.IGNORECASE)
    return text

def tts(text: str) -> bytes | None:
    text = expand(text)
    if not ELEVEN_KEY:
        return None
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_turbo_v2_5",
              "voice_settings": {"stability": 0.4, "similarity_boost": 0.75, "style": 0.7}},
        timeout=30,
    )
    if r.status_code != 200:
        st.error(f"ElevenLabs {r.status_code}: {r.text[:160]}")
        return None
    return r.content


SIGNIFICANT = {"2pt", "3pt", "freethrow", "rebound", "turnover", "foul",
               "timeout", "substitution", "period", "jumpball", "game", "ejection"}


def describe(action) -> str | None:
    atype = (action.get('actionType') or '').lower()
    desc = action.get('description') or ''
    if atype not in SIGNIFICANT:
        return None
    if atype in ("2pt", "3pt", "freethrow") and action.get('shotResult') != 'Made':
        return None  # only announce makes (misses are noisy)
    if atype == "rebound":
        return None  # too frequent
    if atype == "substitution":
        return None
    return desc.strip() or None


def fetch_new_plays(game_id: str, is_knicks: bool):
    """Return (announcement_text, latest_action_number) for plays since last seen."""
    try:
        pbp = playbyplay.PlayByPlay(game_id=game_id).get_dict()['game']
    except Exception:
        return None, None
    actions = pbp.get('actions', [])
    if not actions:
        return None, None
    last_seen = st.session_state.last_action.get(game_id)
    latest_num = actions[-1].get('actionNumber')

    if last_seen is None:
        # First time seeing this game — don't backflood, just mark current.
        return None, latest_num

    new_actions = [a for a in actions if a.get('actionNumber', 0) > last_seen]
    if not new_actions:
        return None, latest_num

    lines = []
    for a in new_actions[-4:]:  # cap to last 4 new events
        d = describe(a)
        if d:
            lines.append(d)
    if not lines:
        return None, latest_num

    prefix = "Knicks update! " if is_knicks else ""
    text = prefix + " ".join(lines)
    return text, latest_num


def render_game(game):
    home, away = game['homeTeam'], game['awayTeam']
    is_knicks = "Knicks" in (home['teamName'], away['teamName'])
    gid = game['gameId']
    status = (game.get('gameStatus') or 0)  # 1 pre, 2 live, 3 final
    title = f"{'⭐ ' if is_knicks else ''}{away['teamCity']} {away['teamName']} @ {home['teamCity']} {home['teamName']}"

    with st.expander(title, expanded=is_knicks or len(ordered) <= 3):
        lc, c1, mid, c2, rc = st.columns([1, 1, 1, 1, 1])
        lc.image(LOGO_URL.format(tid=away['teamId']), width=80)
        c1.metric(away['teamTricode'], away['score'])
        mid.markdown(f"**{game.get('gameStatusText','')}**\n\nQ{game.get('period',0)} • {game.get('gameClock','') or '—'}")
        c2.metric(home['teamTricode'], home['score'])
        rc.image(LOGO_URL.format(tid=home['teamId']), width=80)

        try:
            bs = boxscore.BoxScore(game_id=gid).get_dict()['game']
            cols = st.columns(2)
            for col, side, tri in [(cols[0], 'awayTeam', away['teamTricode']),
                                   (cols[1], 'homeTeam', home['teamTricode'])]:
                played = [p for p in bs[side].get('players', [])
                          if p.get('statistics', {}).get('minutesCalculated', 'PT00M') != 'PT00M']
                played.sort(key=lambda p: p['statistics'].get('points', 0), reverse=True)
                with col:
                    st.markdown(f"**{tri} Leaders**")
                    for p in played[:5]:
                        s = p['statistics']
                        pcols = st.columns([1, 4])
                        pid = p.get('personId')
                        if pid:
                            pcols[0].image(HEADSHOT_URL.format(pid=pid), width=50)
                        pcols[1].write(f"**{p['name']}** — {s.get('points',0)} pts, {s.get('reboundsTotal',0)} reb, {s.get('assists',0)} ast")
        except Exception as e:
            st.caption(f"Box score unavailable: {e}")

        # Auto-announce live plays
        if status == 2 and st.session_state.auto_announce:
            if st.session_state.knicks_only_audio and not is_knicks:
                pass
            else:
                text, latest = fetch_new_plays(gid, is_knicks)
                if latest is not None:
                    st.session_state.last_action[gid] = latest
                if text:
                    st.session_state.audio_queue.append((gid, text))


if not ELEVEN_KEY:
    st.warning("ELEVENLABS_API_KEY not set — voice announcer disabled.")

for g in ordered:
    render_game(g)

# Play queued announcements (new plays detected this refresh)
if st.session_state.audio_queue:
    st.markdown("### 🎙️ Live Calls")
    for gid, text in st.session_state.audio_queue:
        st.caption(f"[{gid}] {text}")
        audio = tts(text)
        if audio:
            st.audio(audio, format="audio/mpeg", autoplay=True)
    st.session_state.audio_queue = []
