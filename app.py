import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# 1. 웹 페이지 기본 설정
st.set_page_config(page_title="측풍 영향 활주로 이용률 분석 도구", layout="wide")

st.title("✈️ 활주로 이용률(Usability Factor) 분석 자동화 도구")
st.markdown("""
이 도구는 기상청 ASOS 데이터를 활용하여 활주로 방향별 측풍분력을 계산하고, ICAO 기준(95%) 만족 여부를 검토합니다.
""")

# 2. 사이드바 설정 (사용자 입력)
st.sidebar.header("📋 분석 설정")
api_key = st.sidebar.text_input("1. 공공데이터포털 API Key (Decoding 키 권장)", type="password", help="공공데이터포털에서 발급받은 인증키를 입력하세요.")
stn_id = st.sidebar.text_input("2. 관측소 지점번호", value="165", help="목포: 165, 해남: 261, 강진: 259")
target_year = st.sidebar.slider("3. 분석 연도", 2018, 2025, 2024)
limit_kt = st.sidebar.selectbox("4. 측풍 허용치 (Knot)", [10, 13, 20], index=0, help="코드 1,2(소형기)는 10kt, 코드 3(중형기)은 13kt, 코드 4(대형기)는 20kt 적용")

# 3. 데이터 수집 함수
def fetch_weather_data(key, stn, year):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    params = {
        'serviceKey': key,
        'pageNo': '1',
        'numOfRows': '9000', # 1년치 데이터(8760시간)를 한 번에 가져옴
        'dataType': 'JSON',
        'dataCd': 'ASOS',
        'dateCd': 'HR',
        'startDt': f"{year}0101",
        'startHh': '01',
        'endDt': f"{year}1231",
        'endHh': '23',
        'stnIds': stn
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        res_json = response.json()
        
        # 기상청 에러 메시지 처리
        header = res_json.get('response', {}).get('header', {})
        res_code = header.get('resultCode')
        res_msg = header.get('resultMsg')
        
        if res_code != '00':
            st.error(f"❌ 기상청 API 에러: {res_msg} (코드: {res_code})")
            if res_code == '99': st.info("💡 팁: API 키가 아직 활성화되지 않았을 수 있습니다. 1~2시간 후 다시 시도해 보세요.")
            return None

        items = res_json.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        if not items:
            st.warning("⚠️ 해당 연도/지점에 데이터가 없습니다.")
            return None
            
        df = pd.DataFrame(items)
        # 필요한 컬럼만 추출 및 숫자 변환 (풍향: wd, 풍속: ws)
        df = df[['tm', 'wd', 'ws']].dropna()
        df['wd'] = pd.to_numeric(df['wd'])
        df['ws'] = pd.to_numeric(df['ws'])
        # m/s를 Knot로 변환 (1 m/s = 1.94384 knots)
        df['ws_kt'] = df['ws'] * 1.94384
        return df
        
    except Exception as e:
        st.error(f"⚠️ 시스템 오류가 발생했습니다: {e}")
        return None

# 4. 분석 실행 섹션
if st.sidebar.button("🚀 분석 시작"):
    if not api_key:
        st.warning("🔑 왼쪽 사이드바에 API Key를 입력해 주세요.")
    else:
        with st.spinner(f'{target_year}년도 데이터를 분석 중입니다...'):
            df = fetch_weather_data(api_key, stn_id, target_year)
            
            if df is not None:
                # 활주로 방향별(0~180도,
