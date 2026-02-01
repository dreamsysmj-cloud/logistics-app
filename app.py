import streamlit as st
import pandas as pd
import plotly.express as px

# 페이지 설정
st.set_page_config(page_title="물류 마스터 통합 시스템", layout="wide")

# 캐시 삭제 버튼 (오류 날 때 누르라고 만듦)
if st.sidebar.button("🔄 오류나면 여기를 눌러서 초기화하세요"):
    st.cache_data.clear()
    st.rerun()

st.title("📦 물류 통합 시스템 (마스터 코드 + 시트 분류)")
st.markdown("""
**사용 순서:**
1. **[1. 기준 정보]**에 `통합재고(total)` 파일을 넣으세요. (업체 코드를 한국코드로 통일해줍니다)
2. **[2. 데이터 파일]**에 하은, 가온, 다이소 등의 엑셀 파일을 넣으세요.
   * 시트 이름에 **'매출'**이 있으면 판매량, **'재고'**가 있으면 재고량으로 인식합니다.
""")

# ==========================================
# 1. 파일 업로드 구역
# ==========================================
with st.sidebar:
    st.header("1️⃣ 기준 정보 (Master)")
    master_file = st.file_uploader("코드 매핑용 파일 (total.csv 등)", type=['xlsx', 'xls', 'csv'], key="master")
    
    st.divider()
    
    st.header("2️⃣ 데이터 파일 (Data)")
    data_files = st.file_uploader("매출/재고 엑셀 파일 (여러 개 가능)", accept_multiple_files=True, type=['xlsx', 'xls'], key="data")

# ==========================================
# 함수: 기준 정보 로딩 (코드 매핑표 만들기)
# ==========================================
@st.cache_data
def load_master_map(file):
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
            
        df.columns = df.columns.astype(str).str.replace(' ', '')
        
        # 한국코드 찾기
        master_col = next((c for c in df.columns if "한국" in c and "코드" in c), None)
        if not master_col:
             master_col = next((c for c in df.columns if "품목코드" in c), df.columns[0]) # 없으면 첫번째 컬럼

        # 품명 찾기
        name_col = next((c for c in df.columns if "품명" in c or "상품명" in c), None)

        # 매핑 딕셔너리 생성
        mapping = {}
        for col in df.columns:
            if col == master_col: continue
            
            # 업체별 코드 컬럼 찾기
            company = None
            if "하은" in col: company = "하은"
            elif "가온" in col: company = "가온"
            elif "다이소" in col: company = "다이소"
            elif "이마트" in col: company = "이마트"
            elif "쿠팡" in col: company = "쿠팡"
            
            if company:
                # {하은코드 : 한국코드} 형태로 저장
                temp_map = df.set_index(col)[master_col].dropna().astype(str).to_dict()
                # 키값도 문자로 변환
                mapping[company] = {str(k): v for k, v in temp_map.items()}
        
        # 품명 매핑 (한국코드 -> 품명)
        name_map = {}
        if name_col:
            name_map = df.set_index(master_col)[name_col].dropna().astype(str).to_dict()
            
        return mapping, name_map, None
    except Exception as e:
        return None, None, str(e)

# ==========================================
# 메인 로직
# ==========================================

# 1. 마스터 파일 처리
master_maps = {}
master_names = {}

if master_file:
    maps, names, err = load_master_map(master_file)
    if err:
        st.error(f"기준 파일 오류: {err}")
    else:
        master_maps = maps
        master_names = names
        st.success(f"✅ 기준 정보 적용됨: {', '.join(maps.keys())} 코드를 한국코드로 변환합니다.")

# 2. 데이터 파일 처리
if data_files:
    sales_list = []
    stock_list = []
    
    for file in data_files:
        try:
            # 모든 시트 읽기
            all_sheets = pd.read_excel(file, sheet_name=None)
            
            for sheet_name, df in all_sheets.items():
                if df.empty: continue
                
                # 헤더 정리
                df.columns = df.columns.astype(str).str.replace(' ', '')
                cols = df.columns
                
                # 필수 컬럼 찾기
                col_code = next((c for c in cols if "코드" in c or "Code" in c), None)
                col_qty = next((c for c in cols if "수량" in c or "재고" in c or "매출" in c or "출고" in c), None)
                col_date = next((c for c in cols if "일자" in c or "날짜" in c), None)
                
                if col_code and col_qty:
                    clean_df = df.copy()
                    
                    # 1) 컬럼명 통일
                    rename_map = {col_code: '원본코드', col_qty: '수량'}
                    if col_date: rename_map[col_date] = '일자'
                    clean_df = clean_df.rename(columns=rename_map)
                    
                    # 2) 수량 숫자 변환
                    clean_df['수량'] = pd.to_numeric(clean_df['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    
                    # 3) 업체명 추측 (시트명 or 파일명)
                    company = "기타"
                    for k in ["하은", "가온", "다이소", "한국", "이마트", "쿠팡"]:
                        if k in sheet_name or k in file.name:
                            company = k
                            break
                    
                    clean_df['업체'] = company
                    
                    # 4) ⭐ 코드 변환 (마스터 파일 이용) ⭐
                    clean_df['마스터코드'] = clean_df['원본코드'].astype(str) # 기본값
                    
                    if company in master_maps:
                        # 매핑표에 있으면 변환, 없으면 원본 유지
                        clean_df['마스터코드'] = clean_df['원본코드'].astype(str).map(master_maps[company]).fillna(clean_df['원본코드'].astype(str))
                    
                    # 한국 코드는 그 자체가 마스터
                    if company == "한국":
                        clean_df['마스터코드'] = clean_df['원본코드'].astype(str)

                    # 5) 품명 가져오기 (마스터 기준)
                    if master_names:
                        clean_df['품목명'] = clean_df['마스터코드'].map(master_names).fillna("미등록 품목")
                    else:
                        # 마스터 없으면 파일 내 품명 사용
                        c_name = next((c for c in cols if "품명" in c or "상품" in c), None)
                        clean_df['품목명'] = clean_df[c_name] if c_name else "-"
                        
                    # 6) 날짜 처리 (매출 데이터용)
                    if '일자' in clean_df.columns:
                        clean_df['일자'] = pd.to_datetime(clean_df['일자'], errors='coerce')
                    else:
                        clean_df['일자'] = pd.Timestamp.now() # 재고는 현재시간
                        
                    # 데이터 분류 (시트 이름 기준)
                    target_cols = ['일자', '업체', '마스터코드', '품목명', '수량']
                    final_data = clean_df[target_cols].copy()
                    
                    if "매출" in sheet_name or "판매" in sheet_name or "출고" in sheet_name:
                        sales_list.append(final_data)
                    elif "재고" in sheet_name:
                        stock_list.append(final_data)
                        
        except Exception as e:
            st.error(f"❌ {file.name} 처리 중 오류: {e}")

    # ==========================================
    # 결과 화면 출력
    # ==========================================
    tab1, tab2 = st.tabs(["💰 2년치 매출 분석 (통합코드)", "📦 현재 재고 현황"])
    
    with tab1:
        if sales_list:
            df_sales = pd.concat(sales_list)
            # 날짜 있는 것만
            df_sales = df_sales.dropna(subset=['일자'])
            
            # 월별/업체별 합계
            df_sales['년월'] = df_sales['일자'].dt.to_period('M').astype(str)
            monthly_trend = df_sales.pivot_table(index='년월', columns='업체', values='수량', aggfunc='sum', fill_value=0)
            
            st.markdown("### 📈 업체별 월간 매출 추이")
            fig = px.line(monthly_trend, markers=True)
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            
            # 품목별 합계 (한국코드 기준 합산!)
            item_sales = df_sales.pivot_table(index=['마스터코드', '품목명'], columns='업체', values='수량', aggfunc='sum', fill_value=0).reset_index()
            item_sales['총판매'] = item_sales.sum(axis=1, numeric_only=True)
            item_sales = item_sales.sort_values('총판매', ascending=False)
            
            st.markdown("### 🏆 통합 품목별 매출 순위 (TOP 50)")
            st.dataframe(item_sales.head(50), use_container_width=True, hide_index=True)
        else:
            st.info("매출 데이터가 없습니다. (시트 이름에 '매출'이 있는지 확인하세요)")
            
    with tab2:
        if stock_list:
            df_stock = pd.concat(stock_list)
            # 재고 합계
            stock_sum = df_stock.pivot_table(index=['마스터코드', '품목명'], columns='업체', values='수량', aggfunc='sum', fill_value=0).reset_index()
            stock_sum['총재고'] = stock_sum.sum(axis=1, numeric_only=True)
            
            st.metric("📦 총 재고 수량", f"{stock_sum['총재고'].sum():,.0f} 개")
            st.dataframe(stock_sum, use_container_width=True, height=600, hide_index=True)
        else:
            st.info("재고 데이터가 없습니다. (시트 이름에 '재고'가 있는지 확인하세요)")
