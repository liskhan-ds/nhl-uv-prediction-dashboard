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
# 1. 페이지 설정 및 상단 탭 네비게이션
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="🏒 NHL AI 승부예측",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "nhl_data.db")

# 상단 탭 네비게이션 (NBA, MLB, EPL, NHL 4대 종목 통일)
nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([2.5, 2.5, 2.5, 2.5])
with nav_col1:
    st.link_button(
        "🏀 NBA 대시보드 ↗", 
        "https://nba-uv-prediction-dashboard.streamlit.app/",
        use_container_width=True
    )
with nav_col2:
    st.link_button(
        "⚾ MLB 대시보드 ↗", 
        "https://mlb-uv-prediction-dashboard.streamlit.app/",
        use_container_width=True
    )
with nav_col3:
    st.link_button(
        "⚽ EPL 대시보드 ↗", 
        "https://epl-uv-prediction-dashboard.streamlit.app/",
        use_container_width=True
    )
with nav_col4:
    st.button(
        "🏒 NHL 대시보드 (현재)", 
        disabled=True, 
        use_container_width=True
    )

st.divider()

# 메인 타이틀 및 본문 설명
st.title("🏒 NHL AI 승부예측 (by 6.0 WUV predictor)")
st.caption("6.0 WUV 기준 (수비/골리 3.0 UV + 공격/유닛 3.0 UV) | 라인업 6.0 WUV 전력 평가 | 홈 어드밴티지(+0.20 UV)")

# Custom CSS
st.markdown(textwrap.dedent("""
<style>
    .match-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    .team-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 14px;
    }
    .team-box {
        text-align: center;
        width: 42%;
    }
    .team-logo {
        width: 56px;
        height: 56px;
        object-fit: contain;
    }
    .team-name {
        font-weight: 700;
        font-size: 1.05rem;
        margin-top: 6px;
    }
    .uv-score {
        font-size: 1.35rem;
        font-weight: 800;
        color: #2563eb;
        margin-top: 4px;
    }
    .vs-badge {
        font-size: 0.85rem;
        font-weight: 800;
        color: #64748b;
        background: #f1f5f9;
        padding: 5px 12px;
        border-radius: 20px;
    }
    .pick-badge {
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
        color: white;
        padding: 10px 14px;
        border-radius: 8px;
        font-weight: 700;
        text-align: center;
        margin-top: 14px;
        font-size: 0.95rem;
    }
    .prob-bar-container {
        display: flex;
        height: 24px;
        border-radius: 12px;
        overflow: hidden;
        margin-top: 14px;
        font-weight: bold;
        font-size: 0.8rem;
        color: white;
    }
    .prob-home {
        background-color: #ef4444;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .prob-away {
        background-color: #3b82f6;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .live-badge {
        background-color: #10b981;
        color: white;
        font-size: 0.78rem;
        font-weight: bold;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
        margin-bottom: 12px;
    }
</style>
"""), unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. NHL 32개 팀 데이터 및 6.0 WUV 계산 엔진 (내부 스탯은 비공개)
# -----------------------------------------------------------------------------
TRI_TO_KOR = {
    "BOS": "보스턴 브루인스", "NYR": "뉴욕 레인저스", "FLA": "플로리다 팬서스",
    "CAR": "캐롤라이나 허리케인스", "EDM": "에드먼턴 오일러스", "DAL": "달라스 스타스",
    "COL": "콜로라도 애벌랜치", "VGK": "베가스 골든나이츠", "TOR": "토론토 메이플리프스",
    "TBL": "탬파베이 라이트닝", "WPG": "위니펙 제츠", "VAN": "밴쿠버 캐넉스",
    "NJD": "뉴저지 데빌스", "LAK": "로스앤젤레스 킹스", "NSH": "내슈빌 프레더터스",
    "MIN": "미네소타 와일드", "NYI": "뉴욕 아일랜더스", "PIT": "피츠버그 펭귄스",
    "WSH": "워싱턴 캐피털스", "PHI": "필라델피아 플라이어스", "DET": "디트로이트 레드윙스",
    "BUF": "버팔로 세이버스", "OTT": "오타와 세네터스", "MTL": "몬트리올 카나디엔스",
    "CGY": "캘거리 플레임스", "SEA": "시애틀 크라켄", "STL": "세인트루이스 블루스",
    "UTA": "유타 하키클럽", "CHI": "시카고 블랙호크스", "ANA": "애너하임 덕스",
    "SJS": "산호세 샤크스", "CBJ": "콜럼버스 블루재키츠"
}

TEAMS_DATA = {
    "보스턴 브루인스": {"tri": "BOS", "base_wuv": 4.54},
    "뉴욕 레인저스": {"tri": "NYR", "base_wuv": 4.62},
    "플로리다 팬서스": {"tri": "FLA", "base_wuv": 4.70},
    "캐롤라이나 허리케인스": {"tri": "CAR", "base_wuv": 4.65},
    "에드먼턴 오일러스": {"tri": "EDM", "base_wuv": 4.78},
    "달라스 스타스": {"tri": "DAL", "base_wuv": 4.58},
    "콜로라도 애벌랜치": {"tri": "COL", "base_wuv": 4.68},
    "베가스 골든나이츠": {"tri": "VGK", "base_wuv": 4.52},
    "토론토 메이플리프스": {"tri": "TOR", "base_wuv": 4.60},
    "탬파베이 라이트닝": {"tri": "TBL", "base_wuv": 4.64},
    "위니펙 제츠": {"tri": "WPG", "base_wuv": 4.56},
    "밴쿠버 캐넉스": {"tri": "VAN", "base_wuv": 4.55},
    "뉴저지 데빌스": {"tri": "NJD", "base_wuv": 4.48},
    "로스앤젤레스 킹스": {"tri": "LAK", "base_wuv": 4.46},
    "내슈빌 프레더터스": {"tri": "NSH", "base_wuv": 4.45},
    "미네소타 와일드": {"tri": "MIN", "base_wuv": 4.42},
    "뉴욕 아일랜더스": {"tri": "NYI", "base_wuv": 4.38},
    "피츠버그 펭귄스": {"tri": "PIT", "base_wuv": 4.35},
    "워싱턴 캐피털스": {"tri": "WSH", "base_wuv": 4.32},
    "필라델피아 플라이어스": {"tri": "PHI", "base_wuv": 4.25},
    "디트로이트 레드윙스": {"tri": "DET", "base_wuv": 4.28},
    "버팔로 세이버스": {"tri": "BUF", "base_wuv": 4.24},
    "오타와 세네터스": {"tri": "OTT", "base_wuv": 4.30},
    "몬트리올 카나디엔스": {"tri": "MTL", "base_wuv": 4.15},
    "캘거리 플레임스": {"tri": "CGY", "base_wuv": 4.20},
    "시애틀 크라켄": {"tri": "SEA", "base_wuv": 4.22},
    "세인트루이스 블루스": {"tri": "STL", "base_wuv": 4.21},
    "유타 하키클럽": {"tri": "UTA", "base_wuv": 4.18},
    "시카고 블랙호크스": {"tri": "CHI", "base_wuv": 4.08},
    "애너하임 덕스": {"tri": "ANA", "base_wuv": 4.05},
    "산호세 샤크스": {"tri": "SJS", "base_wuv": 3.95},
    "콜럼버스 블루재키츠": {"tri": "CBJ", "base_wuv": 4.02}
}

def get_team_info(team_name):
    if team_name in TEAMS_DATA:
        t = TEAMS_DATA[team_name]
        return t["tri"], t["base_wuv"]
    return "NHL", 4.20

def predict_matchup(home_team, away_team):
    h_tri, h_base = get_team_info(home_team)
    a_tri, a_base = get_team_info(away_team)

    # 홈 어드밴티지 +0.20 WUV
    h_wuv = round(h_base + 0.20, 2)
    a_wuv = round(a_base, 2)
    gap = round(h_wuv - a_wuv, 2)

    # 2-Way 로지스틱 확률 계산
    k = 1.35
    prob_h = 1.0 / (1.0 + np.exp(-k * gap))
    prob_a = 1.0 - prob_h

    p_home = round(prob_h * 100, 1)
    p_away = round(prob_a * 100, 1)

    base_g = 3.1
    exp_h = max(1, int(round(base_g + 0.85 * gap)))
    exp_a = max(1, int(round(base_g - 0.85 * gap)))
    if exp_h == exp_a:
        if gap > 0: exp_h += 1
        else: exp_a += 1

    if p_home >= 53.0:
        predicted_winner = home_team
        rec = f"🏒 [홈 승 추천] {home_team}"
    elif p_away >= 53.0:
        predicted_winner = away_team
        rec = f"🏒 [원정 승 추천] {away_team}"
    else:
        predicted_winner = home_team if p_home >= p_away else away_team
        rec = f"⚖️ [미세 우세] {predicted_winner}"

    return {
        "h_tri": h_tri, "a_tri": a_tri,
        "h_wuv": h_wuv, "a_wuv": a_wuv,
        "gap": gap,
        "p_home": p_home, "p_away": p_away,
        "exp_h": exp_h, "exp_a": exp_a,
        "predicted_winner": predicted_winner,
        "recommendation": rec
    }

# -----------------------------------------------------------------------------
# 3. Live NHL API 실시간 일정 연동 (비시즌 가짜 데이터 완전히 제거)
# -----------------------------------------------------------------------------
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
                        
                        h_kor = TRI_TO_KOR.get(h_tri, g.get("homeTeam", {}).get("commonName", {}).get("default", "홈팀"))
                        a_kor = TRI_TO_KOR.get(a_tri, g.get("awayTeam", {}).get("commonName", {}).get("default", "원정팀"))
                        
                        state = g.get("gameState")
                        h_score = g.get("homeTeam", {}).get("score")
                        a_score = g.get("awayTeam", {}).get("score")
                        
                        games.append({
                            "home_team": h_kor,
                            "away_team": a_kor,
                            "home_tri": h_tri,
                            "away_tri": a_tri,
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
            date TEXT NOT NULL,
            home_team TEXT NOT NULL,
            visit_team TEXT NOT NULL,
            predicted_winner TEXT NOT NULL,
            predicted_gap REAL NOT NULL,
            home_uv REAL NOT NULL,
            visit_uv REAL NOT NULL,
            home_prob REAL,
            visit_prob REAL,
            predicted_score TEXT,
            actual_winner TEXT,
            actual_score TEXT,
            is_correct INTEGER
        )
    """)
    conn.commit()

    # 비시즌 가짜 데이터 전량 삭제 (순수 실제 경기 전용)
    cursor.execute("DELETE FROM predictions")
    conn.commit()

    df = pd.read_sql("SELECT * FROM predictions ORDER BY date ASC, id ASC", conn)
    conn.close()
    return df

df = load_data()

# -----------------------------------------------------------------------------
# 4. [상단] 누적 예측 성적표 & 100경기 트래킹
# -----------------------------------------------------------------------------
df['total_no'] = None
valid_mask = df['actual_winner'] != 'Postponed' if not df.empty else pd.Series()
if not df.empty and valid_mask.any():
    df.loc[valid_mask, 'total_no'] = range(1, len(df[valid_mask]) + 1)
    df['total_no'] = df['total_no'].fillna('취소')

stats_df = df[
    (df['actual_winner'] != 'Postponed') & 
    (df['actual_winner'].notna()) & 
    (df['actual_winner'] != '')
].copy() if not df.empty else pd.DataFrame()

st.header("📊 누적 예측 성적표")
total_stats = len(stats_df)
correct_total = stats_df['is_correct'].sum() if total_stats > 0 else 0

col_acc, col_track = st.columns([2, 1])

if total_stats > 0:
    total_acc = (correct_total / total_stats) * 100
    status_suffix = " (⚡ 신계, 시장 왜곡급)" if total_acc >= 60 else (" (🔥 초고수/AI 등급)" if total_acc >= 55 else "")
    
    with col_acc:
        st.subheader(f"전체 예측률: `{total_acc:.2f}%`{status_suffix}")
        st.markdown(f"**적중 경기 수:** {int(correct_total)} / **통산 경기 수:** {total_stats}")
    
    with col_track:
        remaining = 100 - total_stats
        if remaining > 0:
            st.metric("100경기 시스템 검증까지", f"{remaining}경기 남음")
        else:
            st.metric("시스템 검증 상태", "검증 완료 (초고수 등급)")
else:
    with col_acc:
        st.subheader("전체 예측률: `-`")
        st.markdown("**적중 경기 수:** 0 / **통산 경기 수:** 0 (NHL 시즌 개막 후 경기 종료 시 자동 집계)")
    with col_track:
        st.metric("100경기 시스템 검증까지", "100경기 남음")

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. [중단] 일별 예측 성적표 (6단계 등급 및 라벨)
# -----------------------------------------------------------------------------
st.header("📈 일별 예측 성적표 (최근 7일)")

if not stats_df.empty:
    daily_stats = stats_df.groupby('date').agg(
        total_games=('home_team', 'count'), 
        correct_games=('is_correct', 'sum') 
    ).reset_index()

    daily_stats['accuracy'] = (daily_stats['correct_games'] / daily_stats['total_games']) * 100
    
    def get_bar_color(acc):
        if acc >= 60: return '#A020F0'      # 보라 (신계)
        elif acc >= 55: return '#FF0000'    # 빨강 (초고수/AI)
        elif acc >= 52.4: return '#FFA500'  # 주황 (프로/고수)
        elif acc >= 45: return '#1E90FF'    # 파랑 (노력하는 일반인)
        elif acc >= 35: return '#008000'    # 녹색 (지극히 정상인)
        else: return '#808080'             # 회색 (예측 금지)

    daily_stats['bar_color'] = daily_stats['accuracy'].apply(get_bar_color)
    daily_stats['label_text'] = daily_stats.apply(
        lambda x: f"{int(x['correct_games'])}/{int(x['total_games'])}", 
        axis=1
    )

    daily_stats_7d = daily_stats.sort_values('date', ascending=True).tail(7)

    base = alt.Chart(daily_stats_7d).encode(x=alt.X('date', title='날짜(NHL 현지)'))
    bars = base.mark_bar().encode(
        y=alt.Y('accuracy', title='적중률(%)', scale=alt.Scale(domain=[0, 110])),
        color=alt.Color('bar_color', scale=None),
        tooltip=['date', 'accuracy', 'total_games']
    )
    text = base.mark_text(align='center', baseline='bottom', dy=-5, fontSize=14, fontWeight='bold').encode(
        y='accuracy', text='label_text'
    )
    st.altair_chart((bars + text).properties(height=350), use_container_width=True)
else:
    st.info("💡 현재 NHL 비시즌(휴식기)입니다. 9월 말 시범경기 및 정규시즌 개막 후 종료된 경기가 실시간으로 집계됩니다.")

st.markdown(textwrap.dedent("""
<div style="text-align: center; padding: 12px; background-color: #f0f2f6; border-radius: 10px; line-height: 1.6;">
    <span style="color: #A020F0;">●</span> <b>신계</b> (60%↑) &nbsp;&nbsp;
    <span style="color: #FF0000;">●</span> <b>초고수/AI</b> (55%~60%) &nbsp;&nbsp;
    <span style="color: #FFA500;">●</span> <b>프로/고수</b> (52.4%~55%) &nbsp;&nbsp;
    <span style="color: #1E90FF;">●</span> <b>노력하는 일반인</b> (45%~52.4%) &nbsp;&nbsp;
    <span style="color: #008000;">●</span> <b>지극히 정상인</b> (35%~45%) &nbsp;&nbsp;
    <span style="color: #808080;">●</span> <b>예측 금지</b> (35%↓)
    <br><small>* 52.4%는 통계적 손익분기점(Breakeven) 기준입니다.</small>
</div>
"""), unsafe_allow_html=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 6. [메인] 당일 NHL 전 경기 매치업 카드 그리드 (Live API 공식 연동)
# -----------------------------------------------------------------------------
st.header("🏒 NHL 공식 일정 AI 승부예측 카드")

available_nhl_dates = fetch_available_nhl_dates()
default_target_date = datetime.strptime(available_nhl_dates[0], "%Y-%m-%d").date()

selected_date = st.date_input("🗓️ 확인하고 싶은 경기 날짜를 선택하세요 (NHL 공식 일정 자동 연동):", value=default_target_date)
selected_date_str = selected_date.strftime("%Y-%m-%d")

# Live API 조회
live_games = fetch_live_nhl_schedule(selected_date_str)

if live_games:
    st.markdown(f"<span class='live-badge'>📡 NHL Official API 실시간 일정 연동 중 ({selected_date_str} / {len(live_games)} 경기)</span>", unsafe_allow_html=True)
    display_matchups = [(g['home_team'], g['away_team']) for g in live_games]
else:
    display_matchups = []

if not display_matchups:
    st.warning(f"⚠️ {selected_date_str} 날짜에는 예정된 NHL 경기가 없습니다. (8월은 NHL 비시즌 기간입니다. 개막 예정일: {available_nhl_dates[0]}~)")
else:
    grid_cols = st.columns(2)
    
    for idx, (home_team, away_team) in enumerate(display_matchups):
        col_target = grid_cols[idx % 2]
        
        pred = predict_matchup(home_team, away_team)
        h_tri = pred['h_tri']
        a_tri = pred['a_tri']
        
        h_logo = f"https://assets.nhle.com/logos/nhl/svg/{h_tri}_light.svg"
        a_logo = f"https://assets.nhle.com/logos/nhl/svg/{a_tri}_light.svg"
        
        card_html = f"""<div class="match-card">
<div class="team-header">
<div class="team-box">
<img src="{a_logo}" class="team-logo" alt="{away_team}">
<div class="team-name">{away_team}</div>
<div style="font-size:0.78rem; color:#64748b;">(원정)</div>
<div class="uv-score">{pred['a_wuv']:.2f} WUV</div>
</div>
<div style="text-align:center;">
<span class="vs-badge">VS</span>
<div style="font-size:0.75rem; color:#64748b; margin-top:6px;">홈어드디 +0.20</div>
</div>
<div class="team-box">
<img src="{h_logo}" class="team-logo" alt="{home_team}">
<div class="team-name">{home_team}</div>
<div style="font-size:0.78rem; color:#64748b;">(홈)</div>
<div class="uv-score">{pred['h_wuv']:.2f} WUV</div>
</div>
</div>
<div class="prob-bar-container">
<div class="prob-away" style="width: {pred['p_away']}%;">원정 승 {pred['p_away']}%</div>
<div class="prob-home" style="width: {pred['p_home']}%;">홈 승 {pred['p_home']}%</div>
</div>
<div class="pick-badge">
🎯 {pred['recommendation']} &nbsp;|&nbsp; 예상 스코어 ({away_team} {pred['exp_a']} : {pred['exp_h']} {home_team})
</div>
</div>"""

        with col_target:
            st.markdown(card_html, unsafe_allow_html=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. [하단] 일별 상세 예측 리포트 (MLB/NBA 1:1 레이아웃)
# -----------------------------------------------------------------------------
st.header("📋 일별 상세 예측 리포트")

# 리포트용 데이터프레임 구성
if display_matchups:
    report_list = []
    for idx, (h_t, a_t) in enumerate(display_matchups, 1):
        res = predict_matchup(h_t, a_t)
        report_list.append({
            'No.(Day)': idx,
            'No.(Total)': idx,
            '홈 팀': h_t,
            '원정 팀': a_t,
            '예측 승리팀': res['predicted_winner'],
            '예상 격차(uv)': f"{abs(res['gap']):.2f}",
            '실제 승리팀': '⏳ 대기 중',
            '적중 여부': '⏳ 대기'
        })
    rep_df = pd.DataFrame(report_list)

    col1, col2, col3 = st.columns(3)
    col1.metric("해당일 총 경기 수", f"{len(display_matchups)} 경기")
    col2.metric("종료된 경기", "0 경기")
    col3.metric("일일 적중률", "예측 완료 (대기)")

    st.dataframe(rep_df, hide_index=True, use_container_width=True)
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("해당일 총 경기 수", "0 경기")
    col2.metric("종료된 경기", "0 경기")
    col3.metric("일일 적중률", "-")
    st.info("⚠️ 해당 날짜에는 예정된 NHL 경기가 없습니다.")

if st.button("데이터 새로고침"):
    st.rerun()

# -----------------------------------------------------------------------------
# 8. [최하단] 푸터 문구
# -----------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #888888; padding-top: 20px;">
        <p>ⓒ DROPSHOT (사업자 번호: 578-81-03214)</p>
        <p>Contact us: liskhan@gmail.com</p>
    </div>
    """,
    unsafe_allow_html=True
)
