import streamlit as st
import pandas as pd
import io

# 페이지 설정
st.set_page_config(page_title="물류 재고 통합 시스템", layout="wide")

st.title("📦 물류 재고 통합 현황판")
st.markdown("엑셀 파일을 업로드하면 4개 업체를 자동으로 통합하여 보여줍니다.")

# 파일 업로드 기능
uploaded_files = st.file_uploader("엑셀 파일들을 모두 이곳에 드래그하세요 (여러 개 가능)", 
                                  accept_multiple_files=True, type=['xlsx', 'csv'])

if uploaded_files:
    # 데이터 담을 그릇 준비
    all_data = []
    
    # 업로드된 파일 하나씩 읽기
    for file in uploaded_files:
        try:
            # 엑셀 파일 읽기 (헤더 처리: 1행이 제목이라고 가정)
            df = pd.read_excel(file)
            
            # 파일 이름에서 업체명 추측 (예: '하은_재고.xlsx' -> '하은')
            filename = file.name
            company_name = "기타"
            if "하은" in filename: company_name = "하은"
            elif "한국" in filename: company_name = "한국"
            elif "가온" in filename: company_name = "가온"
            elif "다이소" in filename: company_name = "다이소"
            
            # 필요한 컬럼만 남기기 (품목코드, 품명, 수량)
            # 엑셀의 실제 컬럼명을 찾아내는 로직
            col_code = [c for c in df.columns if "코드" in c][0] # '코드'가 들어간 컬럼 찾기
            col_name = [c for c in df.columns if "품명" in c or "규격" in c][0] # '품명' 들어간 컬럼
            col_qty = [c for c in df.columns if "수량" in c or "재고" in c][0] # '수량' 들어간 컬럼
            
            # 데이터 정리
            df_clean = df[[col_code, col_name, col_qty]].copy()
            df_clean.columns = ['품목코드', '품목명', '수량'] # 컬럼 이름 통일
            df_clean['업체'] = company_name # 업체명 표시
            
            all_data.append(df_clean)
            
        except Exception as e:
            st.error(f"{file.name} 파일을 읽는데 실패했습니다. 엑셀 형식을 확인해주세요. ({e})")

    # 데이터가 있으면 통합 시작
    if all_data:
        merged_df = pd.concat(all_data)
        
        # 피벗 테이블 생성 (가로로 펼치기)
        final_df = merged_df.pivot_table(index=['품목코드', '품목명'], 
                                         columns='업체', 
                                         values='수량', 
                                         aggfunc='sum', 
                                         fill_value=0).reset_index()
        
        # 합계 컬럼 추가
        cols = [c for c in final_df.columns if c not in ['품목코드', '품목명']]
        final_df['총합계'] = final_df[cols].sum(axis=1)
        
        # 화면에 보여주기
        st.success("✅ 통합 완료!")
        st.dataframe(final_df, use_container_width=True, height=800)
        
        # 엑셀 다운로드 버튼
        # (생략 가능)