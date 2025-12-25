import json
import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"

# 4개 분야 오퍼레이션
OPERATIONS = [
    "getScsbidListSttusServc",   # 용역
    "getScsbidListSttusThng",    # 물품
    "getScsbidListSttusCnstwk",  # 공사
    "getScsbidListSttusFrgcpt",  # 외자
]

# 설정: 수집할 총 기간 (30일 단위로 나눠서 호출)
TOTAL_DAYS = 90  # 90일치 수집 (30일 x 3회)

def fetch_api(api_key, operation, start_date, end_date, page=1, rows=100):
    """API 호출"""
    params = {
        "serviceKey": api_key,
        "pageNo": page,
        "numOfRows": rows,
        "type": "json",
        "inqryDiv": "1",
        "inqryBgnDt": start_date,
        "inqryEndDt": end_date,
    }

    try:
        url = f"{API_BASE}/{operation}"
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"API 오류: {e}")
        return None

def collect_from_api(api_key, max_pages=10):
    """API에서 데이터 수집 (4개 분야 x 30일 단위)"""
    all_items = []

    # 30일 단위로 기간 분할 (자정 기준, 중복 방지)
    periods = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for i in range(0, TOTAL_DAYS, 30):
        end = today - timedelta(days=i)
        start = end - timedelta(days=30)
        periods.append((
            start.strftime("%Y%m%d") + "0000",
            (end - timedelta(minutes=1)).strftime("%Y%m%d%H%M")
        ))

    print(f"수집 기간: 최근 {TOTAL_DAYS}일 ({len(periods)}개 구간)")

    for operation in OPERATIONS:
        op_name = operation.replace("getScsbidListSttus", "")
        print(f"\n[{op_name}] 수집 중...")

        for period_idx, (start_date, end_date) in enumerate(periods):
            print(f"  구간 {period_idx + 1}/{len(periods)}...")

            for page in range(1, max_pages + 1):
                data = fetch_api(api_key, operation, start_date, end_date, page)

                if not data:
                    break

                try:
                    items = data["response"]["body"]["items"]
                    if not items:
                        break
                    all_items.extend(items)

                    # 더 이상 데이터 없으면 다음 구간으로
                    total = data["response"]["body"].get("totalCount", 0)
                    if page * 100 >= total:
                        break
                except KeyError:
                    break

        print(f"  → 누적 {len(all_items)}개")

    return all_items

def save(data, path="data/bidding.json"):
    """데이터 저장"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {path} ({len(data)}개)")

def main():
    api_key = os.getenv("G2B_API_KEY")

    if not api_key:
        print("G2B_API_KEY가 설정되지 않았습니다.")
        print(".env 파일에 API 키를 입력하세요.")
        return

    print("API에서 데이터 수집 시도...")
    items = collect_from_api(api_key)

    if items:
        save(items)
    else:
        print("수집된 데이터가 없습니다.")

if __name__ == "__main__":
    main()