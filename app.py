import streamlit as st
import pandas as pd
import plotly.express as px

# 페이지 설정
st.set_page_config(page_title="통합 물류 분석 시스템", layout="wide")

st.title("📈 물류 통합 데이터 분석 시스템 (시트명 자동 분류)")
st.markdown("""
**사용 방법:**
1. 여러 시트가 들어있는 **엑셀 파일(.xlsx) 1개**를 업로드하세요.
2. **시트 이름**에 **'매출'** 또는 **'재고'**라는 글자만 있으면 알아서 분류합니다.
   (예: `하은매출`, `1월 매출현황`, `한국재고`, `Total재고` 등)
""")

# 사이드바: 파일 업로드
with st.sidebar:
    st.header("📂 엑셀 파일 업로드")
    uploaded_file = st.file_uploader("시트가 여러 개인 엑셀 파일을 넣으세요", type=['xlsx', 'xls'])
    st.info("💡 시트 이름이 '매출'이면 판매량으로, '재고'면 재고량으로 자동 인식합니다.")

if uploaded_file:
    try:
        # 1. 엑셀 파일의 모든 시트 읽어오기
        # sheet_name=None을 주면 모든 시트를 딕셔너리 형태로 가져옵니다.
        all_sheets = pd.read_excel(uploaded_file, sheet_name=None)
        
        stock_list = []
        sales_list = []
        
        # 2. 시트 하나씩 검사
        for sheet_name, df in all_sheets.items():
            # 데이터가 비어있으면 건너뜀
            if df.empty: continue
            
            # 컬럼 이름 공백 제거
            df.columns = df.columns.astype(str).str.replace(' ', '')
            cols = df.columns
            
            # 필수 컬럼 찾기 (유연하게)
            col_date = next((c for c in cols if "일자" in c or "날짜" in c or "Date" in c), None)
            col_company = next((c for c in cols if "업체" in c or "거래처" in c or "회사" in c), None)
            col_code = next((c for c in cols if "코드" in c), None)
            col_name = next((c for c in cols if "품명" in c or "상품" in c or "규격" in c), None)
            col_qty = next((c for c in cols if "수량" in c or "재고" in c or "매출" in c or "출고" in c), None)
            
            # 필수 데이터가 있는 시트만 처리
            if col_code and col_qty:
                # 데이터 전처리
                clean_df = df.copy()
                
                # 날짜 변환 (날짜 컬럼이 있으면)
                if col_date:
                    clean_df[col_date] = pd.to_datetime(clean_df[col_date], errors='coerce')
                
                # 수량 숫자 변환
                if clean_df[col_qty].dtype == object:
                    clean_df[col_qty] = pd.to_numeric(clean_df[col_qty].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                
                # 컬럼명 통일 (분석을 위해)
                rename_map = {
                    col_code: '품목코드',
                    col_name: '품목명' if col_name else '품목명', # 품명 없으면 유지
                    col_qty: '수량',
                    col_company: '업체명' if col_company else '업체명',
                    col_date: '일자' if col_date else '일자'
                }
                clean_df = clean_df.rename(columns=rename_map)
                
                # 업체명 컬럼이 없으면 '기타'로 채우거나 시트명에서 추측
                if '업체명' not in clean_df.columns:
                    clean_df['업체명'] = sheet_name  # 시트 이름을 업체명으로 사용
                
                # 날짜 컬럼이 없으면 오늘 날짜나 임의 날짜 (재고의 경우)
                if '일자' not in clean_df.columns:
                     clean_df['일자'] = pd.Timestamp.now()

                # 필요한 컬럼만 남기기
                final_cols = ['일자', '업체명', '품목코드', '품목명', '수량']
                # 없는 컬럼은 빈 값으로라도 채워서 오류 방지
                for c in final_cols:
                    if c not in clean_df.columns: clean_df[c] = ""
                
                target_df = clean_df[final_cols].copy()

                # ---------------------------------------------------
                # ⭐ 핵심: 시트 이름(sheet_name)으로 구분 ⭐
                # ---------------------------------------------------
                if "매출" in sheet_name or "판매" in sheet_name or "출고" in sheet_name:
                    sales_list.append(target_df)
                elif "재고" in sheet_name:
                    stock_list.append(target_df)
                else:
                    # 시트 이름에 구분이 없으면 데이터 내부 확인 (혹시 모르니)
                    pass 
            else:
                # 핵심 컬럼(코드, 수량)이 없는 시트는 무시 (설명 시트 등)
                continue

        # 3. 데이터 합치기
        df_sales = pd.concat(sales_list) if sales_list else pd.DataFrame()
        df_stock = pd.concat(stock_list) if stock_list else pd.DataFrame()

        # ---------------------------------------------------------
        # 📊 대시보드 화면 그리기
        # ---------------------------------------------------------
        
        tab1, tab2 = st.tabs(["💰 매출(판매) 추이 분석", "📦 현재 재고 현황"])

        # [탭 1] 매출 분석
        with tab1:
            if not df_sales.empty:
                # 날짜가 제대로 된 데이터만 필터링
                df_sales = df_sales[pd.notnull(df_sales['일자'])]
                
                min_date = df_sales['일자'].min()
                max_date = df_sales['일자'].max()
                
                st.success(f"📅 분석 기간: {min_date.date()} ~ {max_date.date()} (총 {len(df_sales):,} 건)")
                
                # 월별 매출 집계
                df_sales['년월'] = df_sales['일자'].dt.to_period('M').astype(str)
                
                monthly_trend = df_sales.pivot_table(
                    index='년월', columns='업체명', values='수량', aggfunc='sum', fill_value=0
                )
                
                st.markdown("### 📈 월별 매출 수량 추이")
                fig = px.line(monthly_trend, markers=True, title="업체별 월간 매출 변화")
                st.plotly_chart(fig, use_container_width=True)
                
                st.divider()

                c1, c2 = st.columns([1, 1])
                with c1:
                    st.markdown("### 🏆 최다 매출 품목 TOP 10")
                    top_items = df_sales.groupby('품목명')['수량'].sum().sort_values(ascending=False).head(10)
                    st.bar_chart(top_items, color="#FF4B4B")
                    
                with c2:
                    st.markdown("### 🔢 월별 데이터 상세표")
                    st.dataframe(monthly_trend, use_container_width=True)

            else:
                st.warning("⚠️ 매출 데이터를 찾을 수 없습니다. 시트 이름에 **'매출'**이 포함되어 있는지 확인해주세요.")

        # [탭 2] 재고 현황
        with tab2:
            if not df_stock.empty:
                # 재고 합산
                stock_summary = df_stock.pivot_table(
                    index=['품목코드', '품목명'], 
                    columns='업체명', 
                    values='수량', 
                    aggfunc='sum', 
                    fill_value=0
                ).reset_index()
                
                # 총재고
                num_cols = [c for c in stock_summary.columns if c not in ['품목코드', '품목명']]
                stock_summary['총재고'] = stock_summary[num_cols].sum(axis=1)
                
                st.metric("📦 현재 총 재고 수량", f"{stock_summary['총재고'].sum():,.0f} 개")
                st.dataframe(stock_summary, use_container_width=True, height=600, hide_index=True)
            else:
                st.info("재고 데이터가 없습니다. 시트 이름에 **'재고'**가 포함되어 있는지 확인해주세요.")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
