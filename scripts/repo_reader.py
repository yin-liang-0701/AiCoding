import os
import re
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_REPO = PROJECT_ROOT / "target_repo"
OUTPUT_FILE = PROJECT_ROOT / "data" / "repo_map.json"

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".git", ".idea", ".vscode"}
SKIP_FILE_PREFIXES = ("test_",)


# 使用正则表达式提取所有函数定义
def extract_functions(code: str) -> list[str]:
    pattern = r"^\s*def\s+([a-zA-Z_]\w*)\s*\("
    # === re.findall() 方法返回所有匹配正则表达式的子串列表，实现了自动化的代码结构分析。===
    return re.findall(pattern, code, re.MULTILINE)


# 使用正则表达式提取所有类定义
def extract_classes(code: str) -> list[str]:
    pattern = r"^\s*class\s+([a-zA-Z_]\w*)\s*[:\(]"
    return re.findall(pattern, code, re.MULTILINE)


# “角色映射函数”，它的核心作用是为每个代码文件贴上语义标签
# 辅助索引：当 AI 检索代码时，这些 hints 会被加入 Prompt，帮助 AI 快速判断“如果要改数据库，我应该去看 repository.py。 不仅定义了文件名，还定义了职责边界
# 上下文工程中的一个高级技巧，叫做 “元数据增强
def build_role_hint(path_str: str) -> str:
    hints = {
        "app.py": "程序入口 应用启动 依赖装配",
        "auth.py": "认证 密码哈希 密码校验 登录验证",
        "controller.py": "控制层 命令处理 登录 注册 whoami 权限入口",
        "entity.py": "实体层 Memo User Tag 领域对象",
        "repository.py": "仓储层 数据持久化 SQLite 查询 用户 会话 标签",
        "session.py": "会话 token 当前登录状态 登录会话",
        "usecase.py": "业务逻辑 用例层 权限控制 memo 增删改查 tag 搜索",
        "view.py": "显示层 输出格式 命令行展示",
    }
    return hints.get(path_str, "")


# 为每个文件生成包含文件名、职责、函数和类的摘要信息
# 是 AI 能够“一眼看全项目”的关键，起到了建立全局索引的作用
# 辅助“检索增强（RAG）”
def build_summary(file_path: Path, functions: list[str], classes: list[str], role_hint: str) -> str:
    parts = [f"文件: {file_path.name}"]
    if role_hint:
        parts.append("职责: " + role_hint)
    if functions:
        parts.append("函数: " + ", ".join(functions))
    if classes:
        parts.append("类: " + ", ".join(classes))
    return " | ".join(parts)


def read_repo() -> list[dict]:
    repo_info = []

    for root, dirs, files in os.walk(TARGET_REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for file in files:
            if not file.endswith(".py"):
                continue
            if file.startswith(SKIP_FILE_PREFIXES):
                continue

            full_path = Path(root) / file
            # 相对于 target_repo 的相对路径
            rel_path = full_path.relative_to(TARGET_REPO)

            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            functions = extract_functions(content)
            classes = extract_classes(content)
            # 根据文件名生成角色提示（MVC分层信息）
            role_hint = build_role_hint(str(rel_path))
            # 生成文件的综合摘要
            summary = build_summary(rel_path, functions, classes, role_hint)

            repo_info.append({
                "path": str(rel_path),
                "functions": functions,
                "classes": classes,
                "role_hint": role_hint,
                "summary": summary,
                "content": content
            })

    repo_info.sort(key=lambda x: x["path"])
    return repo_info


def save_repo_map(repo_info: list[dict]) -> None:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(repo_info, f, ensure_ascii=False, indent=2)


def main() -> None:
    repo_info = read_repo()
    save_repo_map(repo_info)
    print(f"已生成: {OUTPUT_FILE}")
    print(f"共解析 {len(repo_info)} 个 Python 文件")


if __name__ == "__main__":
    main()