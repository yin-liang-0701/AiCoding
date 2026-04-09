# Mini Context-Aware AI Coding Assistant

## 项目简介
比较不同上下文构造方式对小型代码仓库任务完成效果的影响。

## 仓库目标
记录我对 AI coding 相关概念、仓库实践和后续 PR 想法的整理过程

## 方法
对同一批任务，分别使用无上下文、粗糙上下文、结构化上下文三种方式喂给模型。

## 项目结构
```text
Mini Context-Aware AI Coding Assistant/
├── target_repo/          # 备忘录应用（MVC架构）
├── scripts/              # 分析工具
│   ├── repo_reader.py    # 代码结构分析
│   ├── build_index.py    # TF-IDF索引构建
│   ├── retrieve.py       # 代码检索
│   ├── prompt_builder.py # 提示词生成
│   └── run_experiments.py # 实验运行和评估
└── data/                 # 数据和结果
```

## 预期结果
结构化上下文通常比无上下文和粗糙上下文更稳定。
