import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import time
from datetime import datetime, date

# 1. 페이지 설정
st.set_page_config(page_title="측풍 영향 활주로 분석기 V2.2", layout="wide")
st.title("✈️ 활주로 이용률 정밀 분석 (데이터 가용성 체크 기능 포함)")

# --- 기상청 ASOS 지점 리스트 및 주요 설치 정보 (예시 포함) ---
# 실제 운영 시작일 정보를 일부 포함하여 사용자에게 가이드를 줍니다.
STATIONS = {
    "90": "속초", "93": "북춘천", "95": "철원", "98": "동두천", "99": "파주",
    "100": "대관령", "101": "춘천", "102": "백령도", "104": "북강릉", "105": "강릉",
    "108": "서울", "112": "인천", "115": "울릉도", "119": "수원", "121": "영월",
    "127": "충주", "129": "서산", "131": "청주", "133": "대전", "135": "추풍령",
    "136": "안동", "138": "포항", "140": "군산", "143": "대구", "146": "전주",
    "152": "울산", "155": "창원", "156": "광주", "159": "부산", "162": "통영",
    "165": "목포", "168": "여수", "170": "완도", "172": "고창", "174": "순천",
    "184": "제주", "185": "고산", "188": "성산", "189": "서귀포", "192": "진주",
    "201": "강화", "202": "양평", "203": "이천", "212": "홍천", "216": "태백",
    "221": "제천", "226": "보은", "232": "천안", "235": "보령", "236": "부여",
    "238": "금산", "239": "세종", "243": "부안", "245": "정읍", "247": "남원",
    "248": "장수", "252": "영광군", "253": "김해시", "257": "양산시", "258": "보성군",
    "259": "강진군", "260": "장흥", "261": "해남", "262": "고흥", "263": "의령군",
    "264": "함양군", "266": "광양시", "268": "진도군", "271": "봉화", "272": "영주",
    "273": "문경", "277": "영덕", "278": "의성", "279": "구미", "281": "영천",
    "283": "경주시", "284": "거창", "285": "합천", "288": "밀양", "289": "산청",
    "294": "거제", "295": "남해"
}

# 2. 사이드바 설정
st.sidebar.header("📋 분석 환경 설정")
api_key = st.sidebar.text_input("1. API Key (Decoding)", type="password")

# 관측소 선택
station_name = st.sidebar.selectbox("2. 관측소 선택", list(STATIONS.values()), index=list(STATIONS.values()).index("목포"))
stn_id = [k for k, v in STATIONS.items() if v == station_name][0]

st.sidebar.info(f"선택된 관측소: {station_name} (코드: {stn_id})")

st.sidebar.markdown("---")
st.sidebar.subheader("📅 분석 기간 설정")
start_date = st.sidebar.date_input("시작일", date(2023, 1, 1))
end_date = st.sidebar.date_input("종료일", date(2023, 12, 31))

limit_kt = st.sidebar.selectbox("3. 측풍 허용치 (Knot)", [10, 13, 20], index=0)

# 3. 데이터 수집 함수 (데이터 존재 여부 체크 로직 포함)
def fetch_data(key, stn, s_date, e_date):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    all_data = []
    
    s_dt = s_date.strftime("%Y%m%d")
    e_dt = e_date.strftime("%Y%m%d")
    
    msg_slot = st.empty()
    progress_bar = st.progress(0)
    
    # 데이터 수집 (최대 100페이지)
    for page in range(1, 101):
        params = {
            'serviceKey': key, 'pageNo': str(page), 'numOfRows': '999',
            'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
            'startDt': s_dt, 'startHh': '01', 'endDt': e_dt, 'endHh': '23', 'stnIds': stn
        }
        
        try:
            r = requests.get(url, params=params, timeout=20)
            res_json = r.json()
            
            # 응답 코드 체크
            header = res_json.get('response', {}).get('header', {})
            if header.get('resultCode') != '00':
                st.error(f"❌ API 오류: {header.get('resultMsg')}")
                return None
                
            body = res_json.get('response', {}).get('body', {})
            items = body.get('items', {}).get('item', [])
            
            # 데이터 형태 보정 (1개일 때 dict -> list)
            if isinstance(items, dict): items = [items]
            
            if not items:
                if page == 1:
                    st.warning(f"💡 {station_name}({stn}) 관측소의 {s_date.year}년 근처 데이터를 찾을 수 없습니다. 관측 기간을 확인해 주세요.")
                break
                
            all_data.extend(items)
            msg_slot.info(f"데이터 수집 중: {len(all_data)}행 확보...")
            progress_bar.progress(min(page / 20, 1.0))
            time.sleep(0.1)
            
        except Exception as e:
            st.error(f"시스템 오류: {e}")
            break
            
    if not all_data: return None
    
    df = pd.DataFrame(all_data)
    df['wd'] = pd.to_numeric(df['wd'], errors='coerce')
    df['ws'] = pd.to_numeric(df['ws'], errors='coerce')
    df = df.dropna(subset=['wd', 'ws'])
    df['ws_kt'] = df['ws'] * 1.94384
    
    msg_slot.success(f"✅ 분석 준비 완료! 총 {len(df)}개의 시간별 데이터를 수집했습니다.")
    return df

# 4. 분석 버튼 및 결과 출력
if st.sidebar.button("🚀 분석 시작"):
    if not api_key:
        st.warning("API Key를 입력해주세요.")
    elif start_date > end_date:
        st.error("시작일이 종료일보다 늦을 수 없습니다.")
    else:
        df = fetch_data(api_key, stn_id, start_date, end_date)
        
        if df is not None:
            # 활주로 방향 최적화 (0~180도)
            angles = np.arange(0, 181, 1)
            usability_results = []
            
            for a in angles:
                diff = np.radians(df['wd'] - a)
                crosswind = df['ws_kt'] * np.abs(np.sin(diff))
                usable_pct = (crosswind <= limit_kt).sum() / len(df) * 100
                usability_results.append(usable_pct)
            
            res_df = pd.DataFrame({'angle': angles, 'usability': usability_results})
            best = res_df.loc[res_df['usability'].idxmax()]
            
            # --- 결과 시각화 ---
            st.divider()
            col1, col2
