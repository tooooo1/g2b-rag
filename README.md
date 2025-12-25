# 나라장터 RAG

> 나라장터 낙찰 데이터 기반 RAG 파이프라인

```
Query → ko-sroberta (768d) → ChromaDB → gemma3 → Analysis
```

## Stack

| | |
|---|---|
| Embedding | `jhgan/ko-sroberta-multitask` |
| Vector DB | ChromaDB + cosine similarity |
| LLM | Ollama gemma3 (local) |

## Usage

```bash
python src/collect.py   # API 수집
python src/build_db.py  # 임베딩
python src/chat.py      # 검색
```

```
검색: 서울시 도로공사

'서울시 도로공사' 유사 사업 (5건)
─────────────────────────────────
1. 소공로 보행환경 개선공사
   📍 서울특별시 도시기반시설본부
   💰 3.4B (89.88%)
   📊 64.2%

[AI]
서울시 도시기반시설본부의 도로 인프라 사업들입니다.
```

---

*similarity threshold: 0.60 | streaming enabled*
