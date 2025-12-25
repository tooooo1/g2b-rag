# 트러블슈팅 가이드

> 이 프로젝트를 개발하면서 발생한 에러들과 해결 과정을 정리한 문서.
> 같은 문제를 겪을 다른 개발자(또는 미래의 나)를 위해 작성.

---

## 목차

1. [API 404 Not Found](#1-api-404-not-found)
2. [API 응답 형식 오류](#2-api-응답-형식-오류)
3. [입력범위값 초과 에러](#3-입력범위값-초과-에러)
4. [API 필드명 불일치](#4-api-필드명-불일치)
5. [ChromaDB 배치 크기 초과](#5-chromadb-배치-크기-초과)
6. [Anthropic API 버전/크레딧 문제](#6-anthropic-api-버전크레딧-문제)
7. [ChromaDB 텔레메트리 에러](#7-chromadb-텔레메트리-에러)
8. [LLM 한국어 품질 문제](#8-llm-한국어-품질-문제)
9. [핵심 개념 정리](#9-핵심-개념-정리)

---

## 1. API 404 Not Found

### 증상
```
API 오류: 404 Client Error: Not Found for url:
https://apis.data.go.kr/1230000/as/ScsbidInfoService?serviceKey=...
```

### 원인
REST API는 보통 **베이스 URL + 오퍼레이션명** 구조를 따른다.

```
[베이스 URL]                                    [오퍼레이션]
https://apis.data.go.kr/1230000/as/ScsbidInfoService/getScsbidListSttusServc
                                                      ↑ 이 부분이 없었음
```

나라장터 API는 4개 분야별로 오퍼레이션이 다름:
- `getScsbidListSttusServc` - 용역
- `getScsbidListSttusThng` - 물품
- `getScsbidListSttusCnstwk` - 공사
- `getScsbidListSttusFrgcpt` - 외자

### 해결
```python
# 수정 전
API_URL = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"
resp = requests.get(API_URL, params=params)

# 수정 후
API_BASE = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"
url = f"{API_BASE}/{operation}"  # 오퍼레이션명 추가
resp = requests.get(url, params=params)
```

---

## 2. API 응답 형식 오류

### 증상
```
응답 형식 오류
(API 호출은 성공하지만 데이터 파싱 실패)
```

### 원인
날짜 파라미터 형식이 API 요구사항과 달랐음.

```
API 요구: YYYYMMDDHHMM (예: 202512010000)
내가 보낸: YYYYMMDD (예: 20251201)
```

API 문서에 명시되어 있었지만 처음에 놓침:
> inqryBgnDt: 검색하고자하는 시작일시 'YYYYMMDDHHMM'

### 해결
```python
# 수정 전
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

# 수정 후
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d") + "0000"
end_date = datetime.now().strftime("%Y%m%d%H%M")
```

---

## 3. 입력범위값 초과 에러

### 증상
```json
{
  "header": {
    "resultCode": "07",
    "resultMsg": "입력범위값 초과 에러"
  }
}
```

### 원인
**공공 API의 서버 부하 방지 정책**

대부분의 공공 API는 무료로 제공되기 때문에 남용 방지를 위해 제한을 둔다:
- 일일 호출 횟수 제한 (예: 1,000건/일)
- 한 번에 조회 가능한 기간 제한 (예: 30일)
- 페이지당 최대 건수 제한 (예: 100건)

나라장터 API는 **최대 30일**까지만 한 번에 조회 가능:
```
30일: ✅ 성공
31일: ❌ 입력범위값 초과 에러
```

이 제한은 API 문서에 명시되어 있지 않아서 직접 테스트로 확인함.

### 해결
30일씩 나눠서 여러 번 호출하는 방식으로 우회:

```python
# 90일 = 30일 x 3번 호출
TOTAL_DAYS = 90

periods = []
for i in range(0, TOTAL_DAYS, 30):
    end = datetime.now() - timedelta(days=i)
    start = end - timedelta(days=30)
    periods.append((start, end))

# periods = [(60일전~90일전), (30일전~60일전), (오늘~30일전)]
```

---

## 4. API 필드명 불일치

### 증상
```
낙찰금액, 낙찰률이 0으로 나옴
```

### 원인
API 문서와 실제 응답의 필드명이 다름. 또는 더미 데이터로 개발 후 실제 API 연동할 때 필드명 확인 안 함.

```
예상한 필드명     실제 API 필드명
─────────────────────────────────
succsBidAmt   →  sucsfbidAmt
succsBidRate  →  sucsfbidRate
ntceInsttNm   →  dminsttNm (수요기관명)
presmptPrce   →  (해당 API에 없음)
```

### 해결
실제 API 응답을 찍어보고 필드명 확인 후 수정:

```python
# 수정 전
"succsBidAmt": item.get("succsBidAmt", "0"),
"succsBidRate": item.get("succsBidRate", ""),

# 수정 후
"sucsfbidAmt": item.get("sucsfbidAmt", "0"),
"sucsfbidRate": item.get("sucsfbidRate", ""),
```

### 교훈
- 더미 데이터로 개발할 때도 실제 API 스펙과 동일하게 만들기
- API 연동 전에 실제 응답 한 번 찍어보기

---

## 5. ChromaDB 배치 크기 초과

### 증상
```
ValueError: Batch size 9103 exceeds maximum batch size 5461
```

### 원인
**벡터 DB의 메모리 관리 제약**

벡터 임베딩은 고차원 데이터라 메모리를 많이 사용한다:

```
jhgan/ko-sroberta-multitask 모델 기준:
- 임베딩 차원: 768
- 데이터 타입: float32 (4바이트)
- 1개 임베딩 크기: 768 × 4 = 3,072 바이트 ≈ 3KB

9,103개 한 번에 저장하려면:
- 9,103 × 3KB ≈ 27MB 메모리 필요
- + 인덱싱 오버헤드
- + SQLite 트랜잭션 오버헤드
```

ChromaDB는 SQLite 기반이라 대용량 트랜잭션에 제약이 있음.
안정성을 위해 배치 크기를 5,461개로 제한.

### 해결
5,000개씩 나눠서 저장:

```python
# 수정 전
collection.add(
    embeddings=embeddings,  # 9,103개 한 번에
    documents=documents,
    metadatas=metadatas,
    ids=ids
)

# 수정 후
db_batch_size = 5000
for i in range(0, len(embeddings), db_batch_size):
    end = min(i + db_batch_size, len(embeddings))
    collection.add(
        embeddings=embeddings[i:end],
        documents=documents[i:end],
        metadatas=metadatas[i:end],
        ids=ids[i:end]
    )
```

---

## 6. Anthropic API 버전/크레딧 문제

### 증상 1: 버전 호환성 문제
```
Client.__init__() got an unexpected keyword argument 'proxies'
```

### 원인
anthropic 라이브러리 버전이 오래됨. httpx 라이브러리와 호환성 문제.

### 해결
```bash
pip install --upgrade anthropic httpx
# 0.7.8 → 0.75.0 업그레이드
```

### 증상 2: 크레딧 부족
```
anthropic.BadRequestError: Error code: 400
Your credit balance is too low to access the Anthropic API.
```

### 원인
Claude API는 유료 서비스. 크레딧이 없으면 호출 불가.

### 해결
- **방법 1**: Anthropic 콘솔에서 크레딧 충전 (https://console.anthropic.com/settings/billing)
- **방법 2**: 무료 대안인 Ollama 사용 (로컬 LLM)

```bash
# Ollama 설치 및 모델 다운로드
brew install ollama
ollama pull gemma3
```

---

## 7. ChromaDB 텔레메트리 에러

### 증상
```
Failed to send telemetry event ClientStartEvent: capture() takes 1 positional argument but 3 were given
```

### 원인
ChromaDB가 사용하는 posthog 라이브러리의 버전 충돌. 텔레메트리(사용 통계) 전송 시 에러 발생.

### 해결
posthog를 모킹하여 에러 억제:

```python
import os
import sys

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["POSTHOG_DISABLED"] = "1"

# posthog 모킹
class FakePosthog:
    def capture(self, *args, **kwargs): pass
    def identify(self, *args, **kwargs): pass
    def __getattr__(self, name): return lambda *a, **k: None

sys.modules["posthog"] = FakePosthog()

# 이후 chromadb import
import chromadb
```

### 교훈
라이브러리 의존성 충돌은 흔한 문제. 에러가 기능에 영향 없으면 억제하는 것도 방법.

---

## 8. LLM 한국어 품질 문제

### 증상
```
LLM 응답에 영어, 일본어, 중국어 등이 섞여서 출력됨:
"chattingbot은 chatbot과 유사한 기능을 제공하는 AI 系统입니다"
```

### 원인
**임베딩 모델과 LLM은 역할이 다름:**

| 구분 | 임베딩 모델 | LLM |
|------|-------------|-----|
| 모델 | jhgan/ko-sroberta-multitask | llama3.2 |
| 역할 | 텍스트 → 벡터 | 텍스트 → 텍스트 |
| 한국어 | 특화됨 | 범용 (한국어 약함) |

임베딩 모델은 한국어 특화 모델을 썼지만, LLM은 범용 모델(llama3.2)을 써서 한국어 품질이 낮았음.

### 해결
한국어 성능이 좋은 LLM으로 교체:

```bash
# gemma3 다운로드 (한국어 성능 우수)
ollama pull gemma3
```

```python
# chat.py에서 모델 변경
OLLAMA_MODEL = "gemma3"  # llama3.2 → gemma3
```

### 결과 비교

**llama3.2 (변경 전):**
```
"chattingbot은 chatbot과 유사한 기능을 제공하는 AI 系统입니다"
"사용자가 검색 결과가있으면, saya sẽ tìm kiếm relevant한 정보를..."
```

**gemma3 (변경 후):**
```
"저는 나라장터 조달 사업 검색 도우미입니다. 조달 사업 검색 결과와
사용자 입력이 AI 관련 사업과 관련된 경우, 해당 사업을 요약하고
유사한 이유를 분석해 드립니다."
```

### 교훈
- 임베딩 모델과 LLM은 분리해서 최적화
- 한국어 서비스면 한국어 특화/성능 좋은 모델 선택

---

## 9. 핵심 개념 정리

### REST API 엔드포인트 구조
```
https://api.example.com/v1/users/123/posts
└─────── 베이스 ──────┘ └버전┘└리소스┘└ID┘└하위리소스┘
```

대부분의 REST API는 계층 구조를 따름. 베이스 URL만으로는 404 에러.

### 공공 API Rate Limiting
무료 API는 남용 방지를 위해 제한을 둠:
- **시간당/일일 호출 제한**: 서버 부하 방지
- **기간 제한**: 대용량 데이터 한 번에 요청 방지
- **페이지 크기 제한**: 응답 크기 관리

우회 방법: 작은 단위로 나눠서 여러 번 호출

### 벡터 DB 메모리 관리
벡터 임베딩은 일반 텍스트보다 훨씬 큼:
- 텍스트 "AI 챗봇": 약 10바이트
- 임베딩 [0.1, 0.2, ...]: 768 × 4 = 3,072바이트

대용량 데이터는 배치로 나눠서 처리하는 것이 안전.

---

## 요약 테이블

| 에러 | 핵심 원인 | 해결 패턴 |
|------|----------|----------|
| 404 Not Found | 엔드포인트 구조 이해 부족 | API 문서에서 전체 URL 확인 |
| 응답 형식 오류 | 파라미터 포맷 불일치 | 문서의 샘플 데이터 형식 따르기 |
| 범위 초과 | API Rate Limiting | 작은 단위로 나눠서 호출 |
| 필드명 불일치 | 문서 vs 실제 차이 | 실제 응답 찍어보기 |
| 배치 초과 | 메모리 제약 | 배치 단위로 나눠서 저장 |
| API 버전 충돌 | 라이브러리 호환성 | pip upgrade로 최신 버전 |
| API 크레딧 부족 | 유료 서비스 | 무료 대안(Ollama) 사용 |
| 텔레메트리 에러 | 의존성 충돌 | 해당 모듈 모킹으로 억제 |
| LLM 한국어 품질 | 범용 모델 사용 | 한국어 특화 모델로 교체 |

---

*작성일: 2025-12-25*
*프로젝트: bid-price-assistant*
