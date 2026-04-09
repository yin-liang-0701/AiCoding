import json
import pickle
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_MAP_FILE = PROJECT_ROOT / "data" / "repo_map.json"
INDEX_FILE = PROJECT_ROOT / "data" / "tfidf_index.pkl"


# 将每个代码文件的信息组合成一个搜索文档
def build_document(item: dict) -> str:
    parts = [
        f"path: {item['path']}",
        f"summary: {item.get('summary', '')}",
        f"role_hint: {item.get('role_hint', '')}",
        "functions: " + " ".join(item.get("functions", [])),
        "classes: " + " ".join(item.get("classes", [])),
        item.get("content", "")
    ]
    return "\n".join(parts)


def main() -> None:
    # 读取 repo_reader.py 生成的仓库映射文件
    with open(REPO_MAP_FILE, "r", encoding="utf-8") as f:
        repo_map = json.load(f)

    # 为每个文件创建包含元数据和搜索文本的文档对象
    docs = []
    for item in repo_map:
        docs.append({
            "path": item["path"],
            "summary": item.get("summary", ""),
            "role_hint": item.get("role_hint", ""),
            "functions": item.get("functions", []),
            "classes": item.get("classes", []),
            "text": build_document(item)
        })

    # 形成搜索语料库
    corpus = [doc["text"] for doc in docs]

    # TF-IDF向量化, 将文本转换为数值向量
    # char_wb (Character Word Boundaries): 在单词边界内提取字符级 n-gram。会将 get_user 切分成更小的碎片（如 ge, et, _u, us 等）。它能识别出模糊的相似性。
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4), # 它会同时提取长度为 2、3、4 的字符片段。
        lowercase=True
    )
    # fit: 扫描整个 corpus（语料库），统计所有的字符碎片，建立一本“字典”。
    # transform: 根据字典，把每一段代码/文档变成一排数字（向量）。
    # 结果：matrix 是一个稀疏矩阵，每一行代表一个文件，每一列代表一个碎片权重。
    matrix = vectorizer.fit_transform(corpus)

    payload = {
        "vectorizer": vectorizer, # 用于新查询
        "matrix": matrix, # 用于相似度计算
        "docs": docs # 用于结果显示
    }

    # 生成二进制索引文件
    with open(INDEX_FILE, "wb") as f:
        pickle.dump(payload, f)

    print(f"索引已生成: {INDEX_FILE}")
    print(f"共索引 {len(docs)} 个文件")#


if __name__ == "__main__":
    main()