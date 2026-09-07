import streamlit as st
import pandas as pd
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 1. 페이지 기본 설정
# =========================================================

st.set_page_config(
    page_title="어제의 영화 박스오피스",
    page_icon="🎬",
    layout="wide"
)


# =========================================================
# 2. 한국 시간 기준으로 어제 날짜 계산
# =========================================================

def get_yesterday_korea():
    """
    서버가 어느 나라에 있더라도
    한국 시간(Asia/Seoul)을 기준으로 어제 날짜를 계산합니다.
    """

    # 현재 한국 시간
    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))

    # 한국 시간 기준 어제
    yesterday = korea_now - timedelta(days=1)

    # KOBIS API 요청용 날짜
    # 예: 20260906
    api_date = yesterday.strftime("%Y%m%d")

    # 화면 표시용 날짜
    # 예: 2026-09-06
    display_date = yesterday.strftime("%Y-%m-%d")

    return api_date, display_date


# =========================================================
# 3. KOBIS API에서 박스오피스 데이터 가져오기
# =========================================================

@st.cache_data(ttl=3600)
def get_daily_boxoffice(target_date, api_key):
    """
    같은 날짜의 조회 결과를 1시간 동안 캐시에 저장합니다.

    target_date : 조회 날짜
    api_key     : KOBIS 인증키
    """

    # KOBIS 일별 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API 요청에 사용할 값
    params = {
        "key": api_key,
        "targetDt": target_date
    }

    try:
        # KOBIS API 요청
        response = requests.get(
            url,
            params=params,
            timeout=15
        )

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            "KOBIS API 서버에 연결하지 못했습니다.\n\n"
            f"네트워크 오류: {e}"
        )

    # =====================================================
    # HTTP 상태 코드 확인
    # =====================================================

    if response.status_code != 200:
        raise RuntimeError(
            "KOBIS API 요청에 실패했습니다.\n\n"
            f"HTTP 상태 코드: {response.status_code}"
        )

    # =====================================================
    # JSON 데이터로 변환
    # =====================================================

    try:
        data = response.json()

    except ValueError:
        raise RuntimeError(
            "KOBIS API가 정상적인 JSON 데이터를 반환하지 않았습니다."
        )

    # =====================================================
    # KOBIS faultInfo 오류 확인
    # =====================================================

    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있으므로
    # faultInfo를 반드시 확인해야 합니다.
    if "faultInfo" in data:

        fault = data["faultInfo"]

        # 오류 코드
        error_code = fault.get(
            "errorCode",
            "확인할 수 없음"
        )

        # 오류 메시지
        error_message = fault.get(
            "message",
            fault.get(
                "messageId",
                "오류 메시지가 제공되지 않았습니다."
            )
        )

        raise RuntimeError(
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            f"오류 코드: {error_code}\n"
            f"오류 메시지: {error_message}"
        )

    # =====================================================
    # boxOfficeResult 존재 여부 확인
    # =====================================================

    if "boxOfficeResult" not in data:
        raise RuntimeError(
            "API 응답에 boxOfficeResult가 없습니다.\n\n"
            "KOBIS API 응답 형식을 확인해 주세요."
        )

    boxoffice_result = data["boxOfficeResult"]

    # =====================================================
    # 영화 목록 가져오기
    # =====================================================

    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )

    # =====================================================
    # 영화 목록이 비어 있는 경우
    # =====================================================

    if not movie_list:
        raise RuntimeError(
            f"{target_date} 날짜의 박스오피스 영화 목록이 비어 있습니다.\n\n"
            "조회 날짜가 올바른지, 해당 날짜의 데이터가 "
            "KOBIS에 집계되었는지 확인해 주세요."
        )

    # 정상 데이터 반환
    return movie_list


# =========================================================
# 4. 화면 제목
# =========================================================

st.title("🎬 어제의 영화 박스오피스")


# =========================================================
# 5. 한국 시간 기준 어제 날짜 계산
# =========================================================

api_date, display_date = get_yesterday_korea()

st.caption(
    f"조회 날짜: {display_date} (한국 시간 기준)"
)


# =========================================================
# 6. Streamlit Secrets에서 인증키 가져오기
# =========================================================

try:

    # Secrets에 KOBIS_KEY가 있는지 확인
    if "KOBIS_KEY" not in st.secrets:

        st.error(
            "Streamlit Secrets에 KOBIS_KEY가 등록되어 있지 않습니다."
        )

        st.info(
            """
            Streamlit Cloud의 Settings → Secrets에서
            다음과 같이 설정해 주세요.

            KOBIS_KEY = "본인의_인증키"
            """
        )

        st.stop()

    # Secrets에서 인증키 가져오기
    # 혹시 앞뒤에 공백이 있으면 제거
    api_key = str(
        st.secrets["KOBIS_KEY"]
    ).strip()

    # 인증키가 비어 있는지 확인
    if not api_key:

        st.error(
            "KOBIS_KEY 값이 비어 있습니다."
        )

        st.stop()


except Exception as e:

    st.error(
        "Streamlit Secrets를 읽는 중 오류가 발생했습니다."
    )

    st.code(str(e))

    st.stop()


# =========================================================
# 7. KOBIS API 데이터 요청
# =========================================================

try:

    with st.spinner(
        "어제의 박스오피스 데이터를 불러오는 중입니다..."
    ):

        movie_list = get_daily_boxoffice(
            api_date,
            api_key
        )


except Exception as e:

    st.error(
        "박스오피스 데이터를 불러오지 못했습니다."
    )

    # 실제 오류 메시지 표시
    st.warning(str(e))

    # =====================================================
    # 사용자가 확인할 사항
    # =====================================================

    st.subheader("확인해 볼 사항")

    st.markdown(
        """
        1. **Streamlit Cloud → Settings → Secrets에 `KOBIS_KEY`가 있는지 확인**
        2. **KOBIS에서 발급받은 인증키를 정확하게 입력했는지 확인**
        3. **인증키 앞뒤에 불필요한 공백이나 다른 문자가 없는지 확인**
        4. **Secrets를 수정한 뒤 앱을 다시 실행했는지 확인**
        5. **KOBIS Open API 인증키가 정상적으로 활성화되어 있는지 확인**
        6. **화면에 표시되는 오류 코드와 오류 메시지 확인**
        """
    )

    # 오류 상세 정보
    with st.expander("오류 상세 정보 보기"):

        st.code(
            str(e),
            language="text"
        )

    # 이후 코드는 실행하지 않음
    st.stop()


# =========================================================
# 8. API 데이터를 DataFrame으로 변환
# =========================================================

df = pd.DataFrame(movie_list)


# =========================================================
# 9. 문자열 숫자를 실제 숫자로 변환
# =========================================================

# KOBIS API에서는 숫자도 문자열 형태로 전달됩니다.
# 정렬과 그래프를 위해 실제 숫자로 변환합니다.

numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]


for column in numeric_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


# =========================================================
# 10. 순위 기준 정렬
# =========================================================

df = df.sort_values(
    by="rank",
    ascending=True
).reset_index(
    drop=True
)


# =========================================================
# 11. 1위 영화 정보
# =========================================================

first_movie = df.iloc[0]

st.divider()

st.subheader("🥇 어제의 1위 영화")

st.markdown(
    f"## {first_movie['movieNm']}"
)


# =========================================================
# 12. 1위 영화 지표 카드 3개
# =========================================================

col1, col2, col3 = st.columns(3)


# ---------------------------------------------------------
# 어제 관객수
# ---------------------------------------------------------

with col1:

    st.metric(
        label="어제 관객수",
        value=f"{int(first_movie['audiCnt']):,}명"
    )


# ---------------------------------------------------------
# 누적 관객수
# ---------------------------------------------------------

with col2:

    st.metric(
        label="누적 관객수",
        value=f"{int(first_movie['audiAcc']):,}명"
    )


# ---------------------------------------------------------
# 스크린수
# ---------------------------------------------------------

with col3:

    st.metric(
        label="스크린수",
        value=f"{int(first_movie['scrnCnt']):,}개"
    )


# =========================================================
# 13. 관객수 상위 5편
# =========================================================

st.divider()

st.subheader("📊 관객수 상위 5편")


# 관객수를 기준으로 내림차순 정렬합니다.
# 관객수가 가장 많은 영화가 가장 먼저 오도록 합니다.
top5_df = (
    df.sort_values(
        by="audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)


# 그래프에 사용할 데이터입니다.
# 영화명을 그래프의 이름으로 사용합니다.
chart_df = top5_df.set_index(
    "movieNm"
)[["audiCnt"]]


# 관객수 많은 순서대로 막대그래프 출력
st.bar_chart(
    chart_df
)


# =========================================================
# 14. 전체 박스오피스 표
# =========================================================

st.divider()

st.subheader("📋 전체 박스오피스 순위")


# 표에 표시할 컬럼만 선택합니다.
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# =========================================================
# 15. 숫자 표시 형식 변경
# =========================================================

# 순위는 정수로 표시
table_df["rank"] = (
    table_df["rank"]
    .fillna(0)
    .astype(int)
)


# 관객수에 쉼표 추가
table_df["audiCnt"] = table_df["audiCnt"].apply(
    lambda x: f"{int(x):,}"
    if pd.notna(x)
    else "-"
)


# 누적관객수에 쉼표 추가
table_df["audiAcc"] = table_df["audiAcc"].apply(
    lambda x: f"{int(x):,}"
    if pd.notna(x)
    else "-"
)


# 스크린수에 쉼표 추가
table_df["scrnCnt"] = table_df["scrnCnt"].apply(
    lambda x: f"{int(x):,}"
    if pd.notna(x)
    else "-"
)


# =========================================================
# 16. 컬럼명을 한국어로 변경
# =========================================================

table_df = table_df.rename(
    columns={
        "rank": "순위",
        "movieNm": "영화명",
        "openDt": "개봉일",
        "audiCnt": "관객수",
        "audiAcc": "누적관객",
        "scrnCnt": "스크린수"
    }
)


# =========================================================
# 17. 전체 박스오피스 표 출력
# =========================================================

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# =========================================================
# 18. 데이터 출처
# =========================================================

st.caption(
    f"데이터 출처: 영화진흥위원회(KOBIS) Open API | "
    f"조회 기준일: {display_date}"
)
