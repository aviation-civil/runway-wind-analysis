import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import time
from datetime import datetime, date

# 1. 페이지 설정
st.set_page_config(page_title="측풍 영향 활주로 분석기 V2.1", layout="wide")
st.title("✈️ 활주로 이용률(Usability Factor) 정밀 분석 도구")

# --- 기상청 ASOS 지점 리스트 ---
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
api_key = st.sidebar.text_input("1. API Key (Decoding 권장)", type="password")

station_name = st.sidebar.selectbox("2. 관측소 선택", list(STATIONS.values()), index=list(STATIONS.values()).index("목포"))
stn_id = [k for k, v in STATIONS.items() if v == station_name][0]

st.sidebar.markdown("---")
st.sidebar.subheader("📅 분석 기간 설정")
start_date = st.sidebar.date_input("시작일", date(2023, 1, 1))
end_date = st.sidebar.date_input("종료일", date(2023, 12, 31))

limit_kt = st.sidebar.selectbox("3. 측풍 허용치 (Knot)", [10, 13, 20], index=0)

# 3. 데이터 수집 함수 (강화된 로직)
def get_weather_data(key, stn, s_date, e_date):
    url = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
    all_data = []
    
    s_dt = s_date.strftime("%Y%m%d")
    e_dt = e_date.strftime("%Y%m%d")
    
    msg_slot = st.empty() # 진행 상황 메시지를 띄울 공간
    progress_bar = st.progress(0)
    
    for page in range(1, 101): # 최대 100페이지까지 탐색
        params = {
            'serviceKey': key, 'pageNo': str(page), 'numOfRows': '999',
            'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
            'startDt': s_dt, 'startHh': '01', 'endDt': e_dt, 'endHh': '23', 'stnIds': stn
        }
        
        try:
            r = requests.get(url, params=params, timeout=20)
            data = r.json()
            
            # API 응답 결과 확인
            res_header = data.get('response', {}).get('header', {})
            if res_header.get('resultCode') != '00':
                st.error(f"❌ API 오류: {res_header.get('resultMsg')}")
                return None
            
            body = data.get('response', {}).get('body', {})
            items_raw = body.get('items', {}).get('item', [])
            
            # 데이터가 1개만 올 경우 리스트로 변환
            if isinstance(items_raw, dict):
                items_raw = [items_raw]
                
            if not items_raw:
                break
            
            all_data.extend(items_raw)
            msg_slot.info(f"데이터 수집 중... 현재 {len(all_data)}행 확보 (Page {page})")
            progress_bar.progress(min(page / 20, 1.0)) # 대략적인 진행 표시
            time.sleep(0.1)
            
        except Exception as e:
            st.warning(f"페이지 {page} 호출 중 알림: {e}")
            break
            
    if not all_data:
        st.error("⚠️ 해당 기간에 수집된 바람 데이터가 없습니다.")
        return None
        
    df = pd.DataFrame(all_data)
    
    # 필수 컬럼(풍향 wd, 풍속 ws)이 있는지 확인
    if 'wd' not in df.columns or 'ws' not in df.columns:
        st.error("❌ 수집된 데이터에 풍향/풍속 정보가 포함되어 있지 않습니다.")
        return None

    # 숫자 변환 및 전처리 (결측치 제거)
    df['wd'] = pd.to_numeric(df['wd'], errors='coerce')
    df['ws'] = pd.to_numeric(df['ws'], errors='coerce')
    df = df.dropna(subset=['wd', 'ws'])
    
    df['ws_kt'] = df['ws'] * 1.94384 # m/s -> knot
    msg_slot.success(f"✅ 총 {len(df)}개의 유효 데이터를 확보했습니다.")
    return df

# 4. 분석 및 시각화
if st.sidebar.button("🚀 분석 시작"):
    if not api_key:
        st.warning("API Key를 입력해주세요.")
    elif start_date > end_date:
        st.error("시작일이 종료일보다 이후일 수 없습니다.")
    else:
        df = get_weather_data(api_key, stn_id, start_date, end_date)
        
        if df is not None:
            with st.spinner('활주로 방향 최적화 분석 중...'):
                # 1도 단위 이용률 계산
                angles = np.arange(0, 181, 1)
                usabilities = []
                
                for angle in angles:
                    diff_rad = np.radians(df['wd'] - angle)
                    crosswind = df['ws_kt'] * np.abs(np.sin(diff_rad))
                    usable_pct = (crosswind <= limit_kt).sum() / len(df) * 100
                    usabilities.append(usable_pct)
                
                res_df = pd.DataFrame({'angle': angles, 'usability': usabilities})
                best = res_df.loc[res_df['usability'].idxmax()]
                
                # 결과 지표 표시
                st.divider()
                c1, c2, c3 = st.columns(3)
                c1.metric("선택 관측소", station_name)
                c2.metric("최적 활주로 방향", f"{int(best['angle']/10):02d}-{int((best['angle']+180)/10):02d}", f"{best['angle']}°")
                c3.metric("최대 이용률", f"{best['usability']:.2f}%")
                
                if best['usability'] >= 95:
                    st.success(f"🌟 ICAO 권고 기준(95%)을 만족하는 최적의 방향입니다.")
                else:
                    st.warning(f"⚠️ 현재 조건에서 최대 이용률이 95%에 미달합니다.")

                # 그래프 탭 구성
                tab1, tab2, tab3 = st.tabs(["📊 이용률 곡선", "🌬️ 바람장미(Wind Rose)", "📝 데이터 미리보기"])
                
                with tab1:
                    fig1 = px.line(res_df, x='angle', y='usability', 
                                 title=f"방향별 활주로 이용률 변화 ({start_date} ~ {end_date})")
                    fig1.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="ICAO 기준(95%)")
                    st.plotly_chart(fig1, use_container_width=True)
                
                with tab2:
                    fig2 = px.bar_polar(df, r="ws_kt", theta="wd", color="ws_kt",
                                       color_continuous_scale=px.colors.sequential.Viridis,
                                       template="plotly_dark",
                                       title=f"{station_name} 관측소 풍향/풍속 분포")
                    st.plotly_chart(fig2, use_container_width=True)
                
                with tab3:
                    st.write("수집된 데이터의 상위 50행입니다.")
                    st.dataframe(df.head(50))
