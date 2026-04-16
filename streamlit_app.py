import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
from windrose import WindroseAxes
import matplotlib.pyplot as plt

# 1. 페이지 설정
st.set_page_config(page_title="측풍 영향 활주로 이용률 분석", layout="wide")
st.title("✈️ 활주로 이용률(Usability Factor) 분석 자동화 도구")

# 2. 사이드바 설정
st.sidebar.header("📋 분석 설정")
api_key = st.sidebar.text_input("공공데이터포털 API Key", type="password")
stn_id = st.sidebar.text_input("관측소 지점번호 (목포: 165, 해남: 261)", value="165")
target_year = st.sidebar.slider("분석 연도", 2015, 2026, 2024)
limit_kt = st.sidebar.selectbox("측풍 허용치 (Knot)", [10, 13, 20], index=0)

# 3. 데이터 수집 함수
def get_data(key, stn, year):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    params = {
        'serviceKey': key, 'pageNo': '1', 'numOfRows': '9000',
        'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
        'startDt': f"{year}0101", 'startHh': '01',
        'endDt': f"{year}1231", 'endHh': '23', 'stnIds': stn
    }
    res = requests.get(url, params=params).json()
    items = res['response']['body']['items']['item']
    df = pd.DataFrame(items)
    df['wd'] = pd.to_numeric(df['wd']) # 풍향
    df['ws'] = pd.to_numeric(df['ws']) * 1.94384 # m/s -> knot 변환
    return df

# 4. 분석 실행
if st.sidebar.button("분석 시작"):
    if not api_key:
        st.error("API Key를 입력해주세요.")
    else:
        with st.spinner('데이터 분석 중...'):
            df = get_data(api_key, stn_id, target_year)
            
            # 1도 단위 전수 조사 (0~180도)
            angles = range(0, 181, 1)
            usabilities = []
            for a in angles:
                crosswind = df['ws'] * np.abs(np.sin(np.radians(df['wd'] - a)))
                usable = (crosswind <= limit_kt).sum() / len(df) * 100
                usabilities.append(usable)
            
            res_df = pd.DataFrame({'각도': angles, '이용률': usabilities})
            best = res_df.loc[res_df['이용률'].idxmax()]

            # 결과 출력
            col1, col2 = st.columns([1, 1])
            with col1:
                st.subheader("📍 최적 방향 분석 결과")
                st.metric("최적 활주로 방향", f"{int(best['각도']):02d}-{(int(best['각도'])+180)%360:02d}")
                st.metric("최대 이용률", f"{best['이용률']:.2f}%")
                
                # 이용률 그래프
                fig = px.line(res_df, x='각도', y='이용률', title="방향별 이용률 변화")
                fig.add_hline(y=95, line_dash="dash", line_color="red")
                st.plotly_chart(fig)

            with col2:
                st.subheader("🌬️ 바람장미(Wind Rose)")
                fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection='windrose'))
                ax.bar(df['wd'], df['ws'], normed=True, opening=0.8, edgecolor='white')
                ax.set_legend()
                st.pyplot(fig)
