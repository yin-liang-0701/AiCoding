import argparse
import json
from pathlib import Path

from retrieve import search

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_FILE = PROJECT_ROOT / "data" / "tasks.json"
REPO_MAP_FILE = PROJECT_ROOT / "data" / "repo_map.json"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "cases"


def load_tasks():
    with open(TASKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_repo_map():
    with open(REPO_MAP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    

# 根据ID获取特定任务
def get_task_by_id(task_id: str):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise ValueError(f"未找到任务: {task_id}")


# 将仓库中所有的文件名组织成一个直观的“文件树”字符串。模拟终端里 tree 命令的效果。
# 最后用换行符连接成一个大字符串。
def build_file_tree(repo_map):
    paths = [item["path"] for item in repo_map]
    lines = ["target_repo/"]
    for path in sorted(paths):
        lines.append(f"├── {path}")
    return "\n".join(lines)


# 是 RAG（检索增强生成）系统中的**“保险丝”**，用来防止单个文件的代码量过大，导致 Prompt 超过 AI 的处理极限
def shorten_code(text: str, max_chars: int = 1200):
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... (truncated)"


"""
特点：只提供任务描述，没有任何代码仓库信息
用途：测试模型在没有上下文情况下的表现
要求：让模型基于常识判断，避免编造不存在的文件
"""
def build_no_context_prompt(task_text: str):
    return f"""你是一个代码助手。

            任务：
            {task_text}

            请完成以下要求：
            1. 判断应该修改或查看哪些文件
            2. 说明理由
            3. 如果适合，给出修改建议或代码补丁
            4. 尽量避免编造不存在的文件或函数
            """



"""
包含信息：
    项目文件树结构
    任务描述
    检索到的相关文件摘要（路径、摘要、角色提示、函数、类、相关性分数）
用途：提供基本的项目结构信息，但不包含具体代码
"""
# 核心逻辑是：不给 AI 看具体的源代码，只给 AI 看“地图”和“说明书”。
# 测试 AI 的架构推理能力，而不是简单的代码补全能力。
def build_rough_context_prompt(task_text: str, repo_map: list, retrieved_docs: list):
    # 宏观视野：项目文件树
    # 防止 AI 凭空编造不存在的文件路径（即减少“幻觉”）。让 AI 知道文件的相对位置。
    file_tree = build_file_tree(repo_map)


    # 中观线索：文件元数据
    # 遍历 retrieved_docs（搜索到的相关文件），并将它们的信息结构化。
    summary_blocks = []
    for i, doc in enumerate(retrieved_docs, 1):
        summary_blocks.append(
            f"""[{i}] {doc['path']}
            summary: {doc.get('summary', '')}
            role_hint: {doc.get('role_hint', '')}
            functions: {', '.join(doc.get('functions', [])) if doc.get('functions') else '(none)'}
            classes: {', '.join(doc.get('classes', [])) if doc.get('classes') else '(none)'}
            score: {doc.get('score', 0.0):.4f}
            """
        )

    joined_summaries = "\n".join(summary_blocks)

    # 任务约束：回答要求
    return f"""你是一个面向小型代码仓库的代码助手。

        项目文件树：
        {file_tree}

        当前任务：
        {task_text}

        检索到的相关文件摘要：
        {joined_summaries}

        请回答：
        1. 这个任务最可能涉及哪些文件
        2. 每个文件大概承担什么职责
        3. 应该如何修改或分析
        4. 若需要代码，请给出尽量贴合当前仓库结构的建议
        """


"""
最详细的上下文，包含：
项目目标和实验背景
任务描述
候选关键函数列表
候选关键类列表
详细的文件信息（包括代码片段）
特殊处理：
shorten_code(): 限制代码片段长度（默认1200字符）
只显示前12个关键函数和类
"""
# 带导航索引的详细设计图 + 核心代码残卷
# 不仅堆砌信息，还对信息进行了二次加工
def build_structured_context_prompt(task_text: str, retrieved_docs: list):
    context_blocks = []
    key_functions = []
    key_classes = []

    for i, doc in enumerate(retrieved_docs, 1):
        # 它从每个文件中提取前 8 个函数和类，并加上路径前缀
        # 即使代码片段被截断了，AI 至少知道这些函数在哪里定义，极大减少了它“凭空捏造 API”的可能。
        functions = doc.get("functions", [])
        classes = doc.get("classes", [])
        key_functions.extend([f"{doc['path']}::{fn}" for fn in functions[:8]])
        key_classes.extend([f"{doc['path']}::{cl}" for cl in classes[:8]])

        # 它包含了真实的源代码。通过 1200 字符的限制，它精准地把最核心的类定义和函数签名塞进了 Prompt。
        context_blocks.append(
                        f"""[{i}] 文件: {doc['path']}
            职责提示: {doc.get('role_hint', '')}
            摘要: {doc.get('summary', '')}
            函数: {', '.join(functions) if functions else '(none)'}
            类: {', '.join(classes) if classes else '(none)'}
            相关性分数: {doc.get('score', 0.0):.4f}

            代码片段:
            {shorten_code(doc.get('content', ''), max_chars=1200)}
            """
                    )
    
    # 全局候选名单限制在了 12 个以内。
    key_functions = key_functions[:12]
    key_classes = key_classes[:12]

    # 序列化
    # 通过代码收集到的结构化数据（对象、列表），必须通过这种方式转换成线性文本流，AI 才能读取。
    joined_context = "\n\n".join(context_blocks)
    joined_functions = "\n".join(f"- {x}" for x in key_functions) if key_functions else "- (none)"
    joined_classes = "\n".join(f"- {x}" for x in key_classes) if key_classes else "- (none)"

    return f"""你是一个 repo-level AI coding assistant。你必须基于给定仓库上下文回答，不能凭空编造文件、函数或系统结构。

        项目目标：
        这是一个小型代码仓库分析实验。目标是评估：不同上下文构造方式，会如何影响模型完成仓库级代码任务的表现。

        当前任务：
        {task_text}

        候选关键函数：
        {joined_functions}

        候选关键类：
        {joined_classes}

        检索到的核心上下文：
        {joined_context}

        回答要求：
        1. 先指出这个任务最可能涉及的 2~5 个文件
        2. 说明这些文件在任务中的分工
        3. 如果是 explain 类任务，解释调用链/分层关系
        4. 如果是 feature 或 bugfix 类任务，给出修改方案
        5. 若给代码，尽量保持现有命名与结构一致
        6. 如果信息不足，要明确说明“不确定的部分”
        7. 不要引用不存在的文件
        """


def save_prompt(task_id: str, mode: str, prompt_text: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_file = OUTPUT_DIR / f"{task_id}_{mode}.txt"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(prompt_text)
    return out_file


def build_repo_map_dict(repo_map):
    return {item["path"]: item for item in repo_map}


# 将检索结果与完整的仓库映射数据合并
# 确保检索到的文档包含完整的源代码内容
def enrich_retrieved_docs(retrieved_docs, repo_map):
    repo_dict = build_repo_map_dict(repo_map)
    enriched = []

    for doc in retrieved_docs:
        full_item = repo_dict.get(doc["path"], {})
        merged = {
            **doc,
            "content": full_item.get("content", ""),
            "functions": full_item.get("functions", doc.get("functions", [])),
            "classes": full_item.get("classes", doc.get("classes", [])),
            "summary": full_item.get("summary", doc.get("summary", "")),
            "role_hint": full_item.get("role_hint", doc.get("role_hint", "")),
        }
        enriched.append(merged)

    return enriched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task_id", type=str, required=True, help="tasks.json 中的任务 id")
    parser.add_argument("--mode", type=str, default="all",
                        choices=["all", "no_context", "rough", "structured"],
                        help="生成哪种 prompt")
    parser.add_argument("--topk", type=int, default=5, help="检索前 k 个文件")
    args = parser.parse_args()

    task = get_task_by_id(args.task_id)
    task_text = task["task"]

    repo_map = load_repo_map()
    retrieved_docs = search(task_text, topk=args.topk)
    retrieved_docs = enrich_retrieved_docs(retrieved_docs, repo_map)

    generated = {}

    if args.mode in ["all", "no_context"]:
        generated["no_context"] = build_no_context_prompt(task_text)

    if args.mode in ["all", "rough"]:
        generated["rough"] = build_rough_context_prompt(task_text, repo_map, retrieved_docs)

    if args.mode in ["all", "structured"]:
        generated["structured"] = build_structured_context_prompt(task_text, retrieved_docs)

    for mode, text in generated.items():
        out_file = save_prompt(args.task_id, mode, text)
        print(f"[OK] 已生成: {out_file}")


if __name__ == "__main__":
    main()