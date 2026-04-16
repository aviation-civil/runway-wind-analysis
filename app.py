import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import time
from datetime import datetime, date, timedelta

# 1. 페이지 설정 및 제목
st.set_page_config(page_title="측풍 영향 활주로 분석기 V2.6", layout="wide")
st.title("✈️ 활주로 이용률 정밀 분석 (에러 진단 강화)")

# --- 성능 최적화를 위한 데이터 캐싱 함수 ---
@st.cache_data(show_spinner=False)
def get_weather_data_v26(key, stn, s_date, e_date):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    all_data = []
    s_dt = s_date.strftime("%Y%m%d")
    e_dt = e_date.strftime("%Y%m%d")
    
    params = {
        'serviceKey': key, 'pageNo': '1', 'numOfRows': '10',
        'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
        'startDt': s_dt, 'startHh': '01', 'endDt': e_dt, 'endHh': '23', 'stnIds': stn
    }
    
    try:
        r = requests.get(url, params=params, timeout=15)
        # 1. 응답 자체가 JSON이 아닌 경우 처리
        try:
            res_json = r.json()
        except:
            return None, f"기상청 서버 응답 오류 (HTML 응답). API 키를 확인하세요."

        # 2. 기상청 결과 코드 확인
        header = res_json.get('response', {}).get('header', {})
        res_code = header.get('resultCode')
        res_msg = header.get('resultMsg')

        if res_code != '00':
            return None, f"기상청 API 에러: {res_msg} (코드: {res_code})"
            
        total_count = int(res_json.get('response', {}).get('body', {}).get('totalCount', 0))
        if total_count == 0:
            return None, "해당 기간에 데이터가 0건입니다. 날짜를 조정하세요."

        # 3. 실제 데이터 수집
        num_pages = (total_count // 999) + 1
        msg_slot = st.empty()
        p_bar = st.progress(0)
        
        for page in range(1, num_pages + 1):
            params['pageNo'] = str(page)
            params['numOfRows'] = '999'
            r = requests.get(url, params=params, timeout=20)
            items = r.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            all_data.extend(items)
            
            # 수집 현황 표시
            msg_slot.info(f"📥 데이터 수집 중: {len(all_data)} / {total_count} 행 (Page {page}/{num_pages})")
            p_bar.progress(page / num_pages)
            time.sleep(0.05)
            
        p_bar.empty()
        msg_slot.empty()

        df = pd.DataFrame(all_data)
        df['wd'] = pd.to_numeric(df['wd'], errors='coerce')
        df['ws_kt'] = pd.to_numeric(df['ws'], errors='coerce') * 1.94384
        return df.dropna(subset=['wd', 'ws_kt']), total_count
        
    except Exception as e:
        return None, f"연결 오류: {str(e)}"

# 2. 관측소 DB (생략 없이 주요 지점 포함)
STATION_DB = {
    "165": ["목포", "1904-04-01"], "261": ["해남", "2010-05-18"], "259": ["강진군", "2009-12-23"],
    "108": ["서울", "1907-10-01"], "112": ["인천", "1904-08-29"], "156": ["광주", "1938-10-01"],
    "168": ["여수", "1942-02-01"], "184": ["제주", "1923-05-01"], "146": ["전주", "1918-06-23"]
}

# 3. 사이드바 구성
st.sidebar.header("📋 설정")
api_key = st.sidebar.text_input("1. API Key (Decoding)", type="password")

# 관측소 선택 (DB에 없는 지점은 직접 입력 가능하게 처리)
station_options = [f"{v[0]} ({k})" for k, v in STATION_DB.items()]
selected_stn = st.sidebar.selectbox("2. 관측소 선택", station_options)
stn_id = selected_stn.split("(")[1].replace(")", "")
stn_name = STATION_DB[stn_id][0]

st.sidebar.info(f"📌 {stn_name} ({stn_id})\n- 데이터 가능: {STATION_DB[stn_id][1]}~")

st.sidebar.markdown("---")
start_date = st.sidebar.date_input("분석 시작일", date(2019, 1, 1))
end_date = st.sidebar.date_input("분석 종료일", date(2023, 12, 31))
limit_kt = st.sidebar.selectbox("측풍 허용치 (Knot)", [10, 13, 20], index=0)

# 캐시 초기화 버튼 (데이터가 꼬였을 때 사용)
if st.sidebar.button("🧹 데이터 캐시 초기화"):
    st.cache_data.clear()
    st.sidebar.success("캐시가 삭제되었습니다. 다시 분석을 눌러주세요.")

# 4. 분석 실행
if st.sidebar.button("🚀 분석 시작"):
    if not api_key:
        st.warning("API Key를 입력하세요.")
    else:
        # 데이터 수집 및 에러 진단
        df, result = get_weather_data_v26(api_key, stn_id, start_date, end_date)
        
        if df is not None:
            st.success(f"✅ {stn_name} 관측소 {result:,}건 데이터 확보 완료")
            
            # 활주로 이용률 계산 (최적화)
            angles = np.arange(0, 181, 1)
            usabilities = []
            for a in angles:
                diff = np.radians(df['wd'] - a)
                crosswind = df['ws_kt'] * np.abs(np.sin(diff))
                usabilities.append((crosswind <= limit_kt).sum() / len(df) * 100)
            
            res_df = pd.DataFrame({'angle': angles, 'usability': usabilities})
            best = res_df.loc[res_df['usability'].idxmax()]

            # 결과 대시보드
            st.divider()
            c1, c2, c3 = st.columns(3)
            c1.metric("최적 활주로", f"{int(best['angle']/10):02d}-{int((best['angle']+180)/10):02d}")
            c2.metric("최대 이용률", f"{best['usability']:.2f}%")
            c3.metric("판정", "✅ PASS" if best['usability'] >= 95 else "❌ FAIL")

            t1, t2 = st.tabs(["📊 분석 그래프", "🌬️ 바람장미"])
            with t1:
                fig1 = px.line(res_df, x='angle', y='usability', title="활주로 방향별 이용률")
                fig1.add_hline(y=95, line_dash="dash", line_color="red")
                st.plotly_chart(fig1, use_container_width=True)
            with t2:
                fig2 = px.bar_polar(df, r="ws_kt", theta="wd", color="ws_kt", title="바람장미 분포")
                st.plotly_chart(fig2, use_container_width=True)
        else:
            # 에러 메시지 표시
            st.error(f"❌ 분석 실패: {result}")
            st.info("💡 팁: API 키가 올바른지(Decoding 키 권장), 기상청에서 사용 승인이 났는지 확인하세요.")
