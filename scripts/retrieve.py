import argparse
import pickle
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = PROJECT_ROOT / "data" / "tfidf_index.pkl"


def search(query: str, topk: int = 5) -> list[dict]:
    with open(INDEX_FILE, "rb") as f:
        payload = pickle.load(f)

    # 获取向量化器、文档矩阵和文档元数据
    vectorizer = payload["vectorizer"]
    matrix = payload["matrix"]
    docs = payload["docs"]

    # 使用相同的向量化器将查询文本转换为 TF-IDF 向量
    # 计算查询向量与所有文档向量之间的余弦相似度
    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix).flatten()

    # 按相似度分数降序排列, 返回前 topk 个最相关的结果
    ranked = sorted(
        enumerate(scores),
        key=lambda x: x[1],
        reverse=True
    )[:topk]

    results = []
    for idx, score in ranked:
        results.append({
            "path": docs[idx]["path"],
            "score": float(score),
            "summary": docs[idx]["summary"],
            "role_hint": docs[idx].get("role_hint", ""),
            "functions": docs[idx]["functions"],
            "classes": docs[idx]["classes"],
        })

    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, required=True, help="检索任务描述")
    parser.add_argument("--topk", type=int, default=5, help="返回前 k 个结果")
    args = parser.parse_args()

    results = search(args.query, args.topk)

    print(f"\n查询: {args.query}\n")
    for i, item in enumerate(results, 1):
        print(f"[{i}] {item['path']}")
        print(f"score: {item['score']:.4f}")
        print(f"summary: {item['summary']}")
        print(f"role_hint: {item['role_hint']}")
        print(f"functions: {', '.join(item['functions']) if item['functions'] else '(none)'}")
        print(f"classes: {', '.join(item['classes']) if item['classes'] else '(none)'}")
        print("-" * 60)


if __name__ == "__main__":
    main()