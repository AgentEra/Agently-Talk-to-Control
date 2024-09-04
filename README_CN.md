# Agently-Talk-to-Control（Agently自然语言→控制）

**[English](./README.md) | 中文**

## 简介

Agently-Talk-to-Control是一个基于[Agently AI 应用开发框架](https://github.com/Maplemx/Agently)开发的开源自然语言转控制操作的Agentic工作流展示项目。

该项目展示了如何使用Agently AI 应用开发框架提供的各项能力创建一个复杂的Agentic工作流来**分析用户通过自然语言表达的需求**并决定是应该：

- **直接基于当前环境信息回答用户的问题**或
- **制定并执行包含一个或多个操作步骤的计划**或
- **拒绝用户的要求，并给出解释，甚至是修正的建议**

## 使用方法

- 步骤 1：克隆此仓库：`git clone git@github.com:AgentEra/Agently-Talk-to-Control.git`
- 步骤 2：编辑`SETTINGS.yaml`，填写你的模型API KEY或切换到其他模型 [查看Agently框架支持的模型](https://github.com/AgentEra/Agently-Daily-News-Collector/blob/main/SETTINGS.yaml)
- 步骤 3：运行 Python 脚本：`python app.py` 如果您没有安装Python，可以[从Python官方网站安装](https://www.python.org/)
- 步骤 4：在浏览器中打开 Gradio UI 页面：默认地址为`http://127.0.0.1:7860/`

## 运行效果图

<img width="480" alt="talk-to-control" src="https://github.com/user-attachments/assets/f6a09285-0620-4918-a577-d628c0bf4102" />
