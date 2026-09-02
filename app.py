import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import altair as alt
import os
import requests
import textwrap
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. Page Config & Setup
# -----------------------------------------------------------------------------
st.set_page_config(page_title="NHL AI Game Predictor", page_icon="🏒", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "nhl_data.db")

# 6.0 WUV NHL 32 Teams Database (English Names & Abbrevs)
TEAMS = {
    'EDM': {'name': 'Edmonton Oilers', 'wuv': 6.82},
    'FLA': {'name': 'Florida Panthers', 'wuv': 6.72},
    'COL': {'name': 'Colorado Avalanche', 'wuv': 6.68},
    'CAR': {'name': 'Carolina Hurricanes', 'wuv': 6.65},
    'TBL': {'name': 'Tampa Bay Lightning', 'wuv': 6.62},
    'NYR': {'name': 'New York Rangers', 'wuv': 6.60},
    'TOR': {'name': 'Toronto Maple Leafs', 'wuv': 6.56},
    'DAL': {'name': 'Dallas Stars', 'wuv': 6.52},
    'WPG': {'name': 'Winnipeg Jets', 'wuv': 6.48},
    'VAN': {'name': 'Vancouver Canucks', 'wuv': 6.45},
    'BOS': {'name': 'Boston Bruins', 'wuv': 6.42},
    'VGK': {'name': 'Vegas Golden Knights', 'wuv': 6.38},
    'NJD': {'name': 'New Jersey Devils', 'wuv': 6.32},
    'LAK': {'name': 'Los Angeles Kings', 'wuv': 6.28},
    'NSH': {'name': 'Nashville Predators', 'wuv': 6.24},
    'MIN': {'name': 'Minnesota Wild', 'wuv': 6.18},
    'NYI': {'name': 'New York Islanders', 'wuv': 6.12},
    'PIT': {'name': 'Pittsburgh Penguins', 'wuv': 6.08},
    'WSH': {'name': 'Washington Capitals', 'wuv': 6.02},
    'OTT': {'name': 'Ottawa Senators', 'wuv': 5.95},
    'DET': {'name': 'Detroit Red Wings', 'wuv': 5.90},
    'PHI': {'name': 'Philadelphia Flyers', 'wuv': 5.85},
    'BUF': {'name': 'Buffalo Sabres', 'wuv': 5.80},
    'SEA': {'name': 'Seattle Kraken', 'wuv': 5.75},
    'STL': {'name': 'St. Louis Blues', 'wuv': 5.70},
    'CGY': {'name': 'Calgary Flames', 'wuv': 5.65},
    'UTA': {'name': 'Utah Hockey Club', 'wuv': 5.60},
    'MTL': {'name': 'Montreal Canadiens', 'wuv': 5.52},
    'CHI': {'name': 'Chicago Blackhawks', 'wuv': 5.42},
    'ANA': {'name': 'Anaheim Ducks', 'wuv': 5.35},
    'CBJ': {'name': 'Columbus Blue Jackets', 'wuv': 5.28},
    'SJS': {'name': 'San Jose Sharks', 'wuv': 5.15}
}

def get_team_wuv(team_abbr_or_name):
    if team_abbr_or_name in TEAMS:
        return TEAMS[team_abbr_or_name]['wuv']
    for k, v in TEAMS.items():
        if v['name'] == team_abbr_or_name:
            return v['wuv']
    return 6.00

def predict_matchup(home_team, away_team):
    h_base = get_team_wuv(home_team)
    a_base = get_team_wuv(away_team)

    h_wuv = round(h_base + 0.20, 2)
    a_wuv = round(a_base, 2)
    gap = round(h_wuv - a_wuv, 2)

    pred_winner = home_team if gap >= 0 else away_team
    return pred_winner, abs(gap), h_wuv, a_wuv

# Fetch official live NHL schedule from Web API
@st.cache_data(ttl=600)
def fetch_live_nhl_schedule(date_str):
    url = f"https://api-web.nhle.com/v1/schedule/{date_str}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            games = []
            for gw in data.get("gameWeek", []):
                if gw.get("date") == date_str:
                    for g in gw.get("games", []):
                        h_tri = g.get("homeTeam", {}).get("abbrev")
                        a_tri = g.get("awayTeam", {}).get("abbrev")
                        state = g.get("gameState")
                        h_score = g.get("homeTeam", {}).get("score")
                        a_score = g.get("awayTeam", {}).get("score")
                        
                        games.append({
                            "home_team": h_tri,
                            "visit_team": a_tri,
                            "state": state,
                            "home_score": h_score,
                            "away_score": a_score
                        })
            return games
    except Exception:
        pass
    return []

@st.cache_data(ttl=3600)
def fetch_available_nhl_dates():
    url = "https://api-web.nhle.com/v1/schedule/now"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            dates = [gw.get("date") for gw in data.get("gameWeek", []) if len(gw.get("games", [])) > 0]
            if dates:
                return dates
    except Exception:
        pass
    return ["2026-09-29"]

def load_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season TEXT DEFAULT '2026-27',
            date TEXT NOT NULL,
            home_team TEXT NOT NULL,
            visit_team TEXT NOT NULL,
            predicted_winner TEXT NOT NULL,
            predicted_gap REAL NOT NULL,
            home_uv REAL NOT NULL,
            visit_uv REAL NOT NULL,
            actual_winner TEXT,
            is_correct INTEGER
        )
    """)
    conn.commit()
    
    cursor.execute("DELETE FROM predictions WHERE date LIKE '2026-08%'")
    conn.commit()

    df = pd.read_sql("SELECT * FROM predictions ORDER BY date ASC, id ASC", conn)
    conn.close()
    return df

df = load_data()

# Top 7 Sports Navigation Bar (Clean English Labels & URLs)
# Top Navigation Bar (7 Leagues)
nav_cols = st.columns(7)
with nav_cols[0]:
    st.link_button("🏀 NBA ↗", "https://nba-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[1]:
    st.link_button("⚾ MLB ↗", "https://mlb-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[2]:
    st.link_button("⚽ EPL ↗", "https://epl-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[3]:
    st.link_button("⚽ La Liga ↗", "https://llg-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[4]:
    st.button("🏒 NHL (Current)", disabled=True, use_container_width=True)
with nav_cols[5]:
    st.link_button("🏈 NFL ↗", "https://nfl-uv-prediction.streamlit.app/", use_container_width=True)
with nav_cols[6]:
    st.link_button("⚽ MLS ↗", "https://mls-uv-prediction.streamlit.app/", use_container_width=True)

st.divider()

# Main Title
st.title("🏒 NHL AI Game Outcome Predictor (by WUV predictor)")

# -----------------------------------------------------------------------------
# 🎛️ Season Filter
# -----------------------------------------------------------------------------
season_col1, season_col2 = st.columns([3, 7])
with season_col1:
    selected_season = st.selectbox(
        "🏆 Select Season:",
        ["2026-27 Regular Season (Current)", "2025-26 Regular Season"],
        index=0
    )

if 'season' in df.columns and not df.empty:
    season_key = "2026-27" if "2026-27" in selected_season else "2025-26"
    season_df = df[df['season'] == season_key].copy()
else:
    season_df = df.copy()

season_df['total_no'] = None
valid_mask = season_df['actual_winner'] != 'Postponed' if not season_df.empty else pd.Series()
if not season_df.empty and valid_mask.any():
    season_df.loc[valid_mask, 'total_no'] = range(1, len(season_df[valid_mask]) + 1)
    season_df['total_no'] = season_df['total_no'].fillna('Postponed')

stats_df = season_df[
    (season_df['actual_winner'] != 'Postponed') & 
    (season_df['actual_winner'].notna()) & 
    (season_df['actual_winner'] != '')
].copy() if not season_df.empty else pd.DataFrame()

# -----------------------------------------------------------------------------
# 1. [Top] Cumulative Prediction Accuracy
# -----------------------------------------------------------------------------
st.header(f"📊 Cumulative Prediction Accuracy ({selected_season})")
total_stats = len(stats_df)
correct_total = stats_df['is_correct'].sum() if total_stats > 0 else 0

col_acc, col_track = st.columns([2, 1])

if total_stats > 0:
    total_acc = (correct_total / total_stats) * 100
    status_suffix = " (⚡ Godlike, Market Distorting)" if total_acc >= 60 else ""
    
    with col_acc:
        st.subheader(f"Overall Accuracy: `{total_acc:.2f}%`{status_suffix}")
        st.markdown(f"**Correct Predictions:** {int(correct_total)} / **Total Games:** {total_stats}")
    
    with col_track:
        remaining = 100 - total_stats
        if remaining > 0:
            st.metric("Games for 100-Game Verification", f"{remaining} games left")
        else:
            st.metric("Verification Status", "Verified (Godlike Tier)")
else:
    with col_acc:
        st.subheader("Overall Accuracy: `-`")
        st.markdown(f"**Correct Predictions:** 0 / **Total Games:** 0 (Real-time tracking will begin once {selected_season} games finish)")
    with col_track:
        st.metric("Games for 100-Game Verification", "100 games left")

st.markdown("---")

# -----------------------------------------------------------------------------
# 2. [Middle] Daily Prediction Accuracy (Recent 7 Days)
# -----------------------------------------------------------------------------
st.header("📈 Daily Prediction Accuracy (Recent 7 Days)")

if not stats_df.empty:
    daily_stats = stats_df.groupby('date').agg(
        total_games=('home_team', 'count'), 
        correct_games=('is_correct', 'sum') 
    ).reset_index()

    daily_stats['accuracy'] = (daily_stats['correct_games'] / daily_stats['total_games']) * 100
    
    def get_bar_color(acc):
        if acc >= 60: return '#A020F0'      # Purple (Godlike)
        elif acc >= 55: return '#FF0000'    # Red (Master/AI)
        elif acc >= 52.4: return '#FFA500'  # Orange (Pro/Expert)
        elif acc >= 45: return '#1E90FF'    # Blue (Above Average)
        elif acc >= 35: return '#008000'    # Green (Average)
        else: return '#808080'             # Gray (No Bet)

    daily_stats['bar_color'] = daily_stats['accuracy'].apply(get_bar_color)
    daily_stats['label_text'] = daily_stats.apply(
        lambda x: f"{int(x['correct_games'])}/{int(x['total_games'])}", 
        axis=1
    )

    daily_stats_7d = daily_stats.sort_values('date', ascending=True).tail(7)

    base = alt.Chart(daily_stats_7d).encode(x=alt.X('date', title='Date (NHL Local)'))
    bars = base.mark_bar().encode(
        y=alt.Y('accuracy', title='Accuracy (%)', scale=alt.Scale(domain=[0, 110])),
        color=alt.Color('bar_color', scale=None),
        tooltip=['date', 'accuracy', 'total_games']
    )
    text = base.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold').encode(
        y='accuracy', text='label_text'
    )
    st.altair_chart((bars + text).properties(height=350), use_container_width=True)
else:
    st.info(f"💡 Real-time accuracy tracking will begin as soon as {selected_season} games finish.")

st.markdown("""
<div style="text-align: center; padding: 12px; background-color: #f0f2f6; border-radius: 10px; line-height: 1.6;">
    <span style="color: #A020F0;">●</span> <b>Godlike</b> (60%↑) &nbsp;&nbsp;
    <span style="color: #FF0000;">●</span> <b>Master/AI</b> (55%~60%) &nbsp;&nbsp;
    <span style="color: #FFA500;">●</span> <b>Pro/Expert</b> (52.4%~55%) &nbsp;&nbsp;
    <span style="color: #1E90FF;">●</span> <b>Above Average</b> (45%~52.4%) &nbsp;&nbsp;
    <span style="color: #008000;">●</span> <b>Average</b> (35%~45%) &nbsp;&nbsp;
    <span style="color: #808080;">●</span> <b>No Bet</b> (35%↓)
    <br><small>* 52.4% is the statistical break-even threshold.</small>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 3. [Bottom] Daily Detailed Prediction Report
# -----------------------------------------------------------------------------
st.header("📋 Daily Detailed Prediction Report")

available_dates = fetch_available_nhl_dates()
default_target_date = datetime.strptime(available_dates[0], "%Y-%m-%d").date()

selected_date = st.date_input("Select Date (Official NHL Schedule):", value=default_target_date)
selected_date_str = selected_date.strftime("%Y-%m-%d")

# Live NHL API schedule query
live_games = fetch_live_nhl_schedule(selected_date_str)

if live_games:
    report_list = []
    for idx, g in enumerate(live_games, 1):
        h_t = g['home_team']
        a_t = g['visit_team']
        pred_w, gap, h_uv, a_uv = predict_matchup(h_t, a_t)
        pred_wuv = h_uv if pred_w == h_t else a_uv
        
        act_w = g.get('home_team') if g.get('state') == 'OFF' and g.get('home_score', 0) > g.get('away_score', 0) else (g.get('visit_team') if g.get('state') == 'OFF' else '')
        is_corr = 1 if act_w == pred_w else (0 if act_w != '' else None)
        
        status_str = "⏳ Pending"
        if act_w != '':
            status_str = "✅ Correct" if is_corr == 1 else "❌ Incorrect"

        report_list.append({
            'No.(Day)': idx,
            'No.(Total)': idx,
            'Home Team': f"{h_t}({h_uv:.2f})",
            'Away Team': f"{a_t}({a_uv:.2f})",
            'Predicted Winner': f"{pred_w}({pred_wuv:.2f})",
            'Predicted Gap (UV)': f"{gap:.2f}",
            'Actual Winner': act_w if act_w != '' else '⏳ Pending',
            'Status': status_str
        })
    
    rep_df = pd.DataFrame(report_list)

    finished_count = len([r for r in report_list if r['Actual Winner'] != '⏳ Pending'])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Games Today", f"{len(live_games)} Games")
    col2.metric("Finished Games", f"{finished_count} Games")
    col3.metric("Daily Accuracy", "Predictions Ready (Pending)" if finished_count == 0 else f"{(sum([1 for r in report_list if r['Status']=='✅ Correct'])/finished_count)*100:.1f}%")

    table_height = max(400, (len(rep_df) + 1) * 38 + 25)
    st.dataframe(rep_df, hide_index=True, use_container_width=True, height=table_height)
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Games Today", "0 Games")
    col2.metric("Finished Games", "0 Games")
    col3.metric("Daily Accuracy", "-")
    st.info(f"⚠️ No scheduled NHL games on {selected_date_str}. ({selected_season} Opener: {available_dates[0]}~)")

# -----------------------------------------------------------------------------
# 4. [Footer]
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #888888; padding-top: 20px;">
        <p>ⓒ DROPSHOT (Business Registration No: 578-81-03214)</p>
        <p>Contact us: liskhan@gmail.com</p>
    </div>
    """,
    unsafe_allow_html=True
)
