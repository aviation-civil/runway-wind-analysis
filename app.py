import streamlit as st
import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import plotly.express as px  # <-- 에러 해결을 위해 추가된 핵심 라인!
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

# 1. 페이지 설정
st.set_page_config(page_title="활주로 분석기 V2.9 (최종 수정)", layout="wide")
st.title("✈️ 활주로 이용률 정밀 분석 (시각화 에러 수정 버전)")

# --- [내장 데이터] 기상청 ASOS 지점 정보 ---
STATION_DB = {
    "90": ["속초", "1968-01-01"], "93": ["북춘천", "2016-10-01"], "95": ["철원", "1988-01-01"],
    "98": ["동두천", "1998-02-01"], "99": ["파주", "2001-12-01"], "100": ["대관령", "1971-12-01"],
    "101": ["춘천", "1966-01-01"], "102": ["백령도", "2000-01-01"], "104": ["북강릉", "2008-10-01"],
    "105": ["강릉", "1911-10-01"], "108": ["서울", "1907-10-01"], "112": ["인천", "1904-08-01"],
    "114": ["원주", "1971-01-01"], "115": ["울릉도", "1938-08-01"], "119": ["수원", "1964-01-01"],
    "121": ["영월", "1994-01-01"], "127": ["충주", "1972-01-01"], "129": ["서산", "1968-01-01"],
    "130": ["울진", "1971-01-01"], "131": ["청주", "1967-01-01"], "133": ["대전", "1969-01-01"],
    "135": ["추풍령", "1935-01-01"], "136": ["안동", "1973-01-01"], "137": ["상주", "2002-01-01"],
    "138": ["포항", "1943-01-01"], "140": ["군산", "1968-01-01"], "143": ["대구", "1907-01-01"],
    "146": ["전주", "1918-01-01"], "152": ["울산", "1931-01-01"], "155": ["창원", "1985-01-01"],
    "156": ["광주", "1938-10-01"], "159": ["부산", "1904-04-01"], "162": ["통영", "1968-01-01"],
    "165": ["목포", "1904-04-01"], "168": ["여수", "1942-02-01"], "169": ["흑산도", "1997-01-01"],
    "170": ["완도", "1971-01-01"], "172": ["고창", "2010-12-01"], "174": ["순천", "1973-01-01"],
    "177": ["진도(첨찰산)", "2012-01-01"], "184": ["제주", "1923-05-01"], "185": ["고산", "1988-01-01"],
    "188": ["성산", "1973-01-01"], "189": ["서귀포", "1961-01-01"], "192": ["진주", "1969-01-01"],
    "201": ["강화", "1972-01-01"], "202": ["양평", "1972-01-01"], "203": ["이천", "1972-01-01"],
    "211": ["인제", "1972-01-01"], "212": ["홍천", "1972-01-01"], "216": ["태백", "1985-01-01"],
    "217": ["정선군", "2010-01-01"], "221": ["제천", "1972-01-01"], "226": ["보은", "1972-01-01"],
    "232": ["천안", "1972-01-01"], "235": ["보령", "1972-01-01"], "236": ["부여", "1972-01-01"],
    "238": ["금산", "1972-01-01"], "239": ["세종", "2019-10-01"], "243": ["부안", "1972-01-01"],
    "244": ["임실", "1972-01-01"], "245": ["정읍", "1972-01-01"], "247": ["남원", "1972-01-01"],
    "248": ["장수", "1972-01-01"], "251": ["고창군", "2010-01-01"], "252": ["영광군", "2010-01-01"],
    "253": ["김해시", "2010-01-01"], "254": ["순창군", "2010-01-01"], "255": ["북창원", "2010-01-01"],
    "257": ["양산시", "2010-01-01"], "258": ["보성군", "2010-01-01"], "259": ["강진군", "2009-12-01"],
    "260": ["장흥", "1972-01-01"], "261": ["해남", "2010-05-01"], "262": ["고흥", "1972-01-01"],
    "263": ["의령군", "2010-01-01"], "264": ["함양군", "2010-01-01"], "266": ["광양시", "2010-01-01"],
    "268": ["진도군", "2009-12-01"], "271": ["봉화", "1988-01-01"], "272": ["영주", "1972-01-01"],
    "273": ["문경", "1973-01-01"], "276": ["청송군", "2010-01-01"], "277": ["영덕", "1972-01-01"],
    "278": ["의성", "1973-01-01"], "279": ["구미", "1973-01-01"], "281": ["영천", "1972-01-01"],
    "283": ["경주시", "2010-01-01"], "284": ["거창", "1972-01-01"], "285": ["합천", "1973-01-01"],
    "288": ["밀양", "1973-01-01"], "289": ["산청", "1973-01-01"], "294": ["거제", "1972-01-01"],
    "295": ["남해", "1972-01-01"]
}

# --- [안정화 로직] 세션 및 재시도 설정 ---
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount('http://', HTTPAdapter(max_retries=retries))

@st.cache_data(show_spinner=False)
def get_weather_data_v29(key, stn, s_date, e_date):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    all_combined = []
    
    current_date = s_date.replace(day=1)
    date_list = []
    while current_date <= e_date:
        m_start = current_date.strftime("%Y%m%d")
        next_month = current_date + relativedelta(months=1)
        m_end = min(e_date, next_month - timedelta(days=1)).strftime("%Y%m%d")
        date_list.append((m_start, m_end))
        current_date = next_month

    msg_slot = st.empty()
    p_bar = st.progress(0)
    
    for i, (start, end) in enumerate(date_list):
        msg_slot.info(f"⏳ 데이터 수집 중: {start[:4]}년 {start[4:6]}월 불러오는 중...")
        for page in range(1, 11):
            params = {
                'serviceKey': key, 'pageNo': str(page), 'numOfRows': '999',
                'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
                'startDt': start, 'startHh': '01', 'endDt': end, 'endHh': '23', 'stnIds': stn
            }
            try:
                r = session.get(url, params=params, timeout=30)
                res = r.json()
                items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                if not items: break
                if isinstance(items, dict): items = [items]
                all_combined.extend(items)
            except Exception as e:
                return None, f"서버 응답 초과. 잠시 후 시도하세요."
        p_bar.progress((i + 1) / len(date_list))
    
    if not all_combined: return None, "데이터가 없습니다."
    df = pd.DataFrame(all_combined)
    df['wd'] = pd.to_numeric(df['wd'], errors='coerce')
    df['ws_kt'] = pd.to_numeric(df['ws'], errors='coerce') * 1.94384
    return df.dropna(subset=['wd', 'ws_kt']), len(df)

# 2. 사이드바 UI
st.sidebar.header("📋 분석 설정")
api_key = st.sidebar.text_input("1. API Key (Decoding)", type="password")

stn_options = [f"{v[0]} ({k})" for k, v in STATION_DB.items()]
selected_stn = st.sidebar.selectbox("2. 관측소 선택", stn_options, index=stn_options.index("광주 (156)"))
stn_id = selected_stn.split("(")[1].replace(")", "")
stn_name, stn_start = STATION_DB[stn_id]

st.sidebar.success(f"📌 {stn_name} 관측 시작: {stn_start}")

st.sidebar.markdown("---")
start_date = st.sidebar.date_input("시작일", date(2019, 1, 1))
end_date = st.sidebar.date_input("종료일", date(2023, 12, 31))
limit_kt = st.sidebar.selectbox("3. 측풍 허용치 (Knot)", [10, 13, 20], index=0)

if st.sidebar.button("🧹 데이터 캐시 삭제"):
    st.cache_data.clear()
    st.sidebar.info("삭제 완료.")

# 3. 분석 실행
if st.sidebar.button("🚀 분석 시작"):
    if not api_key: st.error("키를 입력하세요.")
    else:
        df, result = get_weather_data_v29(api_key, stn_id, start_date, end_date)
        if df is not None:
            st.success(f"✅ {stn_name} {result:,}시간 데이터 분석 완료")
            angles = np.arange(0, 181, 1)
            usabilities = []
            for a in angles:
                rad = np.radians(df['wd'] - a)
                crosswind = df['ws_kt'] * np.abs(np.sin(rad))
                usabilities.append((crosswind <= limit_kt).sum() / len(df) * 100)
            
            res_df = pd.DataFrame({'angle': angles, 'usability': usabilities})
            best = res_df.loc[res_df['usability'].idxmax()]

            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("최적 활주로", f"{int(best['angle']/10):02d}-{int((best['angle']+180)/10):02d}")
            c2.metric("최대 이용률", f"{best['usability']:.2f}%")
            c3.metric("판정", "✅ PASS" if best['usability'] >= 95 else "❌ FAIL")

            t1, t2 = st.tabs(["📈 이용률 곡선", "🌀 바람장미"])
            with t1:
                fig1 = px.line(res_df, x='angle', y='usability', title="방향별 활주로 이용률 곡선")
                fig1.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="ICAO 기준(95%)")
                st.plotly_chart(fig1, use_container_width=True)
            with t2:
                fig2 = px.bar_polar(df, r="ws_kt", theta="wd", color="ws_kt", 
                                   color_continuous_scale=px.colors.sequential.Viridis,
                                   title="풍향/풍속 빈도 분포 (Wind Rose)")
                st.plotly_chart(fig2, use_container_width=True)
        else: st.error(f"❌ 분석 실패: {result}")
