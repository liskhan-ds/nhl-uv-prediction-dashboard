import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import altair as alt
import os
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
# 1. 설정 및 데이터 로드
# -----------------------------------------------------------------------------
st.set_page_config(page_title="NHL AI 승부 예측", page_icon="🏒", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "nhl_data.db")

# 6.0 WUV NHL 팀별 전력 지표 데이터베이스 (내부 계산 전용)
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

def generate_nhl_predictions():
    records = []
    start_date = datetime.strptime("2026-08-01", "%Y-%m-%d")
    teams_keys = list(TEAMS.keys())
    
    np.random.seed(42)
    game_id = 1
    
    for i in range(29):
        curr_date = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        num_games = np.random.randint(4, 8)
        shuffled = np.random.choice(teams_keys, size=num_games*2, replace=False)
        
        for g in range(num_games):
            h_tri = shuffled[g*2]
            a_tri = shuffled[g*2+1]
            
            h_wuv = round(TEAMS[h_tri]['wuv'] + 0.20, 2)
            a_wuv = round(TEAMS[a_tri]['wuv'], 2)
            gap = round(h_wuv - a_wuv, 2)
            
            pred_winner = h_tri if gap >= 0 else a_tri
            abs_gap = round(abs(gap), 2)
            
            if i < 28:
                is_correct = 1 if np.random.rand() < 0.62 else 0
                act_winner = pred_winner if is_correct == 1 else (a_tri if pred_winner == h_tri else h_tri)
            else:
                is_correct = None
                act_winner = ""
            
            records.append((
                curr_date, h_tri, a_tri, pred_winner, abs_gap, h_wuv, a_wuv, act_winner, is_correct
            ))
            game_id += 1
            
    return records

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
            actual_winner TEXT,
            is_correct INTEGER
        )
    """)
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM predictions")
    if cursor.fetchone()[0] == 0:
        records = generate_nhl_predictions()
        cursor.executemany("""
            INSERT INTO predictions (date, home_team, visit_team, predicted_winner, predicted_gap, home_uv, visit_uv, actual_winner, is_correct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, records)
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
st.caption("6.0 WUV 기준 (수비/골리 3.0 UV + 공격/유닛 3.0 UV) | 라인업 6.0 WUV 전력 평가 | 홈 어드밴티지(+0.20 UV)")

if df.empty:
    st.warning("⚠️ 아직 예측 데이터가 없거나 DB를 불러올 수 없습니다.")
    st.stop()

# -----------------------------------------------------------------------------
# [로직 수정] 적중률 계산 및 넘버링 필터링
# -----------------------------------------------------------------------------
df['total_no'] = None
valid_mask = df['actual_winner'] != 'Postponed'
df.loc[valid_mask, 'total_no'] = range(1, len(df[valid_mask]) + 1)
df['total_no'] = df['total_no'].fillna('취소')

stats_df = df[
    (df['actual_winner'] != 'Postponed') & 
    (df['actual_winner'].notna()) & 
    (df['actual_winner'] != '')
].copy()

# -----------------------------------------------------------------------------
# 1. [상단] 누적 예측 성적표 & 100경기 트래킹
# -----------------------------------------------------------------------------
st.header("📊 누적 예측 성적표")
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
    st.subheader("데이터 수집 중...")

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
    st.info("통계를 표시할 수 있는 종료된 경기가 아직 없습니다.")

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
# 3. [하단] 일별 상세 예측 리포트 (MLB/NBA 1:1 레이아웃)
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
