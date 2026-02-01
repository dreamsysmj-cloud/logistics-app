import streamlit as st
import pandas as pd

# 페이지 설정
st.set_page_config(page_title="물류 통합 대시보드", layout="wide")

st.title("📦 물류 재고 & 매출 통합 현황판")
st.markdown("엑셀 파일(재고, 판매)을 드래그해서 넣으세요. 제목 줄이 있어도 알아서 처리합니다.")

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
# 함수: 엑셀에서 '진짜 헤더(품목코드)'가 있는 줄 찾기
# ---------------------------------------------------------
def load_excel_smartly(file):
    try:
        # 일단 앞부분 10줄만 읽어봅니다.
        df_preview = pd.read_excel(file, header=None, nrows=10)
        
        # '품목코드' 또는 '코드'라는 글자가 있는 행(Row)을 찾습니다.
        target_row = -1
        for idx, row in df_preview.iterrows():
            row_str = row.astype(str).values
            if any("품목코드" in s or "코드" in s for s in row_str):
                target_row = idx
                break
        
        if target_row == -1:
            return None, "표 머리글(품목코드)을 찾을 수 없음"

        # 진짜 헤더 위치를 알았으니 다시 제대로 읽습니다.
        df = pd.read_excel(file, header=target_row)
        return df, None
        
    except Exception as e:
        return None, str(e)

# ---------------------------------------------------------
# 메인 로직
# ---------------------------------------------------------
if uploaded_files:
    stock_list = [] # 재고 데이터 담을 곳
    sales_list = [] # 판매 데이터 담을 곳
    
    # 1. 파일 읽기 및 분류
    for file in uploaded_files:
        # 파일명으로 업체명 추측
        filename = file.name
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

        # 필요한 컬럼 찾기 (유연하게)
        cols = df.columns.astype(str)
        col_code = next((c for c in cols if "코드" in c), None)
        col_name = next((c for c in cols if "품명" in c or "규격" in c or "품목" in c), None)
        col_qty = next((c for c in cols if "수량" in c or "재고" in c), None)
        
        # 데이터 정제
        if col_code and col_qty:
            clean_df = df.copy()
            # 컬럼 이름 통일
            rename_map = {col_code: '품목코드', col_qty: '수량'}
            if col_name:
                rename_map[col_name] = '품목명'
            else:
                clean_df['품목명'] = '이름없음' # 품명 없으면 임시로 채움
            
            clean_df = clean_df.rename(columns=rename_map)
            clean_df['업체'] = company
            
            # 수량 숫자로 변환 (공백 제거 등)
            clean_df['수량'] = pd.to_numeric(clean_df['수량'], errors='coerce').fillna(0)

            # 파일명에 '판매'나 '매출'이 있으면 판매 리스트로, 아니면 재고로
            if "판매" in filename or "매출" in filename:
                sales_list.append(clean_df[['품목코드', '품목명', '수량', '업체']])
            else:
                stock_list.append(clean_df[['품목코드', '품목명', '수량', '업체']])
        else:
            st.warning(f"⚠️ {filename}: '코드'나 '수량' 칸을 못 찾아서 건너뜁니다.")

    # ---------------------------------------------------------
    # 2. 대시보드 화면 그리기
    # ---------------------------------------------------------
    
    # 탭으로 재고와 판매를 나눠서 보여줌
    tab1, tab2 = st.tabs(["📦 재고 현황", "💰 판매(매출) 현황"])

    # [탭 1] 재고 현황
    with tab1:
        if stock_list:
            df_stock = pd.concat(stock_list)
            
            # 피벗 테이블 (업체별 가로 정렬)
            pivot_stock = df_stock.pivot_table(
                index=['품목코드', '품목명'], columns='업체', values='수량', aggfunc='sum', fill_value=0
            ).reset_index()
            
            # 총계 계산
            num_cols = [c for c in pivot_stock.columns if c not in ['품목코드', '품목명']]
            pivot_stock['총재고'] = pivot_stock[num_cols].sum(axis=1)

            # 상단 지표
            c1, c2, c3 = st.columns(3)
            c1.metric("총 품목 수", f"{len(pivot_stock)} 개")
            c2.metric("총 재고 수량", f"{pivot_stock['총재고'].sum():,.0f} 개")
            c3.metric("최다 보유 업체", pivot_stock[num_cols].sum().idxmax())
            
            st.divider()
            
            # 그래프와 표
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

            # 상단 지표
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
