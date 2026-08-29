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
# 1. 설정 및 데이터 로드 (시즌 필터 적용)
# -----------------------------------------------------------------------------
st.set_page_config(page_title="NHL AI 승부 예측", page_icon="🏒", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "nhl_data.db")

# 6.0 WUV NHL 32개 전 구단 2026-27 시즌 전력 지표 데이터베이스
TEAMS = {
    'BOS': {'name': '보스턴 브루인스', 'wuv': 4.54},
    'NYR': {'name': '뉴욕 레인저스', 'wuv': 4.62},
    'FLA': {'name': '플로리다 팬서스', 'wuv': 4.70},
    'CAR': {'name': '캐롤라이나 허리케인스', 'wuv': 4.65},
    'EDM': {'name': '에드먼턴 오일러스', 'wuv': 4.78},
    'DAL': {'name': '달라스 스타스', 'wuv': 4.58},
    'COL': {'name': '콜로라도 애벌랜치', 'wuv': 4.68},
    'VGK': {'name': '베가스 골든나이츠', 'wuv': 4.52},
    'TOR': {'name': '토론토 메이플리프스', 'wuv': 4.60},
    'TBL': {'name': '탬파베이 라이트닝', 'wuv': 4.64},
    'WPG': {'name': '위니펙 제츠', 'wuv': 4.56},
    'VAN': {'name': '밴쿠버 캐넉스', 'wuv': 4.55},
    'NJD': {'name': '뉴저지 데빌스', 'wuv': 4.48},
    'LAK': {'name': '로스앤젤레스 킹스', 'wuv': 4.46},
    'NSH': {'name': '내슈빌 프레더터스', 'wuv': 4.45},
    'MIN': {'name': '미네소타 와일드', 'wuv': 4.42},
    'NYI': {'name': '뉴욕 아일랜더스', 'wuv': 4.38},
    'PIT': {'name': '피츠버그 펭귄스', 'wuv': 4.35},
    'WSH': {'name': '워싱턴 캐피털스', 'wuv': 4.32},
    'PHI': {'name': '필라델피아 플라이어스', 'wuv': 4.25},
    'DET': {'name': '디트로이트 레드윙스', 'wuv': 4.28},
    'BUF': {'name': '버팔로 세이버스', 'wuv': 4.24},
    'OTT': {'name': '오타와 세네터스', 'wuv': 4.30},
    'MTL': {'name': '몬트리올 카나디엔스', 'wuv': 4.15},
    'CGY': {'name': '캘거리 플레임스', 'wuv': 4.20},
    'SEA': {'name': '시애틀 크라켄', 'wuv': 4.22},
    'STL': {'name': '세인트루이스 블루스', 'wuv': 4.21},
    'UTA': {'name': '유타 하키클럽', 'wuv': 4.18},
    'CHI': {'name': '시카고 블랙호크스', 'wuv': 4.08},
    'ANA': {'name': '애너하임 덕스', 'wuv': 4.05},
    'SJS': {'name': '산호세 샤크스', 'wuv': 3.95},
    'CBJ': {'name': '콜럼버스 블루재키츠', 'wuv': 4.02}
}

def get_team_wuv(team_abbr_or_name):
    if team_abbr_or_name in TEAMS:
        return TEAMS[team_abbr_or_name]['wuv']
    for k, v in TEAMS.items():
        if v['name'] == team_abbr_or_name:
            return v['wuv']
    return 4.20

def predict_matchup(home_team, away_team):
    h_base = get_team_wuv(home_team)
    a_base = get_team_wuv(away_team)

    h_wuv = round(h_base + 0.20, 2)
    a_wuv = round(a_base, 2)
    gap = round(h_wuv - a_wuv, 2)

    pred_winner = home_team if gap >= 0 else away_team
    return pred_winner, abs(gap), h_wuv, a_wuv

# NHL 공식 API 연동
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
    
    # 2026-08월 비시즌 샘플 데이터 전량 삭제
    cursor.execute("DELETE FROM predictions WHERE date LIKE '2026-08%'")
    conn.commit()

    df = pd.read_sql("SELECT * FROM predictions ORDER BY date ASC, id ASC", conn)
    conn.close()
    return df

df = load_data()

# 상단 탭 네비게이션
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
st.title("🏒 NHL AI 승부예측(by 6.0 WUV predictor)")
st.caption("6.0 WUV 기준 (수비/골리 3.0 UV + 공격/유닛 3.0 UV) | NHL 공식 2026-27 시즌 로스터 연동 | 홈 어드밴티지(+0.20 UV)")

# -----------------------------------------------------------------------------
# 🎛️ 시즌 선택 필터 (Season Filter)
# -----------------------------------------------------------------------------
season_col1, season_col2 = st.columns([3, 7])
with season_col1:
    selected_season = st.selectbox(
        "🏆 시즌 선택:",
        ["2026-27 정규시즌 (현재)", "2025-26 정규시즌"],
        index=0
    )

# 시즌 필터링 데이터
if 'season' in df.columns and not df.empty:
    season_key = "2026-27" if "2026-27" in selected_season else "2025-26"
    season_df = df[df['season'] == season_key].copy()
else:
    season_df = df.copy()

# -----------------------------------------------------------------------------
# [통계 산출] 적중률 계산 및 필터링
# -----------------------------------------------------------------------------
season_df['total_no'] = None
valid_mask = season_df['actual_winner'] != 'Postponed' if not season_df.empty else pd.Series()
if not season_df.empty and valid_mask.any():
    season_df.loc[valid_mask, 'total_no'] = range(1, len(season_df[valid_mask]) + 1)
    season_df['total_no'] = season_df['total_no'].fillna('취소')

stats_df = season_df[
    (season_df['actual_winner'] != 'Postponed') & 
    (season_df['actual_winner'].notna()) & 
    (season_df['actual_winner'] != '')
].copy() if not season_df.empty else pd.DataFrame()

# -----------------------------------------------------------------------------
# 1. [상단] 누적 예측 성적표 & 100경기 트래킹
# -----------------------------------------------------------------------------
st.header(f"📊 누적 예측 성적표 ({selected_season})")
total_stats = len(stats_df)
correct_total = stats_df['is_correct'].sum() if total_stats > 0 else 0

col_acc, col_track = st.columns([2, 1])

if total_stats > 0:
    total_acc = (correct_total / total_stats) * 100
    status_suffix = " (⚡ 신계, 시장 왜곡급)" if total_acc >= 60 else ""
    
    with col_acc:
        st.subheader(f"전체 예측률: `{total_acc:.2f}%`{status_suffix}")
        st.markdown(f"**적중 경기 수:** {int(correct_total)} / **통산 경기 수:** {total_stats}")
    
    with col_track:
        remaining = 100 - total_stats
        if remaining > 0:
            st.metric("100경기 시스템 검증까지", f"{remaining}경기 남음")
        else:
            st.metric("시스템 검증 상태", "검증 완료 (신계 등급)")
else:
    with col_acc:
        st.subheader("전체 예측률: `-`")
        st.markdown(f"**적중 경기 수:** 0 / **통산 경기 수:** 0 ({selected_season} 경기 종료 후 실시간 집계)")
    with col_track:
        st.metric("100경기 시스템 검증까지", "100경기 남음")

st.markdown("---")

# -----------------------------------------------------------------------------
# 2. [중단] 일별 예측 성적표 (6단계 등급 및 라벨)
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
    st.info(f"💡 {selected_season} 개막 후 종료되는 경기가 실시간으로 집계됩니다.")

st.markdown("""
<div style="text-align: center; padding: 12px; background-color: #f0f2f6; border-radius: 10px; line-height: 1.6;">
    <span style="color: #A020F0;">●</span> <b>신계</b> (60%↑) &nbsp;&nbsp;
    <span style="color: #FF0000;">●</span> <b>초고수/AI</b> (55%~60%) &nbsp;&nbsp;
    <span style="color: #FFA500;">●</span> <b>프로/고수</b> (52.4%~55%) &nbsp;&nbsp;
    <span style="color: #1E90FF;">●</span> <b>노력하는 일반인</b> (45%~52.4%) &nbsp;&nbsp;
    <span style="color: #008000;">●</span> <b>지극히 정상인</b> (35%~45%) &nbsp;&nbsp;
    <span style="color: #808080;">●</span> <b>예측 금지</b> (35%↓)
    <br><small>* 52.4%는 통계적 손익분기점(Breakeven) 기준입니다.</small>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 3. [하단] 일별 상세 예측 리포트 (실시간 NHL API 연동)
# -----------------------------------------------------------------------------
st.header("📋 일별 상세 예측 리포트")

available_dates = fetch_available_nhl_dates()
default_target_date = datetime.strptime(available_dates[0], "%Y-%m-%d").date()

selected_date = st.date_input("확인하고 싶은 날짜를 선택하세요 (NHL 공식 일정 연동):", value=default_target_date)
selected_date_str = selected_date.strftime("%Y-%m-%d")

# Live NHL API 경기 조회
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
        
        status_str = "⏳ 대기"
        if act_w != '':
            status_str = "✅ 정답" if is_corr == 1 else "❌ 오답"

        report_list.append({
            'No.(Day)': idx,
            'No.(Total)': idx,
            '홈 팀': f"{h_t}({h_uv:.2f})",
            '원정 팀': f"{a_t}({a_uv:.2f})",
            '예측 승리팀': f"{pred_w}({pred_wuv:.2f})",
            '예상 격차(uv)': f"{gap:.2f}",
            '실제 승리팀': act_w if act_w != '' else '⏳ 대기 중',
            '적중 여부': status_str
        })
    
    rep_df = pd.DataFrame(report_list)

    finished_count = len([r for r in report_list if r['실제 승리팀'] != '⏳ 대기 중'])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("해당일 총 경기 수", f"{len(live_games)} 경기")
    col2.metric("종료된 경기", f"{finished_count} 경기")
    col3.metric("일일 적중률", "예측 완료 (대기)" if finished_count == 0 else f"{(sum([1 for r in report_list if r['적중 여부']=='✅ 정답'])/finished_count)*100:.1f}%")

    st.dataframe(rep_df, hide_index=True, use_container_width=True)
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("해당일 총 경기 수", "0 경기")
    col2.metric("종료된 경기", "0 경기")
    col3.metric("일일 적중률", "-")
    st.info(f"⚠️ {selected_date_str} 날짜에는 예정된 NHL 경기가 없습니다. ({selected_season} 개막 예정일: {available_dates[0]}~)")

if st.button("데이터 새로고침"):
    st.rerun()

# -----------------------------------------------------------------------------
# 4. [최하단] 푸터 문구
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
