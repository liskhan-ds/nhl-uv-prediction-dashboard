import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import altair as alt
import plotly.graph_objects as go
import os
import requests
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

# 상단 탭 네비게이션 (NBA, MLB, EPL, NHL 4대 종목)
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

# 메인 타이틀 및 스펙 설명
st.title("🏒 NHL AI 승부예측 (by 6.0 WUV predictor)")
st.caption("6.0 WUV 기준 (골리 1.8 UV + 탑 유닛 2.7 UV + 뎁스 유닛 1.5 UV) | 라인업 (선발 골리 + 1~4라인 F + 1~3페어 D) | 홈 어드밴티지(+0.20 UV)")

# Custom CSS
st.markdown("""
<style>
    .match-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    .team-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .team-box {
        text-align: center;
        width: 42%;
    }
    .team-logo {
        width: 52px;
        height: 52px;
        object-fit: contain;
    }
    .team-name {
        font-weight: 700;
        font-size: 1.05rem;
        margin-top: 4px;
    }
    .uv-score {
        font-size: 1.25rem;
        font-weight: 800;
        color: #2563eb;
    }
    .vs-badge {
        font-size: 0.85rem;
        font-weight: 800;
        color: #64748b;
        background: #f1f5f9;
        padding: 4px 10px;
        border-radius: 20px;
    }
    .goalie-box {
        background-color: #f8fafc;
        border: 1px solid #f1f5f9;
        border-radius: 8px;
        padding: 10px;
        font-size: 0.85rem;
        margin-top: 10px;
    }
    .pick-badge {
        background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
        color: white;
        padding: 8px 14px;
        border-radius: 8px;
        font-weight: 700;
        text-align: center;
        margin-top: 12px;
        font-size: 0.92rem;
    }
    .prob-bar-container {
        display: flex;
        height: 22px;
        border-radius: 11px;
        overflow: hidden;
        margin-top: 10px;
        font-weight: bold;
        font-size: 0.78rem;
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
        font-size: 0.75rem;
        font-weight: bold;
        padding: 2px 8px;
        border-radius: 4px;
        display: inline-block;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. NHL 32개 팀 정적 지표 & 트라이코드 맵핑
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
    "보스턴 브루인스": {
        "eng_name": "Boston Bruins", "tri": "BOS",
        "goalie": {"name": "제러미 스웨이만 (Jeremy Swayman)", "sv_pct": 0.916, "gsax_60": 0.42},
        "top_unit": {"name": "1-2라인 F + 1페어 D (파스트르냐크, 마상, 자하, 맥어보이, 린드홀름)", "xgf_pct": 57.2, "p_60": 2.85},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (코일, 프레더릭, 로라이, 피키)", "cf_pct": 52.4, "xga_60": 2.25}
    },
    "뉴욕 레인저스": {
        "eng_name": "New York Rangers", "tri": "NYR",
        "goalie": {"name": "이고르 시스테르킨 (Igor Shesterkin)", "sv_pct": 0.918, "gsax_60": 0.48},
        "top_unit": {"name": "1-2라인 F + 1페어 D (파나린, 지바네자드, 크라이더, 폭스, 밀러)", "xgf_pct": 56.8, "p_60": 2.90},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (라프레니에르, 트로체크, 슈나이더, 트루바)", "cf_pct": 51.8, "xga_60": 2.30}
    },
    "플로리다 팬서스": {
        "eng_name": "Florida Panthers", "tri": "FLA",
        "goalie": {"name": "세르게이 보브롭스키 (Sergei Bobrovsky)", "sv_pct": 0.915, "gsax_60": 0.38},
        "top_unit": {"name": "1-2라인 F + 1페어 D (바르코브, 카척, 라인하트, 포슬링, 익블라드)", "xgf_pct": 58.5, "p_60": 2.95},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (베라게, 룬델, 미콜라, 쿨리코브)", "cf_pct": 54.2, "xga_60": 2.18}
    },
    "캐롤라이나 허리케인스": {
        "eng_name": "Carolina Hurricanes", "tri": "CAR",
        "goalie": {"name": "프레데리크 안데르센 (Frederik Andersen)", "sv_pct": 0.914, "gsax_60": 0.35},
        "top_unit": {"name": "1-2라인 F + 1페어 D (아호, 스베치니코프, 네차스, 슬래빈, 번스)", "xgf_pct": 59.1, "p_60": 2.78},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (자비스, 스타알, 고티스베헤르, 워커)", "cf_pct": 55.6, "xga_60": 2.10}
    },
    "에드먼턴 오일러스": {
        "eng_name": "Edmonton Oilers", "tri": "EDM",
        "goalie": {"name": "스튜어트 스키너 (Stuart Skinner)", "sv_pct": 0.906, "gsax_60": 0.15},
        "top_unit": {"name": "1-2라인 F + 1페어 D (맥데이비드, 드라이자이트엘, 하이만, 부샤드, 에크홀름)", "xgf_pct": 60.2, "p_60": 3.45},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (뉴전트-홉킨스, 아르비드손, 널스, 엠버슨)", "cf_pct": 53.1, "xga_60": 2.48}
    },
    "달라스 스타스": {
        "eng_name": "Dallas Stars", "tri": "DAL",
        "goalie": {"name": "제이크 오팅거 (Jake Oettinger)", "sv_pct": 0.915, "gsax_60": 0.36},
        "top_unit": {"name": "1-2라인 F + 1페어 D (로버트슨, 힌츠, 세긴, 헤이스카넨, 하리)", "xgf_pct": 56.4, "p_60": 2.75},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (존스턴, 두셰인, 린델, 류부슈킨)", "cf_pct": 53.5, "xga_60": 2.20}
    },
    "콜로라도 애벌랜치": {
        "eng_name": "Colorado Avalanche", "tri": "COL",
        "goalie": {"name": "알렉산다르 게르기예프 (Alexandar Georgiev)", "sv_pct": 0.904, "gsax_60": 0.08},
        "top_unit": {"name": "1-2라인 F + 1페어 D (맥키넌, 란타넨, 마카, 테이브스, 드루앵)", "xgf_pct": 59.4, "p_60": 3.30},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (미텔스타트, 오코너, 지라드, 맨슨)", "cf_pct": 51.5, "xga_60": 2.52}
    },
    "베가스 골든나이츠": {
        "eng_name": "Vegas Golden Knights", "tri": "VGK",
        "goalie": {"name": "아딘 힐 (Adin Hill)", "sv_pct": 0.912, "gsax_60": 0.30},
        "top_unit": {"name": "1-2라인 F + 1페어 D (아이클, 스톤, 혜르틀, 시오도르, 피에트랑젤로)", "xgf_pct": 55.8, "p_60": 2.70},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (바르바셰프, 도로페예프, 해니핀, 맥냅)", "cf_pct": 52.0, "xga_60": 2.28}
    },
    "토론토 메이플리프스": {
        "eng_name": "Toronto Maple Leafs", "tri": "TOR",
        "goalie": {"name": "조셉 월 (Joseph Woll)", "sv_pct": 0.912, "gsax_60": 0.28},
        "top_unit": {"name": "1-2라인 F + 1페어 D (매튜스, 마너, 닐란더, 리엘리, 타네브)", "xgf_pct": 57.5, "p_60": 3.10},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (타바레스, 니스, 맥케이브, 에크만-라르손)", "cf_pct": 51.0, "xga_60": 2.42}
    },
    "탬파베이 라이트닝": {
        "eng_name": "Tampa Bay Lightning", "tri": "TBL",
        "goalie": {"name": "안드레이 바실레프스키 (Andrei Vasilevskiy)", "sv_pct": 0.917, "gsax_60": 0.44},
        "top_unit": {"name": "1-2라인 F + 1페어 D (쿠체로프, 포인트, 겐첼, 헤드만, 맥도나)", "xgf_pct": 56.9, "p_60": 3.05},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (해겔, 시렐리, 체르낙, 펄빅스)", "cf_pct": 50.8, "xga_60": 2.38}
    },
    "위니펙 제츠": {
        "eng_name": "Winnipeg Jets", "tri": "WPG",
        "goalie": {"name": "코너 헬레바이크 (Connor Hellebuyck)", "sv_pct": 0.922, "gsax_60": 0.58},
        "top_unit": {"name": "1-2라인 F + 1페어 D (샤이플리, 코너, 엘러스, 모리시, 디멜로)", "xgf_pct": 54.8, "p_60": 2.65},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (빌라르디, 로우리, 피옹크, 샘버그)", "cf_pct": 51.2, "xga_60": 2.15}
    },
    "밴쿠버 캐넉스": {
        "eng_name": "Vancouver Canucks", "tri": "VAN",
        "goalie": {"name": "대처 뎀코 (Thatcher Demko)", "sv_pct": 0.918, "gsax_60": 0.46},
        "top_unit": {"name": "1-2라인 F + 1페어 D (페테르손, 밀러, 보저, 휴즈, 흐로넥)", "xgf_pct": 56.2, "p_60": 2.88},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (가랜드, 드브러스크, 마이어스, 소시)", "cf_pct": 51.5, "xga_60": 2.32}
    },
    "뉴저지 데빌스": {
        "eng_name": "New Jersey Devils", "tri": "NJD",
        "goalie": {"name": "야코브 마르크스트룀 (Jacob Markstrom)", "sv_pct": 0.913, "gsax_60": 0.32},
        "top_unit": {"name": "1-2라인 F + 1페어 D (휴즈, 히시어, 브라트, 해밀턴, 페시)", "xgf_pct": 57.0, "p_60": 2.80},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (마이어, 머서, 지겐탈러, 루크 휴즈)", "cf_pct": 53.0, "xga_60": 2.30}
    },
    "로스앤젤레스 킹스": {
        "eng_name": "Los Angeles Kings", "tri": "LAK",
        "goalie": {"name": "다르시 켐퍼 (Darcy Kuemper)", "sv_pct": 0.911, "gsax_60": 0.25},
        "top_unit": {"name": "1-2라인 F + 1페어 D (코피타르, 켐페, 피알라, 다우티, 앤더슨)", "xgf_pct": 55.4, "p_60": 2.58},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (바이필드, 다노, 클라크, 에드문드손)", "cf_pct": 53.8, "xga_60": 2.18}
    },
    "내슈빌 프레더터스": {
        "eng_name": "Nashville Predators", "tri": "NSH",
        "goalie": {"name": "유세 사로스 (Juuse Saros)", "sv_pct": 0.915, "gsax_60": 0.36},
        "top_unit": {"name": "1-2라인 F + 1페어 D (포르스베리, 스탐코스, 마체소, 요시, 스케이)", "xgf_pct": 55.9, "p_60": 2.72},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (오라일리, 뉘키스트, 캐리어, 셰인)", "cf_pct": 52.2, "xga_60": 2.26}
    },
    "미네소타 와일드": {
        "eng_name": "Minnesota Wild", "tri": "MIN",
        "goalie": {"name": "필립 구스타프손 (Filip Gustavsson)", "sv_pct": 0.914, "gsax_60": 0.34},
        "top_unit": {"name": "1-2라인 F + 1페어 D (카프리조프, 볼디, 에릭손 에크, 파버, 스퍼전)", "xgf_pct": 55.2, "p_60": 2.78},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (로시, 주카렐로, 브로딘, 보고시안)", "cf_pct": 51.4, "xga_60": 2.28}
    },
    "뉴욕 아일랜더스": {
        "eng_name": "New York Islanders", "tri": "NYI",
        "goalie": {"name": "일리야 소로킨 (Ilya Sorokin)", "sv_pct": 0.916, "gsax_60": 0.40},
        "top_unit": {"name": "1-2라인 F + 1페어 D (바잘, 호밧, 넬슨, 돕슨, 로마노프)", "xgf_pct": 53.8, "p_60": 2.50},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (파미에리, 리, 페렉, 풀록)", "cf_pct": 50.2, "xga_60": 2.34}
    },
    "피츠버그 펭귄스": {
        "eng_name": "Pittsburgh Penguins", "tri": "PIT",
        "goalie": {"name": "트리스탄 자레이 (Tristan Jarry)", "sv_pct": 0.908, "gsax_60": 0.18},
        "top_unit": {"name": "1-2라인 F + 1페어 D (크로스비, 말킨, 러스트, 레탕, 칼손)", "xgf_pct": 54.5, "p_60": 2.68},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (라켈, 번팅, 페테르손, 그레이브스)", "cf_pct": 49.8, "xga_60": 2.55}
    },
    "워싱턴 캐피털스": {
        "eng_name": "Washington Capitals", "tri": "WSH",
        "goalie": {"name": "찰리 린드그렌 (Charlie Lindgren)", "sv_pct": 0.911, "gsax_60": 0.24},
        "top_unit": {"name": "1-2라인 F + 1페어 D (오베치킨, 스트롬, 뒤부아, 칼슨, 치크런)", "xgf_pct": 53.5, "p_60": 2.60},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (윌슨, 만지아파네, 로이, 페헤르바리)", "cf_pct": 49.5, "xga_60": 2.45}
    },
    "필라델피아 플라이어스": {
        "eng_name": "Philadelphia Flyers", "tri": "PHI",
        "goalie": {"name": "사무엘 에르손 (Samuel Ersson)", "sv_pct": 0.904, "gsax_60": 0.10},
        "top_unit": {"name": "1-2라인 F + 1페어 D (미치코프, 코네크니, 쿠투리에, 산하임, 드라이스데일)", "xgf_pct": 52.8, "p_60": 2.45},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (티펫, 파라비, 시엘러, 리스토라이넨)", "cf_pct": 50.8, "xga_60": 2.50}
    },
    "디트로이트 레드윙스": {
        "eng_name": "Detroit Red Wings", "tri": "DET",
        "goalie": {"name": "캄 탈봇 (Cam Talbot)", "sv_pct": 0.912, "gsax_60": 0.26},
        "top_unit": {"name": "1-2라인 F + 1페어 D (라킨, 레이몬드, 데브린캣, 자이더, 에드빈손)", "xgf_pct": 53.2, "p_60": 2.62},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (케인, 타라센코, 샤롯, 페트리)", "cf_pct": 49.0, "xga_60": 2.52}
    },
    "버팔로 세이버스": {
        "eng_name": "Buffalo Sabres", "tri": "BUF",
        "goalie": {"name": "우코-페카 루코넨 (Ukko-Pekka Luukkonen)", "sv_pct": 0.910, "gsax_60": 0.22},
        "top_unit": {"name": "1-2라인 F + 1페어 D (톰슨, 터콧, 다클린, 바이람, 코젠스)", "xgf_pct": 53.0, "p_60": 2.55},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (주커, 페테르카, 요키하류, 클리프턴)", "cf_pct": 49.2, "xga_60": 2.48}
    },
    "오타와 세네터스": {
        "eng_name": "Ottawa Senators", "tri": "OTT",
        "goalie": {"name": "리누스 울마르크 (Linus Ullmark)", "sv_pct": 0.915, "gsax_60": 0.35},
        "top_unit": {"name": "1-2라인 F + 1페어 D (트카척, 슈튀츨레, 지루, 샌더슨, 샤보)", "xgf_pct": 54.0, "p_60": 2.65},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (바더슨, 핀토, 조브, 젠센)", "cf_pct": 50.4, "xga_60": 2.44}
    },
    "몬트리올 카나디엔스": {
        "eng_name": "Montreal Canadiens", "tri": "MTL",
        "goalie": {"name": "샘 몽템보 (Sam Montembeault)", "sv_pct": 0.907, "gsax_60": 0.16},
        "top_unit": {"name": "1-2라인 F + 1페어 D (수즈키, 코필드, 슬라프코프스키, 매더슨, 구흘리)", "xgf_pct": 51.5, "p_60": 2.42},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (라이네, 뉴훅, 허슨, 사바르)", "cf_pct": 48.6, "xga_60": 2.60}
    },
    "캘거리 플레임스": {
        "eng_name": "Calgary Flames", "tri": "CGY",
        "goalie": {"name": "다스틴 울프 (Dustin Wolf)", "sv_pct": 0.909, "gsax_60": 0.20},
        "top_unit": {"name": "1-2라인 F + 1페어 D (카드리, 위베르도, 샤랑고비치, 안드르손, 위거)", "xgf_pct": 51.8, "p_60": 2.38},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (포스피실, 쿠즈멘코, 파샬, 빈)", "cf_pct": 49.0, "xga_60": 2.46}
    },
    "시애틀 크라켄": {
        "eng_name": "Seattle Kraken", "tri": "SEA",
        "goalie": {"name": "조이 다코드 (Joey Daccord)", "sv_pct": 0.912, "gsax_60": 0.26},
        "top_unit": {"name": "1-2라인 F + 1페어 D (맥캔, 베니어스, 스티븐슨, 던, 라르손)", "xgf_pct": 52.4, "p_60": 2.40},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (톨바넨, 타네브, 올레시아크, 몬투어)", "cf_pct": 50.5, "xga_60": 2.35}
    },
    "세인트루이스 블루스": {
        "eng_name": "St. Louis Blues", "tri": "STL",
        "goalie": {"name": "조던 비닝턴 (Jordan Binnington)", "sv_pct": 0.911, "gsax_60": 0.24},
        "top_unit": {"name": "1-2라인 F + 1페어 D (토머스, 카이루, 부츠네비치, 파라이코, 브로베르크)", "xgf_pct": 52.0, "p_60": 2.48},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (사드, 홀로웨이, 르디, 포크)", "cf_pct": 48.8, "xga_60": 2.45}
    },
    "유타 하키클럽": {
        "eng_name": "Utah Hockey Club", "tri": "UTA",
        "goalie": {"name": "코너 인그램 (Connor Ingram)", "sv_pct": 0.909, "gsax_60": 0.18},
        "top_unit": {"name": "1-2라인 F + 1페어 D (켈러, 쿨리, 건더, 세르가체프, 두르지)", "xgf_pct": 52.6, "p_60": 2.50},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (마르첼리, 슈말츠, 발리마키, 콜)", "cf_pct": 49.4, "xga_60": 2.48}
    },
    "시카고 블랙호크스": {
        "eng_name": "Chicago Blackhawks", "tri": "CHI",
        "goalie": {"name": "페트르 음라제크 (Petr Mrazek)", "sv_pct": 0.905, "gsax_60": 0.12},
        "top_unit": {"name": "1-2라인 F + 1페어 D (베다드, 테라바이넨, 버투지, 블라식, 존스)", "xgf_pct": 50.8, "p_60": 2.35},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (폴리뇨, 쿠라셰프, 코친스키, 마르티네즈)", "cf_pct": 47.8, "xga_60": 2.62}
    },
    "애너하임 덕스": {
        "eng_name": "Anaheim Ducks", "tri": "ANA",
        "goalie": {"name": "루카스 도스탈 (Lukas Dostal)", "sv_pct": 0.908, "gsax_60": 0.15},
        "top_unit": {"name": "1-2라인 F + 1페어 D (제그라스, 맥태비시, 칼슨, 민튜코프, 파울러)", "xgf_pct": 49.8, "p_60": 2.30},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (바트라노, 테리, 구다스, 젤웨거)", "cf_pct": 47.2, "xga_60": 2.65}
    },
    "산호세 샤크스": {
        "eng_name": "San Jose Sharks", "tri": "SJS",
        "goalie": {"name": "맥켄지 블랙우드 (Mackenzie Blackwood)", "sv_pct": 0.903, "gsax_60": 0.05},
        "top_unit": {"name": "1-2라인 F + 1페어 D (세레브리니, 스미스, 그란룬드, 루타, 시시)", "xgf_pct": 48.5, "p_60": 2.20},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (토폴리, 제테를룬드, 월먼, 페라로)", "cf_pct": 46.0, "xga_60": 2.75}
    },
    "콜럼버스 블루재키츠": {
        "eng_name": "Columbus Blue Jackets", "tri": "CBJ",
        "goalie": {"name": "엘비스 메르즐리킨스 (Elvis Merzlikins)", "sv_pct": 0.902, "gsax_60": 0.04},
        "top_unit": {"name": "1-2라인 F + 1페어 D (팡틸리, 제너, 존슨, 웨렌스키, 세버슨)", "xgf_pct": 49.2, "p_60": 2.25},
        "depth_unit": {"name": "3-4라인 F + 2-3페어 D (마르첸코, 실린저, 프로보로프, 구드브랜슨)", "cf_pct": 46.8, "xga_60": 2.68}
    }
}

# 팀 UV 계산 함수 (6.0 WUV 스케일)
def calculate_team_wuv(team_name):
    if team_name not in TEAMS_DATA:
        g_uv = 1.35
        t_uv = 2.05
        d_uv = 1.10
        team_info = {
            "eng_name": team_name, "tri": "NHL",
            "goalie": {"name": f"{team_name} 주전 골리", "sv_pct": 0.910, "gsax_60": 0.20},
            "top_unit": {"name": "1-2라인 F + 1페어 D", "xgf_pct": 52.0, "p_60": 2.50},
            "depth_unit": {"name": "3-4라인 F + 2-3페어 D", "cf_pct": 50.0, "xga_60": 2.40}
        }
    else:
        team_info = TEAMS_DATA[team_name]
        g = team_info["goalie"]
        t = team_info["top_unit"]
        d = team_info["depth_unit"]

        # 1. 골리 UV (Max 1.8 UV, 가중치 30%)
        g_norm = 0.5 * ((g["sv_pct"] - 0.890) / 0.035) + 0.5 * (g["gsax_60"] / 0.60)
        g_norm = max(0.1, min(1.0, g_norm))
        g_uv = round(1.8 * g_norm, 2)

        # 2. 탑 유닛 UV (Max 2.7 UV, 가중치 45%)
        t_norm = 0.5 * ((t["xgf_pct"] - 48.0) / 12.0) + 0.5 * ((t["p_60"] - 2.0) / 1.5)
        t_norm = max(0.1, min(1.0, t_norm))
        t_uv = round(2.7 * t_norm, 2)

        # 3. 뎁스 유닛 UV (Max 1.5 UV, 가중치 25%)
        d_norm = 0.5 * ((d["cf_pct"] - 45.0) / 10.0) + 0.5 * ((2.80 - d["xga_60"]) / 0.80)
        d_norm = max(0.1, min(1.0, d_norm))
        d_uv = round(1.5 * d_norm, 2)

    total_wuv = round(g_uv + t_uv + d_uv, 2)
    return {
        "team_name": team_name,
        "eng_name": team_info["eng_name"],
        "tri": team_info["tri"],
        "goalie_uv": g_uv,
        "top_unit_uv": t_uv,
        "depth_unit_uv": d_uv,
        "total_wuv": total_wuv,
        "goalie": team_info["goalie"],
        "top_unit": team_info["top_unit"],
        "depth_unit": team_info["depth_unit"]
    }

# 로지스틱 함수 기반 2-Way 승리 확률 및 예측 스코어 산출
def predict_matchup(home_team, away_team):
    h_info = calculate_team_wuv(home_team)
    a_info = calculate_team_wuv(away_team)

    # 홈 어드밴티지 +0.20 UV 적용
    home_eff_wuv = round(h_info["total_wuv"] + 0.20, 2)
    away_eff_wuv = a_info["total_wuv"]

    uv_diff = home_eff_wuv - away_eff_wuv

    # 2-Way 로지스틱 확률 계산
    k = 1.35
    prob_home = 1.0 / (1.0 + np.exp(-k * uv_diff))
    prob_away = 1.0 - prob_home

    home_win_pct = round(prob_home * 100, 1)
    away_win_pct = round(prob_away * 100, 1)

    # 예상 스코어 계산
    base_goals = 3.1
    home_exp_g = max(1, int(round(base_goals + 0.85 * uv_diff)))
    away_exp_g = max(1, int(round(base_goals - 0.85 * uv_diff)))
    if home_exp_g == away_exp_g:
        if uv_diff > 0: home_exp_g += 1
        else: away_exp_g += 1

    # AI 추천 픽 결정
    if home_win_pct >= 53.0:
        predicted_winner = home_team
        recommendation = f"🏒 [홈 승 추천] {home_team}"
    elif away_win_pct >= 53.0:
        predicted_winner = away_team
        recommendation = f"🏒 [원정 승 추천] {away_team}"
    else:
        if home_win_pct >= away_win_pct:
            predicted_winner = home_team
            recommendation = f"⚖️ [미세 우세] {home_team}"
        else:
            predicted_winner = away_team
            recommendation = f"⚖️ [미세 우세] {away_team}"

    return {
        "home_info": h_info,
        "away_info": a_info,
        "home_eff_wuv": home_eff_wuv,
        "away_eff_wuv": away_eff_wuv,
        "uv_diff": round(uv_diff, 2),
        "home_win_pct": home_win_pct,
        "away_win_pct": away_win_pct,
        "home_exp_g": home_exp_g,
        "away_exp_g": away_exp_g,
        "predicted_winner": predicted_winner,
        "recommendation": recommendation
    }

# -----------------------------------------------------------------------------
# 3. Live NHL API 실시간 일정 조회 & 데이터베이스 관리 (순수 실시간 DB)
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
    df = pd.read_sql("SELECT * FROM predictions ORDER BY date ASC, id ASC", conn)
    conn.close()
    return df

df = load_data()

# -----------------------------------------------------------------------------
# 4. [상단] 누적 예측 성적표 & 100경기 트래킹
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
        st.subheader("전체 예측률: `-`")
        st.markdown("**적중 경기 수:** 0 / **통산 경기 수:** 0 (시즌 개막 후 경기 종료 시 자동 집계)")
    with col_track:
        st.metric("100경기 시스템 검증까지", "100경기 남음")

st.markdown("---")

# -----------------------------------------------------------------------------
# 5. [중단] 일별 예측 성적표 (6단계 등급 바 차트 및 2-Way 벤치마크)
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
    st.info("💡 8월은 NHL 공식 비시즌(휴식기)입니다. 9월 말 시범경기 및 정규시즌 개막 후 종료된 경기가 실시간으로 집계됩니다.")

# 2-Way 벤치마크 문구
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
# 6. [메인] 당일 NHL 전 경기 매치업 카드 그리드 (Live API + Database)
# -----------------------------------------------------------------------------
st.header("🏒 NHL 공식 일정 AI 승부예측 카드")

available_nhl_dates = fetch_available_nhl_dates()
default_target_date = datetime.strptime(available_nhl_dates[0], "%Y-%m-%d").date()

selected_date = st.date_input("🗓️ 확인하고 싶은 경기 날짜를 선택하세요 (NHL 개막 일정 자동 연동):", value=default_target_date)
selected_date_str = selected_date.strftime("%Y-%m-%d")

# Live API 조회
live_games = fetch_live_nhl_schedule(selected_date_str)

if live_games:
    st.markdown(f"<span class='live-badge'>📡 NHL Official API 실시간 일정 연동 중 ({selected_date_str} / {len(live_games)} 경기)</span>", unsafe_allow_html=True)
    display_matchups = [(g['home_team'], g['away_team']) for g in live_games]
else:
    display_matchups = []

if not display_matchups:
    st.warning(f"⚠️ {selected_date_str} 날짜에는 예정된 NHL 경기가 없습니다. 상단 일자 선택기에서 NHL 일정({available_nhl_dates[0]} 등)을 선택해 주세요.")
else:
    grid_cols = st.columns(2)
    
    for idx, (home_team, away_team) in enumerate(display_matchups):
        col_target = grid_cols[idx % 2]
        
        pred = predict_matchup(home_team, away_team)
        h_info = pred['home_info']
        a_info = pred['away_info']
        
        h_logo = f"https://assets.nhle.com/logos/nhl/svg/{h_info['tri']}_light.svg"
        a_logo = f"https://assets.nhle.com/logos/nhl/svg/{a_info['tri']}_light.svg"
        
        with col_target:
            st.markdown(f"""
            <div class="match-card">
                <div class="team-header">
                    <div class="team-box">
                        <img src="{a_logo}" class="team-logo" alt="{away_team}">
                        <div class="team-name">{away_team}</div>
                        <div style="font-size:0.78rem; color:#64748b;">(원정)</div>
                        <div class="uv-score">{a_info['total_wuv']:.2f} WUV</div>
                    </div>
                    <div style="text-align:center;">
                        <span class="vs-badge">VS</span>
                        <div style="font-size:0.75rem; color:#64748b; margin-top:6px;">홈어드디 +0.20</div>
                    </div>
                    <div class="team-box">
                        <img src="{h_logo}" class="team-logo" alt="{home_team}">
                        <div class="team-name">{home_team}</div>
                        <div style="font-size:0.78rem; color:#64748b;">(홈)</div>
                        <div class="uv-score">{pred['home_eff_wuv']:.2f} WUV</div>
                    </div>
                </div>
                
                <div class="goalie-box">
                    <div style="font-weight:bold; margin-bottom:4px; text-align:center;">🥅 선발 골리 매치업 (골리 1.8 UV 스케일)</div>
                    <div style="display:flex; justify-content:space-between;">
                        <div><b>원정:</b> {a_info['goalie']['name']} <br>SV%: {a_info['goalie']['sv_pct']:.3f} | GSAx/60: +{a_info['goalie']['gsax_60']:.2f} | <b>UV: {a_info['goalie_uv']:.2f}</b></div>
                        <div style="text-align:right;"><b>홈:</b> {h_info['goalie']['name']} <br>SV%: {h_info['goalie']['sv_pct']:.3f} | GSAx/60: +{h_info['goalie']['gsax_60']:.2f} | <b>UV: {h_info['goalie_uv']:.2f}</b></div>
                    </div>
                </div>

                <div style="margin-top:10px; font-size:0.82rem;">
                    <div style="display:flex; justify-content:space-between;">
                        <span>🔥 탑 유닛 (2.7 UV): 원정 {a_info['top_unit_uv']:.2f} vs 홈 {h_info['top_unit_uv']:.2f}</span>
                        <span>🛡️ 뎁스 유닛 (1.5 UV): 원정 {a_info['depth_unit_uv']:.2f} vs 홈 {h_info['depth_unit_uv']:.2f}</span>
                    </div>
                </div>

                <div class="prob-bar-container">
                    <div class="prob-away" style="width: {pred['away_win_pct']}%;">원정 승 {pred['away_win_pct']}%</div>
                    <div class="prob-home" style="width: {pred['home_win_pct']}%;">홈 승 {pred['home_win_pct']}%</div>
                </div>

                <div class="pick-badge">
                    🎯 {pred['recommendation']} &nbsp;|&nbsp; 예상 스코어 ({away_team} {pred['away_exp_g']} : {pred['home_exp_g']} {home_team})
                </div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("---")

# -----------------------------------------------------------------------------
# 7. [하단] 상세 라인업 분석기 및 공수 밸런스 차트
# -----------------------------------------------------------------------------
st.header("📋 상세 경기 라인업 분석기 & 6.0 WUV 차트")

if display_matchups:
    game_options = [f"{a} vs {h}" for h, a in display_matchups]
    selected_game_str = st.selectbox("분석할 경기를 선택하세요:", options=game_options)
    
    away_sel_name, home_sel_name = selected_game_str.split(" vs ")
    pred_detail = predict_matchup(home_sel_name, away_sel_name)
    h_detail = pred_detail['home_info']
    a_detail = pred_detail['away_info']

    tab1, tab2 = st.tabs(["🔍 유닛별 상세 UV 비교 테이블", "📊 공수 & 유닛 밸런스 레이더 차트"])

    with tab1:
        st.subheader(f"🏒 {away_sel_name} vs {home_sel_name} 세부 UV 구성 요소")
        
        table_data = [
            {
                "구분 (Unit Component)": "🥅 주전 골리 (Goalie Unit - Max 1.8 UV)",
                f"원정: {away_sel_name}": f"{a_detail['goalie']['name']} (SV%: {a_detail['goalie']['sv_pct']:.3f}, GSAx/60: +{a_detail['goalie']['gsax_60']:.2f})",
                "원정 UV": a_detail['goalie_uv'],
                f"홈: {home_sel_name}": f"{h_detail['goalie']['name']} (SV%: {h_detail['goalie']['sv_pct']:.3f}, GSAx/60: +{h_detail['goalie']['gsax_60']:.2f})",
                "홈 UV": h_detail['goalie_uv'],
                "격차 (홈 - 원정)": f"{h_detail['goalie_uv'] - a_detail['goalie_uv']:+.2f}"
            },
            {
                "구분 (Unit Component)": "🔥 탑 유닛 (Top Unit: 1-2F + 1D - Max 2.7 UV)",
                f"원정: {away_sel_name}": f"xGF%: {a_detail['top_unit']['xgf_pct']}% | P/60: {a_detail['top_unit']['p_60']}",
                "원정 UV": a_detail['top_unit_uv'],
                f"홈: {home_sel_name}": f"xGF%: {h_detail['top_unit']['xgf_pct']}% | P/60: {h_detail['top_unit']['p_60']}",
                "홈 UV": h_detail['top_unit_uv'],
                "격차 (홈 - 원정)": f"{h_detail['top_unit_uv'] - a_detail['top_unit_uv']:+.2f}"
            },
            {
                "구분 (Unit Component)": "🛡️ 뎁스 유닛 (Depth Unit: 3-4F + 2-3D - Max 1.5 UV)",
                f"원정: {away_sel_name}": f"CF%: {a_detail['depth_unit']['cf_pct']}% | xGA/60: {a_detail['depth_unit']['xga_60']}",
                "원정 UV": a_detail['depth_unit_uv'],
                f"홈: {home_sel_name}": f"CF%: {h_detail['depth_unit']['cf_pct']}% | xGA/60: {h_detail['depth_unit']['xga_60']}",
                "홈 UV": h_detail['depth_unit_uv'],
                "격차 (홈 - 원정)": f"{h_detail['depth_unit_uv'] - a_detail['depth_unit_uv']:+.2f}"
            },
            {
                "구분 (Unit Component)": "🏠 홈 어드밴티지 보정 (Home Advantage)",
                f"원정: {away_sel_name}": "-",
                "원정 UV": 0.00,
                f"홈: {home_sel_name}": "빙상 홈 링크 득점/수비 어드밴티지",
                "홈 UV": 0.20,
                "격차 (홈 - 원정)": "+0.20"
            },
            {
                "구분 (Unit Component)": "🏆 최종 6.0 WUV 합계 (Total WUV)",
                f"원정: {away_sel_name}": f"{away_sel_name} 총 전력",
                "원정 UV": a_detail['total_wuv'],
                f"홈: {home_sel_name}": f"{home_sel_name} 보정 후 총 전력",
                "홈 UV": pred_detail['home_eff_wuv'],
                "격차 (홈 - 원정)": f"{pred_detail['uv_diff']:+.2f}"
            }
        ]
        
        detail_df = pd.DataFrame(table_data)
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

    with tab2:
        st.subheader(f"📊 {away_sel_name} vs {home_sel_name} 5개 항목 밸런스 분석")
        
        categories = ['골리 능력', '탑 유닛 공격', '탑 유닛 수비', '뎁스 수비 억제', '전체 6.0 WUV']
        
        fig = go.Figure()

        fig.add_trace(go.Scatterpolar(
            r=[
                a_detail['goalie_uv'], 
                a_detail['top_unit_uv'] * 0.5, 
                a_detail['top_unit_uv'] * 0.5, 
                a_detail['depth_unit_uv'], 
                a_detail['total_wuv']
            ],
            theta=categories,
            fill='toself',
            name=away_sel_name,
            line_color='#3b82f6'
        ))

        fig.add_trace(go.Scatterpolar(
            r=[
                h_detail['goalie_uv'], 
                h_detail['top_unit_uv'] * 0.5, 
                h_detail['top_unit_uv'] * 0.5, 
                h_detail['depth_unit_uv'], 
                pred_detail['home_eff_wuv']
            ],
            theta=categories,
            fill='toself',
            name=f"{home_sel_name} (홈)",
            line_color='#ef4444'
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 6.0]
                )
            ),
            showlegend=True,
            height=480
        )

        st.plotly_chart(fig, use_container_width=True)
