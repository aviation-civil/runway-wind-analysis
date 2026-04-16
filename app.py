import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="측풍 영향 활주로 분석기", layout="wide")
st.title("✈️ 활주로 이용률(Usability Factor) 분석 자동화")

# 2. 사이드바 설정
st.sidebar.header("📋 분석 설정")
api_key = st.sidebar.text_input("1. API Key (Decoding 키 권장)", type="password")
stn_id = st.sidebar.text_input("2. 관측소 번호", value="165")
target_year = st.sidebar.slider("3. 분석 연도", 2018, 2026, 2024)
limit_kt = st.sidebar.selectbox("4. 측풍 허용치 (Knot)", [10, 13, 20], index=0)

# 3. 데이터 가져오기 함수
def get_weather(key, stn, year):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    params = {
        'serviceKey': key, 'pageNo': '1', 'numOfRows': '9000',
        'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
        'startDt': f"{year}0101", 'startHh': '01',
        'endDt': f"{year}1231", 'endHh': '23', 'stnIds': stn
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if data['response']['header']['resultCode'] != '00':
            st.error(f"API 에러: {data['response']['header']['resultMsg']}")
            return None
        items = data['response']['body']['items']['item']
        df = pd.DataFrame(items)
        df['wd'] = pd.to_numeric(df['wd']) # 풍향
        df['ws_kt'] = pd.to_numeric(df['ws']) * 1.94384 # 풍속(Knot)
        return df
    except Exception as e:
        st.error(f"데이터를 불러오지 못했습니다. API 키 승인 대기 중이거나 키가 틀릴 수 있습니다. (에러: {e})")
        return None

# 4. 분석 실행
if st.sidebar.button("🚀 분석 시작"):
    if not api_key:
        st.warning("API Key를 입력해주세요.")
    else:
        with st.spinner('기상청 데이터를 분석 중입니다...'):
            df = get_weather(api_key, stn_id, target_year)
            if df is not None:
                # 활주로 방향별 이용률 계산 (1도 단위)
                results = []
                for angle in range(0, 181):
                    rad = np.radians(df['wd'] - angle)
                    crosswind = df['ws_kt'] * np.abs(np.sin(rad))
                    usable_count = (crosswind <= limit_kt).sum()
                    usability = (usable_count / len(df)) * 100
                    results.append({'angle': angle, 'usability': usability})
                
                res_df = pd.DataFrame(results)
                best = res_df.loc[res_df['usability'].idxmax()]

                # --- 결과 출력 ---
                st.success(f"✅ {target_year}년 분석 완료")
                c1, c2, c3 = st.columns(3)
                c1.metric("최적 활주로 방향", f"{int(best['angle']/10):02d}-{int((best['angle']+180)/10):02d}")
                c2.metric("최대 이용률", f"{best['usability']:.2f}%")
                c3.metric("판정", "PASS" if best['usability'] >= 95 else "FAIL")

                # 그래프 1: 이용률 곡선
                fig1 = px.line(res_df, x='angle', y='usability', 
                             labels={'angle': 'Runway Angle', 'usability': 'Usability (%)'},
                             title="방향별 활주로 이용률 변화")
                fig1.add_hline(y=95, line_dash="dash", line_color="red")
                st.plotly_chart(fig1, use_container_width=True)

                # 그래프 2: 바람장미 (Plotly 버전 - 추가 라이브러리 불필요!)
                st.subheader("🌬️ 바람장미 (Wind Rose)")
                fig2 = px.bar_polar(df, r="ws_kt", theta="wd", color="ws_kt",
                                   color_continuous_scale=px.colors.sequential.Viridis,
                                   title=f"{target_year}년 풍향/풍속 빈도 분포")
                st.plotly_chart(fig2, use_container_width=True)
