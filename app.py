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
# 함수: 엑셀에서 '진짜 헤더' 위치를 점수로 찾기 (가장 중요!)
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
        qty_keywords = ["수량", "재고", "가용재고", "장부재고", "출고", "매출", "출고(E)", "주문수량"]

        # 2. 각 줄을 검사해서 점수를 매깁니다.
        for idx, row in df_preview.iterrows():
            row_str = row.astype(str).values
            score = 0
            
            # 해당 줄에 '코드' 관련 단어가 있으면 1점 추가
            if any(k in s for s in row_str for k in code_keywords): score += 1
            # 해당 줄에 '품명' 관련 단어가 있으면 1점 추가
            if any(k in s for s in row_str for k in name_keywords): score += 1
            # 해당 줄에 '수량' 관련 단어가 있으면 1점 추가
            if any(k in s for s in row_str for k in qty_keywords): score += 1
            
            # 점수가 가장 높은 줄을 기억합니다 (진짜 헤더일 확률이 높음)
            if score > max_score:
                max_score = score
                best_row_idx = idx
        
        # 3. 점수가 0점이면 표를 못 찾은 것
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
        
        # 1. 스마트하게 엑셀 읽기 (점수 기반)
        df, error_msg = find_header_and_load(file)
        
        if df is None:
            st.error(f"❌ {filename} 읽기 실패: {error_msg}")
            continue

        # 2. 컬럼 매칭 (번역)
        cols = df.columns
        
        # 품목코드 찾기 (우선순위: 바코드 > 품목코드 > 내부코드)
        col_code = find_column_name(cols, ['바코드', '품목코드', '상품코드', '내부코드', 'Code'])
        
        # 품목명 찾기
        col_name = find_column_name(cols, ['상품명 및 규격', '품목명', '품명', '상품명', '규격'])
        
        # 수량 찾기 (가온의 '출고(E)', '가용재고' 등을 찾기 위함)
        # 주의: '출고일자', '재고금액' 같은 건 피해야 함
        qty_candidates = ['가용재고', '출고(E)', '재고수량', '수량', '총재고', '출고수량', '매출수량']
        col_qty = None
        for key in qty_candidates:
            found = next((c for c in cols if key in str(c) and "일자" not in str(c) and "금액" not in str(c) and "단가" not in str(c)), None)
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
                clean_df['품목명'] = '이름없음' # 품명 없으면 임시로 채움
            
            clean_df = clean_df.rename(columns=rename_map)
            clean_df['업체'] = company
            
            # 수량 숫자로 변환 (콤마 제거, 문자 제거)
            clean_df['수량'] = pd.to_numeric(clean_df['수량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

            # 0보다 큰 수량만 가져올지 여부는 선택사항 (여기선 다 가져옴)
            
            # 파일명에 '판매'나 '매출'이 있으면 판매 리스트로, 아니면 재고로 분류
            if "판매" in filename or "매출" in filename:
                sales_list.append(clean_df[['품목코드', '품목명', '수량', '업체']])
            else:
                stock_list.append(clean_df[['품목코드', '품목명', '수량', '업체']])
        else:
            # 디버깅을 위해 찾은 컬럼들을 보여줌
            st.warning(f"⚠️ {filename}: 핵심 칸을 못 찾았습니다. (찾은 헤더: {list(cols)})")

    # ---------------------------------------------------------
    # 대시보드 화면 그리기
    # ---------------------------------------------------------
    
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
                st.dataframe(pivot_stock, use_container_width=True, height=500, hide_index=True)
        else:
            st.info("데이터가 없습니다.")

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
