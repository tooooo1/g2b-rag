import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

MODEL_NAME = "jhgan/ko-sroberta-multitask"

def load_data(filename="data/bidding.json"):
    """데이터 로드"""
    if not os.path.exists(filename):
        print(f"파일 없음: {filename}")
        print("먼저 collect.py를 실행하세요.")
        return None

    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"데이터 로드: {len(data)}개")
    return data

def build_db(data_file="data/bidding.json"):
    """벡터 DB 구축"""
    data = load_data(data_file)
    if not data:
        return

    print(f"모델 로드: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    client = chromadb.PersistentClient(path="data/chroma")
    try:
        client.delete_collection(name="bidding")
        print("기존 컬렉션 삭제")
    except ValueError:
        pass  # 컬렉션이 없는 경우

    collection = client.create_collection(
        name="bidding",
        embedding_function=None,
        metadata={"hnsw:space": "cosine"},
    )

    texts, metadatas, ids = [], [], []

    for i, item in enumerate(data):
        text_parts = [item.get("bidNtceNm", ""), item.get("dminsttNm", "")]
        text = " | ".join(p for p in text_parts if p)

        if not text:
            continue

        texts.append(text)
        metadatas.append({
            "bidNtceNm": item.get("bidNtceNm", ""),
            "dminsttNm": item.get("dminsttNm", ""),
            "sucsfbidAmt": item.get("sucsfbidAmt", "0"),
            "sucsfbidRate": item.get("sucsfbidRate", ""),
            "bidNtceNo": item.get("bidNtceNo", ""),
            "rlOpengDt": item.get("rlOpengDt", ""),
        })
        ids.append(str(i))

    print(f"임베딩 생성: {len(texts)}개")

    # 배치 임베딩
    batch_size = 32
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_emb = model.encode(batch)
        embeddings.extend(batch_emb.tolist())
        print(f"  {min(i + batch_size, len(texts))}/{len(texts)}")

    # DB 저장 (배치로 나눠서)
    db_batch_size = 5000
    for i in range(0, len(embeddings), db_batch_size):
        end = min(i + db_batch_size, len(embeddings))
        collection.add(
            embeddings=embeddings[i:end],
            documents=texts[i:end],
            metadatas=metadatas[i:end],
            ids=ids[i:end]
        )
        print(f"  DB 저장: {end}/{len(embeddings)}")

    print(f"완료: {len(embeddings)}개")

if __name__ == "__main__":
    build_db()