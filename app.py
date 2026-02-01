import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="물류 통합 대시보드", layout="wide")

st.title("📦 물류 재고 & 매출 통합 현황판")
st.markdown("엑셀 파일(재고, 판매)을 드래그해서 넣으세요. (가온, 하은, 다이소 등 양식이 달라도 알아서 처리합니다)")

# 사이드바: 파일 업로드
with st.sidebar:
    st.header("📂 엑셀 파일 업로드")
    uploaded_files = st.file_uploader(
        "파일을 모두 이곳에 드래그하세요", 
        accept_multiple_files=True, 
        type=['xlsx', 'xls', 'csv']
    )
    st.info("💡 재고 파일과 판매 파일을 섞어서 올려도 됩니다.")

# ---------------------------------------------------------
# 함수: 엑셀에서 '진짜 헤더'가 있는 줄 찾기
# ---------------------------------------------------------
def load_excel_smartly(file):
    try:
        # 앞부분 15줄을 읽어서 표의 머리글을 찾습니다.
        df_preview = pd.read_excel(file, header=None, nrows=15)
        
        # 우리가 찾고 싶은 핵심 단어들 (이 중 하나라도 있으면 거기가 헤더!)
        # 가온 파일을 위해 '바코드', '출고', '가용재고' 등을 추가했습니다.
        keywords = ["품목코드", "코드", "바코드", "품명", "상품명", "수량", "재고", "출고", "가용재고"]
        
        target_row = -1
        for idx, row in df_preview.iterrows():
            row_str = row.astype(str).values
            # 행에 키워드가 포함되어 있는지 확인
            if any(key in s for s in row_str for key in keywords):
                target_row = idx
                break
        
        if target_row == -1:
            return None, "표 머리글(품목코드/바코드 등)을 찾을 수 없음"

        # 진짜 헤더 위치를 알았으니 다시 제대로 읽습니다.
        df = pd.read_excel(file, header=target_row)
        return df, None
        
    except Exception as e:
        return None, str(e)

# ---------------------------------------------------------
# 함수: 컬럼 이름 찾기 (번역기 기능)
# ---------------------------------------------------------
def find_column_name(columns, keywords):
    # keywords 리스트에 있는 단어가 포함된 컬럼을 찾아서 반환
    for key in keywords:
        found = next((c for c in columns if key in str(c)), None)
        if found:
            return found
    return None

# ---------------------------------------------------------
# 메인 로직
# ---------------------------------------------------------
if uploaded_files:
    stock_list = [] # 재고 데이터 담을 곳
    sales_list = [] # 판매 데이터 담을 곳
    
    # 1. 파일 읽기 및 분류
    for file in uploaded_files:
        filename = file.name
        
        # 업체명 추측
        company = "기타"
        if "하은" in filename: company = "하은"
        elif "한국" in filename: company = "한국"
        elif "가온" in filename: company = "가온"
        elif "다이소" in filename: company = "다이소"
        
        # 스마트하게 엑셀 읽기
        df, error_msg = load_excel_smartly(file)
        
        if df is None:
            st.error(f"❌ {filename} 읽기 실패: {error_msg}")
            continue

        # 컬럼 찾기 (우선순위대로 찾습니다)
        cols = df.columns
        
        # 1) 품목코드 찾기 (바코드, 내부코드 등)
        col_code = find_column_name(cols, ['품목코드', '바코드', '상품코드', '내부코드', 'Code'])
        
        # 2) 품목명 찾기 (상품명, 규격 등)
        col_name = find_column_name(cols, ['품목명', '품명', '상품명', '규격', '상품'])
        
        # 3) 수량 찾기 (가용재고, 출고, 재고수량 등)
        # 중요: '출고일자' 같은 날짜 컬럼이 걸리지 않게 주의
        qty_candidates = ['재고수량', '가용재고', '장부재고', '총재고', '재고', '출고(E)', '출고', '수량', '매출']
        col_qty = None
        for key in qty_candidates:
            found = next((c for c in cols if key in str(c) and "일자" not in str(c) and "날짜" not in str(c)), None)
            if found:
                col_qty = found
                break
        
        # 데이터 정제
        if col_code and col_qty:
            clean_df = df.copy()
            
            # 컬럼 이름 통일
            rename_map = {col_code: '품목코드', col_qty: '수량'}
            if col_name:
                rename_map[col_name] = '품목명'
            else:
                clean_df['품목명'] = '이름없음'
            
            clean_df = clean_df.rename(columns=rename_map)
            clean_df['업체'] = company
            
            # 수량 숫자로 변환 (천단위 콤마, 공백 제거)
            clean_df['수량'] = pd.to_numeric(clean_df['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

            # 파일명에 '판매'나 '매출'이 있으면 판매 리스트로, 아니면 재고로
            if "판매" in filename or "매출" in filename:
                sales_list.append(clean_df[['품목코드', '품목명', '수량', '업체']])
            else:
                stock_list.append(clean_df[['품목코드', '품목명', '수량', '업체']])
        else:
            st.warning(f"⚠️ {filename}: 핵심 칸(코드, 수량)을 못 찾아서 건너뜁니다. (확인된 컬럼: {col_code}, {col_qty})")

    # ---------------------------------------------------------
    # 2. 대시보드 화면 그리기
    # ---------------------------------------------------------
    
    tab1, tab2 = st.tabs(["📦 재고 현황", "💰 판매(매출) 현황"])

    # [탭 1] 재고 현황
    with tab1:
        if stock_list:
            df_stock = pd.concat(stock_list)
            
            # 피벗 테이블
            pivot_stock = df_stock.pivot_table(
                index=['품목코드', '품목명'], columns='업체', values='수량', aggfunc='sum', fill_value=0
            ).reset_index()
            
            # 총계
            num_cols = [c for c in pivot_stock.columns if c not in ['품목코드', '품목명']]
            pivot_stock['총재고'] = pivot_stock[num_cols].sum(axis=1)

            c1, c2, c3 = st.columns(3)
            c1.metric("총 품목 수", f"{len(pivot_stock)} 개")
            c2.metric("총 재고 수량", f"{pivot_stock['총재고'].sum():,.0f} 개")
            c3.metric("최다 보유 업체", pivot_stock[num_cols].sum().idxmax())
            
            st.divider()
            
            col_chart, col_table = st.columns([1, 2])
            with col_chart:
                st.subheader("업체별 재고 비중")
                st.bar_chart(pivot_stock[num_cols].sum(), color="#FF4B4B")
            with col_table:
                st.subheader("상세 재고표")
                st.dataframe(pivot_stock, use_container_width=True, height=400, hide_index=True)
        else:
            st.info("재고 파일이 아직 업로드되지 않았습니다.")

    # [탭 2] 판매 현황
    with tab2:
        if sales_list:
            df_sales = pd.concat(sales_list)
            
            # 피벗 테이블
            pivot_sales = df_sales.pivot_table(
                index=['품목코드', '품목명'], columns='업체', values='수량', aggfunc='sum', fill_value=0
            ).reset_index()
            
            pivot_sales['총판매량'] = pivot_sales[[c for c in pivot_sales.columns if c not in ['품목코드', '품목명']]].sum(axis=1)

            k1, k2 = st.columns(2)
            k1.metric("총 판매 건수", f"{len(df_sales):,.0f} 건")
            k2.metric("총 판매 수량", f"{pivot_sales['총판매량'].sum():,.0f} 개")
            
            st.divider()
            
            st.subheader("🏆 많이 팔린 상품 TOP 5")
            top_sales = pivot_sales.sort_values(by='총판매량', ascending=False).head(5)
            st.bar_chart(top_sales.set_index('품목명')['총판매량'], color="#1E90FF")
            
            st.subheader("상세 판매 내역")
            st.dataframe(pivot_sales, use_container_width=True, hide_index=True)
        else:
            st.info("판매(매출) 파일이 아직 업로드되지 않았습니다.")

else:
    st.info("👈 왼쪽 사이드바에 엑셀 파일들을 드래그해서 넣어주세요.")
