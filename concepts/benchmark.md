# Benchmarks
一些常见的 benchmnarks以及测试方向

## SWE-bench
1. 能力  
   真实软件工程场景下，在完整仓库里理解 issue、定位问题、修改代码并修复 bug 的能力。
2. 任务  
   真实 GitHub issue + 完整代码仓库环境。
   模型面对的是一个已有项目，要先读上下文、理解 repo 结构，再决定改哪里。
3. 输出  
   输出是一个补丁（patch），目标是让这个仓库里的问题真正被修掉，而不是只给解释或伪代码
4. 指标  
   在 Docker 环境里搭起目标仓库，应用模型生成的 patch，然后跑仓库测试，看 issue 是否被成功解决。

## SWE-bench
1. 能力  
   带视觉信息的软件工程修复能力。  
   考模型能不能理解截图、UI 渲染、设计稿、带视觉上下文的错误信息。
2. 任务  
   包含截图、界面 bug 图、wireframe、功能示意图、带视觉上下文的报错信息。仍是软件工程问题。
3. 输出  
   对现有项目的修复。
4. 指标  
   是否真正修复任务实例。

## HumanEval
1. 能力  
   测的是函数级代码生成的功能正确性。
   衡量模型能不能根据 docstring 合成程序，并用 functional correctness 来评估，而不是看表面相似度。
3. 任务  
   每道题都包含 function signature、docstring、body 和若干 unit tests。
4. 输出  
   函数补全，根据 prompt 补全代码。
5. 指标  
   正确性由是否通过 unit tests定义  
   核心指标是 pass@k，意思是，每题生成 k 个候选，只要其中有一个通过测试，就算该题被解出来。
   
## MBPP
1. 能力  
   从自然语言描述生成短 Python 程序的能力。
2. 任务  
   题目描述，每道题由 task description、code solution 和 3 个 automated test cases 构成
3. 输出  
   短 Python 程序/函数实现
4. 指标  
   生成程序能不能通过自动测试。

## Vibe Code Bench
1. 能力  
   从自然语言需求到完整 Web 应用的端到端交付能力
2. 任务  
   自然语言形式的 Web application specification。
3. 输出  
   是一个完整 runnable application artifact
4. 指标  
   让一个autonomous browser agent 去操作模型生成并部署好的应用，执行端到端 workflows，根据 substep completion 打分。

## 对比
benchmark 不能直接横向比较，因为它们的任务粒度、输入上下文、输出形式和评测方法都不同，本质上是在区分不同层次的软件开发能力。
