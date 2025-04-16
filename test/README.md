## 1. 概述

使用OpenAI的GPT-4o-mini模型，从LeetCode网站抓取问题，生成Python解决方案，并自动执行测试以验证生成代码的正确性。

## 2. 测试结果摘要

基于500个LeetCode问题的测试，系统取得了以下结果：

- **成功率**: 37.80% (189/500)
- **失败问题**: 281个
- **错误问题**: 30个

## 3. 系统架构

系统由以下主要组件构成：

### 3.1 LeetCodeScraper类

该类负责从LeetCode网站获取问题信息

### 3.2 SolutionGenerator类

该类负责生成问题解决方案

### 3.3 TestExecutor类

该类负责测试生成的解决方案

主要和测试的数据进行比较，如果全部正确，则视为生成代码正确。（但有局限性，有些题目答案不止一个解）

### 3.4 LeetCodeTester类

系统的主类，协调其他组件工作

## 4. 数据收集方法

系统通过以下步骤收集LeetCode问题数据：

1. **问题列表获取**: 系统首先尝试通过GraphQL API获取LeetCode问题列表，如果失败则依次尝试REST API和网页抓取
2. **问题详情获取**: 对每个问题，系统获取完整描述、输入/输出示例、函数签名等信息
3. **测试用例提取**: 系统从问题描述和示例中提取结构化的测试用例
4. **数据缓存**: 所有获取的问题数据都会缓存到本地，避免重复下载
5. **数据格式化**: 原始数据被转换为结构化格式，便于后续处理

## 5. 解决方案生成方法

系统使用OpenAI的GPT-4o-mini模型生成解决方案：

1. 将问题描述、示例和函数签名整合为提示
2. 通过DSPy框架发送请求到GPT-4o-mini
3. 解析返回的代码和解释
4. 清理和格式化代码
5. 如果生成失败，会进行多次尝试

## 6. 程序运行指南

### 6.1 运行模式

系统支持三种主要运行模式：

#### 6.1.1 下载模式

下载并缓存LeetCode问题（获取500个leetcode问题）：

```bash
python leetcode_tester.py --mode download --limit 500 --api-key YOUR_API_KEY
```

#### 6.1.2 测试模式

生成并测试LeetCode问题的解决方案：

```bash
python leetcode_tester.py --mode test --test-count 500 --api-key YOUR_API_KEY
```

#### 6.1.3 重测模式

重新测试已生成的解决方案：

```bash
python leetcode_tester.py --mode retest
```

### 6.2 命令行参数

- `--mode`: 运行模式(`download`, `test`, `retest`)
- `--api-key`: OpenAI API密钥
- `--model`: 使用的模型(默认: `openai/gpt-4o-mini`)
- `--limit`: 下载模式中的问题数量上限(默认: 500)
- `--test-count`: 测试模式中的问题数量(默认: 500)
- `--pattern`: 重测模式中的文件匹配模式
- `--attempts`: 每个问题的最大尝试次数(默认: 2)
- `--seed`: 问题选择的随机种子(默认: 42)

### 6.3 数据集清洗

在leetcode数据集收集的时候有些数据并没有收集准确，运行代码以清洗`leetcode_dataset.py`的数据内容。

```bash
python fix_dataset.py
```

## 7. 数据集描述

- leetcode_cache：保存爬取的原始leetcode问题
- leetcode_dataset：保留leetcode问题、Python初始代码、测例等
- results：包括测试结果