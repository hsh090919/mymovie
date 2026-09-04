import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# =========================================================
# 1. Streamlit 페이지 기본 설정
# =========================================================
st.set_page_config(
    page_title="어제의 영화 박스오피스",
    page_icon="🎬",
    layout="wide"
)


# =========================================================
# 2. 한국 시간 기준으로 "어제" 날짜 계산
# =========================================================
def get_yesterday_korea():
    """
    배포 서버의 시간대와 관계없이
    한국 시간(Asia/Seoul)을 기준으로 어제 날짜를 계산합니다.

    반환값 예시:
    - API용: 20260903
    - 화면용: 2026-09-03
    """

    korea_now = datetime.now(ZoneInfo("Asia/Seoul"))
    yesterday = korea_now - timedelta(days=1)

    api_date = yesterday.strftime("%Y%m%d")
    display_date = yesterday.strftime("%Y-%m-%d")

    return api_date, display_date


# =========================================================
# 3. KOBIS API 호출
# =========================================================
@st.cache_data(ttl=3600)
def get_daily_boxoffice(target_date):
    """
    같은 날짜를 다시 조회할 경우
    1시간(3600초) 동안 결과를 캐시에 저장합니다.

    즉, 같은 날짜를 여러 번 새로고침해도
    매번 API를 호출하지 않도록 합니다.
    """

    # Streamlit Cloud Secrets에서 인증키 불러오기
    # 코드 안에는 실제 인증키를 작성하지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_date
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 상태 코드 오류 확인
        response.raise_for_status()

        data = response.json()

        # -------------------------------------------------
        # KOBIS API는 인증키가 틀려도 HTTP 200을 줄 수 있으므로
        # faultInfo가 있는지 별도로 확인해야 합니다.
        # -------------------------------------------------
        if "faultInfo" in data:
            return {
                "success": False,
                "message": (
                    "KOBIS API에서 오류 정보를 반환했습니다. "
                    "Streamlit Cloud의 Secrets에 저장한 "
                    "KOBIS_KEY가 올바른지 확인해 주세요."
                )
            }

        # boxOfficeResult 확인
        if "boxOfficeResult" not in data:
            return {
                "success": False,
                "message": (
                    "API 응답에 boxOfficeResult 정보가 없습니다. "
                    "API 주소와 요청 형식을 확인해 주세요."
                )
            }

        result = data["boxOfficeResult"]

        # 일별 박스오피스 목록 가져오기
        movie_list = result.get("dailyBoxOfficeList", [])

        # 영화 목록이 비어 있는 경우
        if not movie_list:
            return {
                "success": False,
                "message": (
                    "조회된 영화 목록이 없습니다. "
                    "조회 날짜가 올바른지, 해당 날짜의 박스오피스가 "
                    "집계되었는지 확인해 주세요."
                )
            }

        return {
            "success": True,
            "data": movie_list
        }

    # 네트워크 오류
    except requests.exceptions.RequestException:
        return {
            "success": False,
            "message": (
                "KOBIS API에 연결하지 못했습니다. "
                "인터넷 연결과 API 서버 상태를 확인한 뒤 다시 시도해 주세요."
            )
        }

    # JSON 형식 오류
    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API 응답을 읽는 중 오류가 발생했습니다. "
                "API 서버가 정상적인 JSON 데이터를 반환하는지 확인해 주세요."
            )
        }

    # Secrets 설정 오류 등 그 외 오류
    except Exception:
        return {
            "success": False,
            "message": (
                "데이터를 불러오는 중 오류가 발생했습니다. "
                "Streamlit Cloud Secrets의 KOBIS_KEY 설정과 "
                "API 인증키 상태를 확인해 주세요."
            )
        }


# =========================================================
# 4. 화면 제목
# =========================================================
st.title("🎬 어제의 영화 박스오피스")

api_date, display_date = get_yesterday_korea()

st.caption(
    f"조회 날짜: {display_date} "
    f"(한국 시간 기준)"
)


# =========================================================
# 5. API 데이터 불러오기
# =========================================================
result = get_daily_boxoffice(api_date)


# =========================================================
# 6. 오류가 발생한 경우 안내 메시지 표시
# =========================================================
if not result["success"]:

    st.error("박스오피스 데이터를 불러오지 못했습니다.")

    st.warning(result["message"])

    st.subheader("확인해 볼 사항")

    st.markdown(
        """
        1. **Streamlit Cloud Secrets에 `KOBIS_KEY`가 등록되어 있는지**
        2. **KOBIS 인증키가 올바르고 사용 가능한 상태인지**
        3. **조회 날짜의 박스오피스 데이터가 집계되었는지**
        4. **KOBIS Open API 서버가 정상적으로 동작하는지**
        5. **네트워크 연결 상태가 정상인지**
        """
    )

    st.stop()


# =========================================================
# 7. API 데이터를 pandas DataFrame으로 변환
# =========================================================
df = pd.DataFrame(result["data"])


# =========================================================
# 8. 문자열로 전달되는 숫자를 실제 숫자로 변환
# =========================================================
# API에서는 숫자도 문자열로 전달되므로
# 정렬과 그래프를 위해 숫자형으로 바꿉니다.

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
# 9. 순위 기준으로 정렬
# =========================================================
df = df.sort_values(
    by="rank",
    ascending=True
).reset_index(drop=True)


# =========================================================
# 10. 1위 영화 정보 표시
# =========================================================
first_movie = df.iloc[0]

st.divider()

st.subheader("🥇 오늘의 1위 영화")

st.markdown(f"### {first_movie['movieNm']}")

# 1위 영화의 주요 지표 3개를 카드 형태로 표시
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="어제 관객수",
        value=f"{int(first_movie['audiCnt']):,}명"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{int(first_movie['audiAcc']):,}명"
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{int(first_movie['scrnCnt']):,}개"
    )


# =========================================================
# 11. 관객수 상위 5편 막대그래프
# =========================================================
st.divider()

st.subheader("📊 관객수 상위 5편")

# 관객수 기준으로 내림차순 정렬 후 상위 5개 선택
top5_df = df.nlargest(
    5,
    "audiCnt"
).copy()

# 영화명을 인덱스로 설정하여 Streamlit 막대그래프에 사용
chart_df = top5_df.set_index("movieNm")[["audiCnt"]]

st.bar_chart(chart_df)


# =========================================================
# 12. 전체 박스오피스 표
# =========================================================
st.divider()

st.subheader("📋 전체 박스오피스 순위")


# 화면에 표시할 열만 선택
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
# 13. 보기 좋은 숫자 형식으로 변경
# =========================================================
# DataFrame의 실제 숫자형 데이터는 그대로 유지하고
# 화면 표시용으로 쉼표를 추가합니다.

table_df["rank"] = table_df["rank"].astype(int)

table_df["audiCnt"] = table_df["audiCnt"].apply(
    lambda x: f"{int(x):,}"
)

table_df["audiAcc"] = table_df["audiAcc"].apply(
    lambda x: f"{int(x):,}"
)

table_df["scrnCnt"] = table_df["scrnCnt"].apply(
    lambda x: f"{int(x):,}"
)


# =========================================================
# 14. 컬럼 이름을 한국어로 변경
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
# 15. 표 출력
# =========================================================
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# =========================================================
# 16. 하단 안내
# =========================================================
st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS) Open API"
)
