import streamlit as st
import pandas as pd

# 페이지 설정 (넓은 화면 사용)
st.set_page_config(page_title="물류 재고 통합 시스템", layout="wide")

# 제목 및 헤더 디자인
st.title("📦 물류 재고 통합 대시보드")
st.markdown("---")

# 사이드바 (파일 업로드 창을 왼쪽으로 뺌)
with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded_files = st.file_uploader(
        "엑셀 파일들을 모두 드래그하세요", 
        accept_multiple_files=True, 
        type=['xlsx', 'csv']
    )
    st.info("💡 팁: 여러 파일을 한꺼번에 선택해서 놓으세요.")

if uploaded_files:
    # 데이터 처리 로직
    all_data = []
    
    for file in uploaded_files:
        try:
            df = pd.read_excel(file)
            
            # 업체명 추측 (파일명 기반)
            filename = file.name
            company_name = "기타"
            if "하은" in filename: company_name = "하은"
            elif "한국" in filename: company_name = "한국"
            elif "가온" in filename: company_name = "가온"
            elif "다이소" in filename: company_name = "다이소"
            
            # 컬럼 찾기 (유연하게)
            col_code = [c for c in df.columns if "코드" in c][0]
            col_name = [c for c in df.columns if "품명" in c or "규격" in c][0]
            col_qty = [c for c in df.columns if "수량" in c or "재고" in c][0]
            
            # 필요한 데이터만 추출
            df_clean = df[[col_code, col_name, col_qty]].copy()
            df_clean.columns = ['품목코드', '품목명', '수량']
            df_clean['업체'] = company_name
            
            all_data.append(df_clean)
            
        except Exception as e:
            st.error(f"❌ {file.name} 읽기 실패: {e}")

    # 데이터 통합 및 대시보드 표시
    if all_data:
        merged_df = pd.concat(all_data)
        
        # 피벗 테이블 (업체별 가로 정렬)
        final_df = merged_df.pivot_table(
            index=['품목코드', '품목명'], 
            columns='업체', 
            values='수량', 
            aggfunc='sum', 
            fill_value=0
        ).reset_index()
        
        # 총 합계 계산
        numeric_cols = [c for c in final_df.columns if c not in ['품목코드', '품목명']]
        final_df['총재고'] = final_df[numeric_cols].sum(axis=1)
        
        # --------------------
        # 📊 대시보드 화면 시작
        # --------------------
        
        # 1. 핵심 지표 (Metrics) - 맨 위에 큰 숫자로 보여줌
        total_items = len(final_df)
        total_qty = final_df['총재고'].sum()
        top_product = final_df.sort_values(by='총재고', ascending=False).iloc[0]['품목명']

        col1, col2, col3 = st.columns(3)
        col1.metric("📦 전체 품목 수", f"{total_items} 개")
        col2.metric("📊 총 재고 수량", f"{total_qty:,.0f} 개")
        col3.metric("🏆 최다 보유 품목", top_product)
        
        st.markdown("---")

        # 2. 그래프 영역 (업체별 재고 비교)
        col_chart1, col_chart2 = st.columns([1, 1]) # 화면을 반반 나눔
        
        with col_chart1:
            st.subheader("🏭 업체별 재고 점유율")
            # 업체별 총 수량 계산
            company_sums = final_df[numeric_cols].sum()
            st.bar_chart(company_sums, color="#FF4B4B") # 빨간색 그래프

        with col_chart2:
            st.subheader("🥇 재고 많은 품목 TOP 5")
            # 재고 많은 순서대로 5개만 자르기
            top_5 = final_df[['품목명', '총재고']].sort_values(by='총재고', ascending=False).head(5)
            top_5 = top_5.set_index('품목명') # 그래프 축 설정을 위해 인덱스 변경
            st.bar_chart(top_5, color="#1E90FF") # 파란색 그래프

        st.markdown("---")

        # 3. 상세 데이터 표
        st.subheader("📋 상세 재고 현황표")
        st.dataframe(
            final_df, 
            use_container_width=True, 
            height=500,
            hide_index=True
        )

    else:
        st.warning("데이터가 없습니다. 엑셀 파일을 업로드해주세요.")

else:
    st.info("👈 왼쪽 사이드바에서 엑셀 파일을 업로드하면 대시보드가 나타납니다.")
