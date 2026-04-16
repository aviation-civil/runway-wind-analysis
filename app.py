import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import time
from datetime import datetime, date, timedelta

# 1. 페이지 설정 및 캐시 기능 정의
st.set_page_config(page_title="측풍 영향 활주로 분석기 V2.5", layout="wide")

# --- 성능 최적화를 위한 데이터 캐싱 함수 ---
@st.cache_data(show_spinner=False)
def get_cached_weather_data(key, stn, s_date, e_date):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    all_data = []
    s_dt = s_date.strftime("%Y%m%d")
    e_dt = e_date.strftime("%Y%m%d")
    
    # 데이터 총 개수 파악을 위한 첫 호출
    params = {
        'serviceKey': key, 'pageNo': '1', 'numOfRows': '1',
        'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
        'startDt': s_dt, 'startHh': '01', 'endDt': e_dt, 'endHh': '23', 'stnIds': stn
    }
    
    try:
        r = requests.get(url, params=params, timeout=10)
        res_json = r.json()
        total_count = int(res_json.get('response', {}).get('body', {}).get('totalCount', 0))
        
        if total_count == 0:
            return None, 0
            
        # 실제 데이터 수집 (999개씩 분할 호출)
        num_pages = (total_count // 999) + 1
        for page in range(1, num_pages + 1):
            params['pageNo'] = str(page)
            params['numOfRows'] = '999'
            r = requests.get(url, params=params, timeout=20)
            items = r.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            all_data.extend(items)
            time.sleep(0.01) # 속도 향상을 위해 대기시간 최소화
            
        df = pd.DataFrame(all_data)
        df['wd'] = pd.to_numeric(df['wd'], errors='coerce')
        df['ws_kt'] = pd.to_numeric(df['ws'], errors='coerce') * 1.94384
        return df.dropna(subset=['wd', 'ws_kt']), total_count
    except:
        return None, 0

# 2. 관측소 상세 정보 (지점번호: [이름, 관측시작일])
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
    "184": ["제주", "1923-05-01"], "185": ["고산", "1988-01-01"], "188": ["성산", "1973-01-01"],
    "189": ["서귀포", "1961-01-01"], "192": ["진주", "1969-01-01"], "201": ["강화", "1972-01-01"],
    "202": ["양평", "1972-01-01"], "203": ["이천", "1972-01-01"], "211": ["인제", "1972-01-01"],
    "212": ["홍천", "1972-01-01"], "216": ["태백", "1985-01-01"], "217": ["정선군", "2010-01-01"],
    "221": ["제천", "1972-01-01"], "226": ["보은", "1972-01-01"], "232": ["천안", "1972-01-01"],
    "235": ["보령", "1972-01-01"], "236": ["부여", "1972-01-01"], "238": ["금산", "1972-01-01"],
    "239": ["세종", "2019-10-01"], "243": ["부안", "1972-01-01"], "244": ["임실", "1972-01-01"],
    "245": ["정읍", "1972-01-01"], "247": ["남원", "1972-01-01"], "248": ["장수", "1972-01-01"],
    "251": ["고창군", "2010-01-01"], "252": ["영광군", "2010-01-01"], "253": ["김해시", "2010-01-01"],
    "254": ["순창군", "2010-01-01"], "255": ["북창원", "2010-01-01"], "257": ["양산시", "2010-01-01"],
    "258": ["보성군", "2010-01-01"], "259": ["강진군", "2009-12-01"], "260": ["장흥", "1972-01-01"],
    "261": ["해남", "2010-05-01"], "262": ["고흥", "1972-01-01"], "263": ["의령군", "2010-01-01"],
    "264": ["함양군", "2010-01-01"], "266": ["광양시", "2010-01-01"], "268": ["진도군", "2009-12-01"],
    "271": ["봉화", "1988-01-01"], "272": ["영주", "1972-01-01"], "273": ["문경", "1973-01-01"],
    "276": ["청송군", "2010-01-01"], "277": ["영덕", "1972-01-01"], "278": ["의성", "1973-01-01"],
    "279": ["구미", "1973-01-01"], "281": ["영천", "1972-01-01"], "283": ["경주시", "2010-01-01"],
    "284": ["거창", "1972-01-01"], "285": ["합천", "1973-01-01"], "288": ["밀양", "1973-01-01"],
    "289": ["산청", "1973-01-01"], "294": ["거제", "1972-01-01"], "295": ["남해", "1972-01-01"]
}

# 3. 사이드바 UI
st.sidebar.header("📋 분석 환경 설정")
api_key = st.sidebar.text_input("1. API Key (Decoding)", type="password")

station_options = [f"{v[0]} ({k})" for k, v in STATION_DB.items()]
selected_stn = st.sidebar.selectbox("2. 관측소 선택", station_options, index=station_options.index("목포 (165)"))
stn_id = selected_stn.split("(")[1].replace(")", "")
stn_name = STATION_DB[stn_id][0]
stn_start = STATION_DB[stn_id][1]

st.sidebar.info(f"📌 {stn_name} 관측소\n- 데이터 가능 시점: {stn_start} 부터")

st.sidebar.markdown("---")
st.sidebar.subheader("📅 분석 기간 설정")
start_date = st.sidebar.date_input("분석 시작일", date(2019, 1, 1))
end_date = st.sidebar.date_input("분석 종료일", date(2023, 12, 31))

limit_kt = st.sidebar.selectbox("3. 측풍 허용치 (Knot)", [10, 13, 20], index=0)

# 4. 메인 로직
if st.sidebar.button("🚀 분석 시작"):
    if not api_key:
        st.warning("API Key를 입력해주세요.")
    else:
        # 데이터 수집 (캐시 사용)
        status_text = st.empty()
        status_text.info(f"🔄 {stn_name} 관측소 데이터를 불러오고 있습니다. (최초 1회 소요)")
        
        df, count = get_cached_weather_data(api_key, stn_id, start_date, end_date)
        
        if df is not None:
            status_text.success(f"✅ 데이터 {count:,}건 수집 완료! 분석을 시작합니다.")
            
            # 활주로 방향 최적화 (NumPy 벡터 연산으로 속도 극대화)
            angles = np.arange(0, 181, 1)
            usabilities = []
            
            # 진행 상태 표시
            progress_bar = st.progress(0)
            for i, a in enumerate(angles):
                rad = np.radians(df['wd'] - a)
                crosswind = df['ws_kt'] * np.abs(np.sin(rad))
                usabilities.append((crosswind <= limit_kt).sum() / len(df) * 100)
                if i % 20 == 0: progress_bar.progress(i / 180)
            progress_bar.empty()

            res_df = pd.DataFrame({'angle': angles, 'usability': usabilities})
            best = res_df.loc[res_df['usability'].idxmax()]
            
            # --- 결과 대시보드 ---
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("분석 관측소", stn_name)
            c2.metric("최적 활주로 방향", f"{int(best['angle']/10):02d}-{int((best['angle']+180)/10):02d}", f"{int(best['angle'])}°")
            c3.metric("최대 이용률", f"{best['usability']:.2f}%")
            
            t1, t2 = st.tabs(["📊 방향별 이용률", "🌬️ 바람장미"])
            with t1:
                fig1 = px.line(res_df, x='angle', y='usability', title=f"Runway Usability ({start_date} ~ {end_date})")
                fig1.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="ICAO 95%")
                st.plotly_chart(fig1, use_container_width=True)
            with t2:
                fig2 = px.bar_polar(df, r="ws_kt", theta="wd", color="ws_kt", 
                                   color_continuous_scale=px.colors.sequential.Viridis,
                                   title="Wind Rose (바람장미)")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            status_text.error("데이터를 가져오지 못했습니다. 날짜 범위를 다시 확인해 주세요.")
