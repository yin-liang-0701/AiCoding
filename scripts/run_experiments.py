import argparse
import csv
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_FILE = PROJECT_ROOT / "data" / "tasks.json"
REPO_MAP_FILE = PROJECT_ROOT / "data" / "repo_map.json"
CASES_DIR = PROJECT_ROOT / "outputs" / "cases"
ANSWERS_DIR = PROJECT_ROOT / "outputs" / "answers"
RESULTS_FILE = PROJECT_ROOT / "data" / "results.csv"

DEFAULT_MODES = ["no_context", "rough", "structured"]


def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tasks() -> List[Dict[str, Any]]:
    return load_json(TASKS_FILE)


def load_repo_map() -> List[Dict[str, Any]]:
    return load_json(REPO_MAP_FILE)


# 将任务列表转换为ID到任务的映射字典
def build_task_index(tasks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {task["id"]: task for task in tasks}


def get_known_repo_files(repo_map: List[Dict[str, Any]]) -> List[str]:
    return sorted(item["path"] for item in repo_map)


def ensure_dirs() -> None:
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)


def read_prompt(task_id: str, mode: str) -> str:
    prompt_file = CASES_DIR / f"{task_id}_{mode}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"未找到 prompt 文件: {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def answer_file_path(task_id: str, mode: str) -> Path:
    return ANSWERS_DIR / f"{task_id}_{mode}_answer.txt"


import time
import requests

def call_openai_compatible_api(prompt: str, system_prompt: str | None = None) -> str:
    api_key = os.getenv("MODEL_API_KEY", "").strip()
    api_base = os.getenv("MODEL_API_BASE", "").strip() # 指向 API 的服务器地址
    model_name = os.getenv("MODEL_NAME", "").strip()
    timeout_s = int(os.getenv("MODEL_TIMEOUT", "120"))
    temperature = float(os.getenv("MODEL_TEMPERATURE", "0"))

    url = api_base.rstrip("/") + "/chat/completions"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    session = requests.Session() # 使用 Session 可以复用 TCP 连接，提高连续多次请求的效率。
    session.trust_env = False # 告诉 Python 忽略系统环境变量里的代理设置

    last_err = None
    for attempt in range(3):
        try:
            resp = session.post(url, headers=headers, json=payload, timeout=timeout_s)
            if resp.status_code >= 400:
                raise RuntimeError(f"API 调用失败: {resp.status_code}\n{resp.text}")
            data = resp.json()
            return data["choices"][0]["message"]["content"] # 精准提取出 AI 生成的那段文本内容并返回。
        except Exception as e:
            last_err = e
            print(f"[WARN] 第 {attempt + 1}/3 次调用失败: {e}")
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f"API 连续 3 次调用失败: {last_err}")


# 提取回答中提到的已知文件
def extract_known_file_mentions(text: str, known_files: List[str]) -> List[str]:
    text_lower = text.lower()
    hits = []
    for f in known_files:
        if f.lower() in text_lower:
            hits.append(f)
    return sorted(set(hits))


# 提取回答中提到的未知.py文件
def extract_unknown_py_mentions(text: str, known_files: List[str]) -> List[str]:
    known_set = {f.lower() for f in known_files}
    candidates = re.findall(r"\b([A-Za-z_][\w\-]*\.py)\b", text)
    unknown = []
    for item in candidates:
        if item.lower() not in known_set:
            unknown.append(item)
    return sorted(set(unknown))


# 统计回答中命中任务关键词的数量
def count_keyword_hits(text: str, keywords: List[str]) -> Tuple[int, List[str]]:
    text_lower = text.lower()
    hits = []
    for kw in keywords:
        if kw.lower() in text_lower:
            hits.append(kw)
    return len(set(hits)), sorted(set(hits))


import re
from typing import List


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def normalize_items(items: List[str]) -> List[str]:
    return sorted(set(x.strip().lower() for x in items if x and x.strip()))


def score_relevant_files(pred_files: List[str], gold_files: List[str]) -> float:
    """
    0~4 分，连续值
    依据 precision / recall / F1，而不是粗暴分档
    """
    pred = set(normalize_items(pred_files))
    gold = set(normalize_items(gold_files))

    if not gold:
        return 0.0
    if not pred:
        return 0.0

    overlap = len(pred & gold)
    precision = safe_div(overlap, len(pred))
    recall = safe_div(overlap, len(gold))
    f1 = safe_div(2 * precision * recall, precision + recall)

    exact_bonus = 0.3 if pred == gold else 0.0
    full_recall_bonus = 0.2 if recall == 1.0 else 0.0

    score = 4.0 * f1 + exact_bonus + full_recall_bonus
    return round(clamp(score, 0.0, 4.0), 2)


def score_structure_understanding(
    answer: str,
    task_type: str,
    pred_files: List[str],
    gold_files: List[str],
    hit_keywords: List[str],
    gold_keywords: List[str],
) -> float:
    """
    0~4 分，连续值
    explain 任务重点看：
    - gold keyword 覆盖率
    - gold file 覆盖率
    - 是否出现流程/调用/分层表达
    feature/bugfix 任务额外看是否有“修改计划”
    """
    answer_lower = answer.lower()

    gold_norm = set(normalize_items(gold_files))
    pred_norm = set(normalize_items(pred_files))
    overlap = len(pred_norm & gold_norm)

    file_coverage = safe_div(overlap, len(gold_norm))
    keyword_coverage = safe_div(len(set(k.lower() for k in hit_keywords)), len(set(k.lower() for k in gold_keywords)))

    flow_terms = [
        "调用", "流程", "经过", "负责", "分层", "入口", "委托", "返回",
        "controller", "usecase", "repository", "view", "entity",
        "auth", "session", "读取", "查询", "展示", "校验", "保存"
    ]
    flow_hits = sum(1 for t in flow_terms if t in answer_lower)
    flow_score = min(flow_hits / 6.0, 1.0)

    plan_terms = ["修改", "新增", "增加", "实现", "检查", "修复", "优先检查", "改动", "步骤"]
    plan_hits = sum(1 for t in plan_terms if t in answer_lower)
    plan_score = min(plan_hits / 5.0, 1.0)

    if task_type == "explain":
        score = (
            1.8 * keyword_coverage +
            1.4 * file_coverage +
            0.8 * flow_score
        )
    else:
        score = (
            1.4 * keyword_coverage +
            1.2 * file_coverage +
            0.8 * flow_score +
            0.6 * plan_score
        )

    return round(clamp(score, 0.0, 4.0), 2)


def score_nonexistent_files(unknown_files: List[str], pred_files: List[str]) -> float:
    """
    0~4 分，但这是“惩罚项”，越高越差
    同时考虑数量和比例，不再是 0/1/2 三档
    """
    unknown_count = len(set(normalize_items(unknown_files)))
    pred_count = len(set(normalize_items(pred_files)))

    if unknown_count == 0:
        return 0.0

    count_penalty = min(unknown_count * 1.2, 3.2)
    ratio_penalty = min(safe_div(unknown_count, max(1, pred_count + unknown_count)) * 1.2, 0.8)

    penalty = count_penalty + ratio_penalty
    return round(clamp(penalty, 0.0, 4.0), 2)


def score_actionable(answer: str, pred_files: List[str], task_type: str) -> float:
    """
    0~4 分，连续值
    看回答是否“可执行”
    """
    answer_lower = answer.lower()
    length = len(answer.strip())

    has_numbering = bool(re.search(r"(^|\n)\s*(\d+\.|-|\*)\s+", answer))
    has_code_block = "```" in answer
    has_patch_words = any(
        kw in answer_lower for kw in [
            "修改建议", "代码补丁", "patch", "diff", "应该修改",
            "建议修改", "优先检查", "实现方式", "修改步骤"
        ]
    )
    has_reasoning_words = any(
        kw in answer for kw in [
            "因为", "因此", "所以", "负责", "调用", "流程", "首先", "然后", "最后"
        ]
    )

    length_score = min(length / 700.0, 1.0)
    grounding_score = min(len(set(normalize_items(pred_files))) / 3.0, 1.0)

    structure_score = 0.0
    if has_numbering:
        structure_score += 0.5
    if has_code_block or has_patch_words:
        structure_score += 0.5

    reasoning_score = 1.0 if has_reasoning_words else 0.0

    if task_type == "explain":
        score = (
            1.3 * grounding_score +
            1.1 * length_score +
            0.8 * structure_score +
            0.8 * reasoning_score
        )
    else:
        score = (
            1.1 * grounding_score +
            0.9 * length_score +
            1.2 * structure_score +
            0.8 * reasoning_score
        )

    return round(clamp(score, 0.0, 4.0), 2)


def normalize_total_score(
    relevant_files_correct: float,
    structure_understanding: float,
    mentions_nonexistent_files: float,   # 惩罚项，越高越差
    actionable: float,
) -> float:
    raw = (
        relevant_files_correct
        + structure_understanding
        + (4.0 - mentions_nonexistent_files)
        + actionable
    )  # max = 16

    return round(raw / 16.0 * 10.0, 2)



def auto_evaluate(
    answer: str,
    task: Dict[str, Any],
    known_files: List[str],
) -> Dict[str, Any]:
    gold_files = task.get("gold_files", [])
    gold_keywords = task.get("gold_keywords", [])
    task_type = task.get("type", "unknown")

    pred_files = extract_known_file_mentions(answer, known_files)
    unknown_files = extract_unknown_py_mentions(answer, known_files)
    keyword_hit_count, hit_keywords = count_keyword_hits(answer, gold_keywords)

    relevant_files_correct = score_relevant_files(pred_files, gold_files)

    structure_understanding = score_structure_understanding(
        answer=answer,
        task_type=task_type,
        pred_files=pred_files,
        gold_files=gold_files,
        hit_keywords=hit_keywords,
        gold_keywords=gold_keywords,
    )

    mentions_nonexistent_files = score_nonexistent_files(
        unknown_files=unknown_files,
        pred_files=pred_files,
    )

    actionable = score_actionable(
        answer=answer,
        pred_files=pred_files,
        task_type=task_type,
    )

    score = normalize_total_score(
        relevant_files_correct=relevant_files_correct,
        structure_understanding=structure_understanding,
        mentions_nonexistent_files=mentions_nonexistent_files,
        actionable=actionable,
    )

    notes = (
        f"pred_files={pred_files}; "
        f"gold_overlap={sorted(set(pred_files) & set(gold_files))}; "
        f"keyword_hits={hit_keywords}; "
        f"unknown_files={unknown_files}"
    )

    return {
        "pred_files": pred_files,
        "unknown_files": unknown_files,
        "hit_keywords": hit_keywords,
        "relevant_files_correct": relevant_files_correct,
        "structure_understanding": structure_understanding,
        "mentions_nonexistent_files": mentions_nonexistent_files,
        "actionable": actionable,
        "score": score,
        "notes": notes,
    }


def init_results_csv_if_needed() -> None:
    if RESULTS_FILE.exists():
        return

    headers = [
        "timestamp",
        "task_id",
        "task_type",
        "mode",
        "model_name",
        "answer_file",
        "relevant_files_correct",
        "structure_understanding",
        "mentions_nonexistent_files",
        "actionable",
        "score",
        "pred_files",
        "unknown_files",
        "hit_keywords",
        "notes",
        "manual_score",
        "manual_notes",
    ]

    with open(RESULTS_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)


def append_result_row(row: Dict[str, Any]) -> None:
    init_results_csv_if_needed()
    headers = [
        "timestamp",
        "task_id",
        "task_type",
        "mode",
        "model_name",
        "answer_file",
        "relevant_files_correct",
        "structure_understanding",
        "mentions_nonexistent_files",
        "actionable",
        "score",
        "pred_files",  # AI回答中提到的文件列表
        "unknown_files",  
        "hit_keywords",
        "notes",
        "manual_score",
        "manual_notes",
    ]

    with open(RESULTS_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writerow(row)


def run_single(task: Dict[str, Any], mode: str, known_files: List[str], overwrite: bool = False) -> None:
    task_id = task["id"]
    task_type = task.get("type", "unknown")
    model_name = os.getenv("MODEL_NAME", "").strip()

    prompt = read_prompt(task_id, mode)
    out_file = answer_file_path(task_id, mode)

    if out_file.exists() and not overwrite:
        answer = out_file.read_text(encoding="utf-8")
        print(f"[SKIP] 已存在回答，直接复用: {out_file}")
    else:
        answer = call_openai_compatible_api(prompt)
        out_file.write_text(answer, encoding="utf-8")
        print(f"[OK] 已保存回答: {out_file}")

    metrics = auto_evaluate(answer, task, known_files)

    row = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task_id": task_id,
        "task_type": task_type,
        "mode": mode,
        "model_name": model_name,
        "answer_file": str(out_file.relative_to(PROJECT_ROOT)),
        "relevant_files_correct": metrics["relevant_files_correct"],
        "structure_understanding": metrics["structure_understanding"],
        "mentions_nonexistent_files": metrics["mentions_nonexistent_files"],
        "actionable": metrics["actionable"],
        "score": metrics["score"],
        "pred_files": "|".join(metrics["pred_files"]),
        "unknown_files": "|".join(metrics["unknown_files"]),
        "hit_keywords": "|".join(metrics["hit_keywords"]),
        "notes": metrics["notes"],
        "manual_score": "",
        "manual_notes": "",
    }

    append_result_row(row)

    print(
        f"[SCORE] {task_id} / {mode} -> "
        f"relevant={row['relevant_files_correct']} "
        f"structure={row['structure_understanding']} "
        f"unknown={row['mentions_nonexistent_files']} "
        f"actionable={row['actionable']} "
        f"score={row['score']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task_ids",
        nargs="+",
        required=True,
        help="例如: task_01 task_02 task_03，或 all",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=DEFAULT_MODES,
        help="例如: no_context rough structured",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="如果已有回答文件，是否覆盖重跑",
    )
    return parser.parse_args()


def main() -> None:
    ensure_dirs()

    tasks = load_tasks()
    task_index = build_task_index(tasks)
    repo_map = load_repo_map()
    known_files = get_known_repo_files(repo_map)

    args = parse_args()

    if args.task_ids == ["all"]:
        selected_tasks = tasks
    else:
        selected_tasks = []
        for task_id in args.task_ids:
            if task_id not in task_index:
                raise ValueError(f"tasks.json 中不存在任务: {task_id}")
            selected_tasks.append(task_index[task_id])

    for task in selected_tasks:
        for mode in args.modes:
            run_single(task, mode, known_files, overwrite=args.overwrite)


if __name__ == "__main__":
    main()