import os

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["POSTHOG_DISABLED"] = "1"

import warnings
warnings.filterwarnings("ignore")

import logging
logging.getLogger("chromadb").setLevel(logging.CRITICAL)
logging.getLogger("posthog").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)

import requests
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

MODEL_NAME = "jhgan/ko-sroberta-multitask"
OLLAMA_MODEL = "gemma3"
TOP_K = 10
MIN_SIMILARITY = 0.60
MAX_RESULTS = 5

_model = None
_collection = None

def init():
    import threading
    import time

    global _model, _collection
    stop_event = threading.Event()

    def animate():
        dots = 0
        while not stop_event.is_set():
            print(f"\r모델 로딩 중{'.' * dots}   ", end="", flush=True)
            dots = (dots + 1) % 4
            time.sleep(0.3)

    t = threading.Thread(target=animate)
    t.start()

    _model = SentenceTransformer(MODEL_NAME)
    _collection = chromadb.PersistentClient(
        path="data/chroma",
        settings=Settings(anonymized_telemetry=False)
    ).get_collection(name="bidding")

    stop_event.set()
    t.join()
    print(f"\r벡터 DB 연결: {_collection.count()}개 문서")

def search(query):
    query_embedding = _model.encode([query])[0].tolist()
    results = _collection.query(query_embeddings=[query_embedding], n_results=TOP_K)

    filtered = {"metadatas": [[]], "distances": [[]]}
    count = 0

    for i, dist in enumerate(results["distances"][0]):
        similarity = 1 - dist
        if similarity >= MIN_SIMILARITY and count < MAX_RESULTS:
            filtered["metadatas"][0].append(results["metadatas"][0][i])
            filtered["distances"][0].append(dist)
            count += 1

    return filtered

CHAT_KEYWORDS = ["안녕", "뭐", "누구", "어떻게", "할 수", "도움", "헬프", "help", "hi", "hello"]

def is_chat_query(query):
    q = query.lower().strip()
    for kw in CHAT_KEYWORDS:
        if kw in q:
            return True
    return False

def build_prompt(query, metadatas, distances):
    if metadatas:
        context_lines = []
        for i, m in enumerate(metadatas):
            similarity = (1 - distances[i]) * 100
            line = f"- {m['bidNtceNm']} (기관: {m['dminsttNm']}, 유사도: {similarity:.0f}%)"
            context_lines.append(line)
        context = "\n".join(context_lines)
    else:
        context = "없음"

    is_chat = is_chat_query(query) and context == "없음"
    is_no_results = not is_chat_query(query) and context == "없음"

    if is_chat:
        return f"""<role>웰로비즈 나라장터 조달 사업 검색 도우미</role>

<user_input>{query}</user_input>

<instructions>
1. 친근하게 자기소개
2. 서비스 사용법 안내 (사업명 입력하면 유사 사업 검색)
</instructions>

<example>
"안녕하세요! 웰로비즈 조달 검색 도우미입니다. '서울시 도로공사'처럼 사업명을 입력하시면 유사한 조달 사업을 찾아드려요."
</example>

<output_format>2문장 이내, 한국어</output_format>"""

    elif is_no_results:
        return f"""검색어 "{query}"에 대한 유사 조달 사업을 찾지 못했습니다.

다음과 같이 응답하세요:
"'{query}' 관련 조달 사업을 찾지 못했습니다. 다른 키워드로 검색해보세요. (예: 'AI 챗봇', '도로 보수공사')"

한국어, 1-2문장"""

    else:
        return f"""<role>조달 사업 분석가</role>

<task>검색 결과의 공통점을 분석</task>

<data>
<query>{query}</query>
<results>
{context}
</results>
</data>

<instructions>
1. 위 검색 결과들의 공통된 특징을 파악
2. 발주 기관 특성, 사업 유형, 지역 등 공통점 분석
3. 개별 사업명 나열 금지 - 공통점만 언급
</instructions>

<examples>
검색어: "서울시 시설물" → "서울시 산하 기관에서 발주한 시설물 유지보수 및 관리 사업들입니다. 공조시설, 보행환경, 공원 관리 등 다양한 분야가 포함됩니다."
검색어: "AI 챗봇" → "공공기관의 AI 기반 서비스 구축 사업들입니다. 주로 민원 응대, 상담 자동화 목적으로 발주되었습니다."
</examples>

<output_format>2문장, 한국어, 분석만</output_format>"""

def respond(query, results):
    import json
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    prompt = build_prompt(query, metadatas, distances)

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": True},
        stream=True
    )

    print("\033[38;2;209;213;219m", end="")
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            if chunk.get("response"):
                print(chunk["response"], end="", flush=True)
            if chunk.get("done"):
                break
    print("\033[0m")

class Color:
    @staticmethod
    def rgb(r, g, b, text):
        return f"\033[38;2;{r};{g};{b}m{text}\033[0m"

    @staticmethod
    def bold(text):
        return f"\033[1m{text}\033[0m"

    # 색상 프리셋
    @staticmethod
    def title(text): return Color.rgb(255, 200, 87, text)      # 노란색
    @staticmethod
    def name(text): return Color.bold(Color.rgb(255, 255, 255, text))  # 흰색 볼드
    @staticmethod
    def org(text): return Color.rgb(156, 163, 175, text)       # 회색
    @staticmethod
    def price(text): return Color.rgb(74, 222, 128, text)      # 초록색
    @staticmethod
    def similarity(text): return Color.rgb(96, 165, 250, text) # 파란색
    @staticmethod
    def ai(text): return Color.rgb(192, 132, 252, text)        # 보라색
    @staticmethod
    def dim(text): return Color.rgb(107, 114, 128, text)       # 어두운 회색

def print_results(results, query):
    metadatas = results["metadatas"][0]
    distances = results.get("distances", [[]])[0]

    if not metadatas:
        return

    title = f"'{query}' 유사 사업 ({len(metadatas)}건)"
    print(f"\n{Color.title(title)}")
    print(Color.dim("─" * 60))

    total_bid_amt = 0

    for i, meta in enumerate(metadatas):
        similarity = (1 - distances[i]) * 100 if distances else 0
        bid_amt = int(meta.get("sucsfbidAmt", 0) or 0)
        bid_rate = meta.get("sucsfbidRate", "")
        total_bid_amt += bid_amt

        print(f"{Color.name(f'{i+1}. ' + meta['bidNtceNm'])}")
        print(f"   {Color.org('📍 ' + meta['dminsttNm'])}")
        if bid_amt:
            rate_str = f" ({bid_rate}%)" if bid_rate else ""
            print(f"   {Color.price(f'💰 {bid_amt:,}원' + rate_str)}")
        print(f"   {Color.similarity(f'📊 {similarity:.1f}%')}")
        print()

    if len(metadatas) > 1 and total_bid_amt:
        print(Color.dim("─" * 60))
        avg_bid = total_bid_amt // len(metadatas)
        print(Color.dim(f"평균 낙찰가: {avg_bid:,}원"))

def main():
    print()
    print(Color.title("━" * 50))
    print(Color.title("  🔍 웰로비즈 나라장터 조달 검색"))
    print(Color.title("━" * 50))
    print(Color.dim("사업명 입력 → 유사 사업 검색 | 'quit' 종료\n"))

    try:
        init()
    except Exception as e:
        print(f"초기화 실패: {e}")
        print("먼저 build_db.py를 실행하세요.")
        return

    print()

    while True:
        try:
            query = input(f"{Color.rgb(99, 102, 241, '검색')}: ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                break

            if not query:
                continue

            results = search(query)
            print_results(results, query)

            print(f"\n{Color.ai('[AI]')}")
            respond(query, results)
            print()

        except KeyboardInterrupt:
            break

    print("종료")

if __name__ == "__main__":
    main()
