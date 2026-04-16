import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import time
from datetime import datetime, date

# 1. 페이지 설정
st.set_page_config(page_title="측풍 영향 활주로 분석기 V2", layout="wide")
st.title("✈️ 활주로 이용률(Usability Factor) 정밀 분석 도구")

# --- 기상청 ASOS 모든 지점 리스트 (지점번호: 지점명) ---
STATIONS = {
    "90": "속초", "93": "북춘천", "95": "철원", "98": "동두천", "99": "파주",
    "100": "대관령", "101": "춘천", "102": "백령도", "104": "북강릉", "105": "강릉",
    "106": "동해", "108": "서울", "112": "인천", "114": "원주", "115": "울릉도",
    "119": "수원", "121": "영월", "127": "충주", "129": "서산", "130": "울진",
    "131": "청주", "133": "대전", "135": "추풍령", "136": "안동", "137": "상주",
    "138": "포항", "140": "군산", "143": "대구", "146": "전주", "152": "울산",
    "155": "창원", "156": "광주", "159": "부산", "162": "통영", "165": "목포",
    "168": "여수", "169": "흑산도", "170": "완도", "172": "고창", "174": "순천",
    "177": "진도(첨찰산)", "184": "제주", "185": "고산", "188": "성산", "189": "서귀포",
    "192": "진주", "201": "강화", "202": "양평", "203": "이천", "211": "인제",
    "212": "홍천", "216": "태백", "217": "정선군", "221": "제천", "226": "보은",
    "232": "천안", "235": "보령", "236": "부여", "238": "금산", "239": "세종",
    "243": "부안", "244": "임실", "245": "정읍", "247": "남원", "248": "장수",
    "251": "고창군", "252": "영광군", "253": "김해시", "254": "순창군", "255": "북창원",
    "257": "양산시", "258": "보성군", "259": "강진군", "260": "장흥", "261": "해남",
    "262": "고흥", "263": "의령군", "264": "함양군", "266": "광양시", "268": "진도군",
    "271": "봉화", "272": "영주", "273": "문경", "276": "청송군", "277": "영덕",
    "278": "의성", "279": "구미", "281": "영천", "283": "경주시", "284": "거창",
    "285": "합천", "288": "밀양", "289": "산청", "294": "거제", "295": "남해"
}

# 2. 사이드바 설정
st.sidebar.header("📋 분석 설정")
api_key = st.sidebar.text_input("1. API Key (Decoding)", type="password")

# 모든 관측소를 선택할 수 있는 셀렉트 박스 (이름으로 찾기)
station_name = st.sidebar.selectbox("2. 관측소 선택", list(STATIONS.values()), index=list(STATIONS.values()).index("목포"))
stn_id = [k for k, v in STATIONS.items() if v == station_name][0]

# 기간 설정 기능을 연도 슬라이더 대신 날짜 입력기로 변경
st.sidebar.markdown("---")
st.sidebar.subheader("📅 분석 기간 설정")
start_date = st.sidebar.date_input("시작일", date(2023, 1, 1))
end_date = st.sidebar.date_input("종료일", date(2023, 12, 31))

limit_kt = st.sidebar.selectbox("3. 측풍 허용치 (Knot)", [10, 13, 20], index=0)

# 3. 데이터 가져오기 함수 (날짜 기반 정밀 호출)
def get_weather_data(key, stn, s_date, e_date):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    all_data = []
    
    # 날짜 포맷 변경 (YYYYMMDD)
    s_dt = s_date.strftime("%Y%m%d")
    e_dt = e_date.strftime("%Y%m%d")
    
    progress_bar = st.progress(0)
    # 데이터 양에 따라 페이지 수를 넉넉히 잡음 (5년치 분석 시 최대 50페이지 예상)
    for page in range(1, 100):
        params = {
            'serviceKey': key, 'pageNo': str(page), 'numOfRows': '999',
            'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
            'startDt': s_dt, 'startHh': '01', 'endDt': e_dt, 'endHh': '23', 'stnIds': stn
        }
        
        try:
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            
            if data['response']['header']['resultCode'] != '00':
                st.error(f"API 에러: {data['response']['header']['resultMsg']}")
                return None
            
            items = data['response']['body']['items']['item']
            if not items: break
            
            all_data.extend(items)
            # 대략적인 진행률 표시
            progress_bar.progress(min(page / 50, 1.0))
            time.sleep(0.05)
        except:
            break
            
    if not all_data: return None
    df = pd.DataFrame(all_data)
    df['wd'] = pd.to_numeric(df['wd'])
    df['ws_kt'] = pd.to_numeric(df['ws']) * 1.94384
    return df

# 4. 분석 실행
if st.sidebar.button("🚀 분석 시작"):
    if start_date > end_date:
        st.error("시작일이 종료일보다 늦을 수 없습니다.")
    elif not api_key:
        st.warning("API Key를 입력해주세요.")
    else:
        with st.spinner(f'{station_name} 관측소 데이터를 분석 중입니다...'):
            df = get_weather_data(api_key, stn_id, start_date, end_date)
            
            if df is not None:
                results = []
                for angle in range(0, 181):
                    rad = np.radians(df['wd'] - angle)
                    crosswind = df['ws_kt'] * np.abs(np.sin(rad))
                    usable = (crosswind <= limit_kt).sum() / len(df) * 100
                    results.append({'angle': angle, 'usability': usable})
                
                res_df = pd.DataFrame(results)
                best = res_df.loc[res_df['usability'].idxmax()]

                st.success(f"✅ {start_date} ~ {end_date} 분석 완료")
                c1, c2, c3 = st.columns(3)
                c1.metric("선택 관측소", station_name)
                c2.metric("최적 활주로 방향", f"{int(best['angle']/10):02d}-{int((best['angle']+180)/10):02d}")
                c3.metric("최대 이용률", f"{best['usability']:.2f}%")

                # 그래프 시각화 (동일)
                fig1 = px.line(res_df, x='angle', y='usability', title="방향별 이용률 곡선")
                fig1.add_hline(y=95, line_dash="dash", line_color="red")
                st.plotly_chart(fig1, use_container_width=True)

                fig2 = px.bar_polar(df, r="ws_kt", theta="wd", color="ws_kt",
                                   color_continuous_scale=px.colors.sequential.Viridis,
                                   title="풍향/풍속 빈도 분포 (Wind Rose)")
                st.plotly_chart(fig2, use_container_width=True)
