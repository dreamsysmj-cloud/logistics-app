import streamlit as st
import pandas as pd
import io

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
# 함수: 엑셀에서 '진짜 헤더' 위치를 점수로 찾기 (개선됨)
# ---------------------------------------------------------
def find_header_and_load(file):
    try:
        # 1. 파일의 앞부분 20줄만 미리 읽어옵니다.
        df_preview = pd.read_excel(file, header=None, nrows=20)
        
        best_row_idx = -1
        max_score = 0
        
        # 우리가 찾는 핵심 단어들
        code_keywords = ["품목코드", "코드", "바코드", "내부코드", "상품코드"]
        name_keywords = ["품명", "상품명", "규격", "상품명 및 규격"]
        # '출고 (E)' 처럼 괄호가 있는 경우도 찾기 위해 키워드 보강
        qty_keywords = ["수량", "재고", "가용재고", "장부재고", "출고", "매출", "출고(E)", "출고 (E)", "주문수량"]

        # 2. 각 줄을 검사해서 점수를 매깁니다.
        for idx, row in df_preview.iterrows():
            row_str_list = row.astype(str).values
            score = 0
            
            # 특수문자 '▶'로 시작하는 줄은 메타데이터이므로 무시 (가온 파일 해결책)
            if str(row_str_list[0]).strip().startswith("▶"):
                continue

            # 셀 하나하나를 검사
            for cell in row_str_list:
                cell_text = str(cell)
                
                # '코드' 관련 단어가 있으면 1점
                if any(k in cell_text for k in code_keywords): score += 1
                
                # '품명' 관련 단어가 있으면 1점
                if any(k in cell_text for k in name_keywords): score += 1
                
                # '수량' 관련 단어가 있으면 1점 (단, '일자', '금액' 등은 제외)
                if any(k in cell_text for k in qty_keywords):
                    if "일자" not in cell_text and "금액" not in cell_text and "단가" not in cell_text:
                        score += 1
            
            # 점수가 가장 높은 줄을 기억합니다
            if score > max_score:
                max_score = score
                best_row_idx = idx
        
        # 3. 점수가 0점이거나 못 찾았으면
        if max_score == 0 or best_row_idx == -1:
            return None, "표의 머리글(코드, 수량 등)을 찾지 못했습니다."

        # 4. 진짜 헤더 위치로 파일을 다시 읽습니다.
        df = pd.read_excel(file, header=best_row_idx)
        return df, None
        
    except Exception as e:
        return None, str(e)

# ---------------------------------------------------------
# 함수: 컬럼 이름 찾기 (번역기 기능)
# ---------------------------------------------------------
def find_column_name(columns, keywords):
    for key in keywords:
        # 정확히 일치하거나 포함된 컬럼 찾기
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
    
    for file in uploaded_files:
        filename = file.name
        
        # 업체명 추측
        company = "기타"
        if "하은" in filename: company = "하은"
        elif "한국" in filename: company = "한국"
        elif "가온" in filename: company = "가온"
        elif "다이소" in filename: company = "다이소"
        elif "이마트" in filename: company = "이마트" # 이마트 추가
        
        # 1. 스마트하게 엑셀 읽기
        df, error_msg = find_header_and_load(file)
        
        if df is None:
            st.error(f"❌ {filename} 읽기 실패: {error_msg}")
            continue

        # 2. 컬럼 매칭 (번역)
        cols = df.columns
        
        # 품목코드 찾기
        col_code = find_column_name(cols, ['바코드', '품목코드', '상품코드', '내부코드', 'Code'])
        
        # 품목명 찾기
        col_name = find_column_name(cols, ['상품명 및 규격', '품목명', '품명', '상품명', '규격'])
        
        # 수량 찾기 (가온 판매의 '출고 (E)' 포함)
        qty_candidates = ['가용재고', '출고(E)', '출고 (E)', '재고수량', '수량', '총재고', '출고수량', '매출수량', '출고']
        col_qty = None
        for key in qty_candidates:
            # '일자', '금액', '단가', '오류' 등이 포함된 컬럼은 제외
            found = next((c for c in cols if key in str(c) and "일자" not in str(c) and "금액" not in str(c) and "단가" not in str(c) and "오류" not in str(c)), None)
            if found:
                col_qty = found
                break
        
        # 3. 데이터 정제 및 담기
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
            
            # 수량 숫자로 변환 (콤마 제거)
            clean_df['수량'] = pd.to_numeric(clean_df['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

            # 파일명에 '판매'나 '매출'이 있으면 판매 리스트로
            if "판매" in filename or "매출" in filename:
                sales_list.append(clean_df[['품목코드', '품목명', '수량', '업체']])
            else:
                stock_list.append(clean_df[['품목코드', '품목명', '수량', '업체']])
        else:
            st.warning(f"⚠️ {filename}: 핵심 칸을 못 찾았습니다. (확인된 헤더: {list(cols)[:5]}...)")

    # ---------------------------------------------------------
    # 대시보드 화면 그리기
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
            
            # 총계 계산
            num_cols = [c for c in pivot_stock.columns if c not in ['품목코드', '품목명']]
            pivot_stock['총재고'] = pivot_stock[num_cols].sum(axis=1)

            # 상단 지표
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
                st.dataframe(pivot_stock, use_container_width=True, height=500, hide_index=True)
        else:
            st.info("재고 데이터를 업로드해주세요.")

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
            
            col_s1, col_s2 = st.columns([1, 1])
            with col_s1:
                st.subheader("🏆 많이 팔린 상품 TOP 5")
                top_sales = pivot_sales.sort_values(by='총판매량', ascending=False).head(5)
                st.bar_chart(top_sales.set_index('품목명')['총판매량'], color="#1E90FF")
            
            with col_s2:
                 st.subheader("상세 판매 내역")
                 st.dataframe(pivot_sales, use_container_width=True, hide_index=True)
        else:
            st.info("판매 데이터를 업로드해주세요.")

else:
    st.info("👈 왼쪽 사이드바에 엑셀 파일들을 드래그해서 넣어주세요.")
