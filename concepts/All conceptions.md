# 概念总集合

## AI 重心迁移史
- Prompt Engineering

  模型有没有听懂你在说什么。
  
  本质上不是“命令模型”，而是塑造一个**概率局部空间**，更专注于**语言设计**。
- Context Engineering
  
  模型有没有拿到足够且正确的信息。
  
  系统在调用时将必须模型未必知道的信息在合适的时机把**正确的信息**送进去。其实Prompt可以看作Context的一部分。
- Harness Engineering

  模型在真实执行里能不能持续做对

  更关注模型别跑偏、跑得稳、跑错了还能拉回来。

## Transformer
是当前AI使用的架构，本质上是**编码器-翻译-解码器**。

## Token
是大模型处理数据的基本单元，将User prompt划分为多个token作为输入给大模型

## Prompt
- System prompt
  系统级提示词，是开发者为大模型设定好的框架，比如说该大模型的身份
- User prompt
  用户提示词，即用户和大模型交流时所使用的语句

## Tool
本质上是一个函数，给大模型提供一套可调用的外部能力，让大模型可以感知和影响外部环境。
实际上调用Tool要经过平台的转发，而不是大模型直接调用。

## MCP
Tool的统一接入规范

## Agent
能够自主规划、自主调用工具，直到完成用户任务的系统

## Agent skill

提前写好塞给Agent的一份说明文档，避免多次对话时输入重复的背景条件。策略是**渐进式披露**。

由 **元数据层**（*name* + *description*）+ **指令层**组成

## Harness Engineering
[harness 详细说明](Harness-Engineering.md)

