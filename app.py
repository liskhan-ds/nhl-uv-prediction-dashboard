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

# Custom CSS (내부 스탯 노출 제거, 깔끔한 카드 스타일링)
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
        font-size: 0.9rem;
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
# 2. NHL 32개 팀 데이터 및 6.0 WUV 계산 엔진 (내부 스탯은 비공개 산출)
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
# 3. 데이터베이스 로드 및 히스토리 관리
# -----------------------------------------------------------------------------
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

    # 샘플 데이터 초기화 (2026-08-26 전후 시즌 샘플 데이터 연동)
    cursor.execute("SELECT COUNT(*) FROM predictions")
    if cursor.fetchone()[0] == 0:
        sample_records = [
            ("2026-08-26", "보스턴 브루인스", "뉴욕 레인저스", "보스턴 브루인스", 0.12, 4.74, 4.62, 54.1, 45.9, "3 : 2", "보스턴 브루인스", "3 : 2", 1),
            ("2026-08-26", "플로리다 팬서스", "캐롤라이나 허리케인스", "플로리다 팬서스", 0.25, 4.90, 4.65, 58.4, 41.6, "4 : 2", "플로리다 팬서스", "4 : 1", 1),
            ("2026-08-26", "에드먼턴 오일러스", "달라스 스타스", "에드먼턴 오일러스", 0.40, 4.98, 4.58, 63.2, 36.8, "4 : 2", "에드먼턴 오일러스", "5 : 3", 1),
            ("2026-08-26", "토론토 메이플리프스", "탬파베이 라이트닝", "토론토 메이플리프스", 0.16, 4.80, 4.64, 55.4, 44.6, "3 : 2", "토론토 메이플리프스", "4 : 2", 1),
            ("2026-08-26", "베가스 골든나이츠", "콜로라도 애벌랜치", "콜로라도 애벌랜치", -0.04, 4.72, 4.68, 48.6, 51.4, "2 : 3", "콜로라도 애벌랜치", "1 : 3", 1),
            ("2026-08-26", "위니펙 제츠", "밴쿠버 캐넉스", "위니펙 제츠", 0.21, 4.76, 4.55, 57.1, 42.9, "3 : 2", "위니펙 제츠", "3 : 1", 1),

            ("2026-08-27", "뉴저지 데빌스", "로스앤젤레스 킹스", "뉴저지 데빌스", 0.22, 4.68, 4.46, 57.4, 42.6, "3 : 2", "로스앤젤레스 킹스", "2 : 4", 0),
            ("2026-08-27", "내슈빌 프레더터스", "미네소타 와일드", "내슈빌 프레더터스", 0.23, 4.65, 4.42, 57.7, 42.3, "3 : 2", "내슈빌 프레더터스", "4 : 2", 1),
            ("2026-08-27", "뉴욕 아일랜더스", "피츠버그 펭귄스", "뉴욕 아일랜더스", 0.23, 4.58, 4.35, 57.7, 42.3, "3 : 2", "피츠버그 펭귄스", "1 : 3", 0),
            ("2026-08-27", "워싱턴 캐피털스", "필라델피아 플라이어스", "워싱턴 캐피털스", 0.27, 4.52, 4.25, 59.0, 41.0, "4 : 2", "필라델피아 플라이어스", "2 : 3", 0),
            ("2026-08-27", "디트로이트 레드윙스", "버팔로 세이버스", "디트로이트 레드윙스", 0.24, 4.48, 4.24, 58.1, 41.9, "3 : 2", "디트로이트 레드윙스", "3 : 1", 1),

            ("2026-08-28", "오타와 세네터스", "몬트리올 카나디엔스", "오타와 세네터스", 0.35, 4.50, 4.15, 61.7, 38.3, "4 : 2", "몬트리올 카나디엔스", "2 : 4", 0),
            ("2026-08-28", "캘거리 플레임스", "시애틀 크라켄", "캘거리 플레임스", 0.18, 4.40, 4.22, 56.1, 43.9, "3 : 2", "시애틀 크라켄", "1 : 3", 0),
            ("2026-08-28", "세인트루이스 블루스", "유타 하키클럽", "세인트루이스 블루스", 0.23, 4.41, 4.18, 57.7, 42.3, "3 : 2", "세인트루이스 블루스", "4 : 2", 1),

            ("2026-08-29", "보스턴 브루인스", "뉴욕 레인저스", "보스턴 브루인스", 0.12, 4.74, 4.62, 54.1, 45.9, "3 : 2", "보스턴 브루인스", "3 : 2", 1),
            ("2026-08-29", "플로리다 팬서스", "캐롤라이나 허리케인스", "플로리다 팬서스", 0.25, 4.90, 4.65, 58.4, 41.6, "4 : 2", "플로리다 팬서스", "4 : 1", 1),
            ("2026-08-29", "에드먼턴 오일러스", "달라스 스타스", "에드먼턴 오일러스", 0.40, 4.98, 4.58, 63.2, 36.8, "4 : 2", "에드먼턴 오일러스", "5 : 2", 1)
        ]
        cursor.executemany("""
            INSERT INTO predictions (date, home_team, visit_team, predicted_winner, predicted_gap, home_uv, visit_uv, home_prob, visit_prob, predicted_score, actual_winner, actual_score, is_correct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_records)
        conn.commit()

    df = pd.read_sql("SELECT * FROM predictions ORDER BY date ASC, id ASC", conn)
    conn.close()
    return df

df = load_data()

# -----------------------------------------------------------------------------
# 1. [상단] 누적 예측 성적표 & 100경기 트래킹
# -----------------------------------------------------------------------------
df['total_no'] = None
valid_mask = df['actual_winner'] != 'Postponed'
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
        st.subheader(f"전체 예측 대상 경기: `{len(df)} 경기`")
        st.markdown("**예측 완료 경기:** 0 경기 (경기 종료 후 실시간 적중률 집계)")
    with col_track:
        st.metric("시스템 상태", "실시간 예측 진행 중")

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
    st.info("💡 예정 경기 예측 완료! (경기가 종료되는 대로 실시간 적중률이 집계됩니다.)")

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
# 3. [하단] 일별 상세 예측 리포트 (MLB/NBA 1:1 레이아웃 복사)
# -----------------------------------------------------------------------------
st.header("📋 일별 상세 예측 리포트")

df['date_dt'] = pd.to_datetime(df['date']).dt.date
unique_dates = sorted(df['date_dt'].unique(), reverse=True)

default_date_target = datetime.strptime("2026-08-29", "%Y-%m-%d").date()
default_val = default_date_target if default_date_target in unique_dates else unique_dates[0]

selected_date = st.date_input("확인하고 싶은 날짜를 선택하세요:", value=default_val)
filtered_df = df[df['date_dt'] == selected_date].copy().reset_index(drop=True)

if not filtered_df.empty:
    filtered_df['day_no'] = None
    day_valid_mask = filtered_df['actual_winner'] != 'Postponed'
    filtered_df.loc[day_valid_mask, 'day_no'] = range(1, len(filtered_df[day_valid_mask]) + 1)
    filtered_df['day_no'] = filtered_df['day_no'].fillna('취소')

    day_stats_mask = (filtered_df['actual_winner'] != 'Postponed') & (filtered_df['actual_winner'].notna()) & (filtered_df['actual_winner'] != '')
    finished_games = filtered_df[day_stats_mask]
    finished_count = len(finished_games)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("해당일 총 경기 수", f"{len(filtered_df)} 경기")
    col2.metric("종료된 경기", f"{finished_count} 경기")
    if finished_count > 0:
        acc = (finished_games['is_correct'].sum() / finished_count) * 100
        col3.metric("일일 적중률", f"{acc:.1f}%")
    else:
        col3.metric("일일 적중률", "예측 완료 (대기)")

    display_df = filtered_df[[
        'day_no', 'total_no', 'home_team', 'visit_team', 
        'predicted_winner', 'predicted_gap', 'actual_winner', 'is_correct'
    ]].copy()
    
    display_df.columns = [
        'No.(Day)', 'No.(Total)', '홈 팀', '원정 팀', 
        '예측 승리팀', '예상 격차(uv)', '실제 승리팀', '적중 여부'
    ]
    
    def mark_ox(row):
        if row['실제 승리팀'] == 'Postponed': return "🆖 취소"
        if pd.isna(row['적중 여부']) or row['실제 승리팀'] == '': return "⏳ 대기"
        return "✅ 정답" if row['적중 여부'] == 1 else "❌ 오답"
    
    display_df['적중 여부'] = display_df.apply(mark_ox, axis=1)
    display_df['예상 격차(uv)'] = display_df['예상 격차(uv)'].apply(lambda x: f"{x:.2f}")
    display_df['실제 승리팀'] = display_df['실제 승리팀'].replace('Postponed', '취소됨').fillna('⏳ 대기 중')

    st.dataframe(display_df, hide_index=True, use_container_width=True)

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
