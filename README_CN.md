# Agently-Talk-to-Control（Agently自然语言→控制）

**[English](./README.md) | 中文**

## 简介

**Agently-Talk-to-Control** 是一个基于 [Agently AI 应用开发框架](https://github.com/Maplemx/Agently) 构建的开源“自然语言到控制操作”工作流示例项目。

它展示了如何把用户的一段自然语言请求，转成下面三类结果之一：

- **直接基于当前环境状态回答**
- **拆解并执行一个或多个控制动作**
- **拒绝请求，并给出解释或建议**

适用场景包括：

- 智能家居的自然语言输入理解
- 制造、监控、医疗辅助等设备在语音转文字后的控制理解
- 企业内部拥有大量标准控制接口，但仍需要自然语言规划与执行的场景

## 它能做什么

在默认配置下，项目维护一个包含两个摄像头的设备池，并能够：

- 从自由表达的聊天输入中理解控制意图
- 先读取当前设备状态，再决定回复、规划还是拒绝
- 将复杂请求拆成有顺序的控制动作
- 调用控制器函数，并把执行结果写回共享状态
- 在聊天界面里展示规划与执行过程

## 使用方法

1. 克隆仓库：

```bash
git clone git@github.com:AgentEra/Agently-Talk-to-Control.git
cd Agently-Talk-to-Control
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 配置 `SETTINGS.yaml`。

推荐使用 Agently v4 风格的模型配置：

```yaml
AGENT_SETTINGS:
  provider: "OpenAICompatible"
  options:
    base_url: ${ENV.DEEPSEEK_BASE_URL}
    model: ${ENV.DEEPSEEK_DEFAULT_MODEL}
    auth:
      api_key: ${ENV.DEEPSEEK_API_KEY}
```

4. 启动应用：

```bash
python app.py
```

5. 打开终端中显示的本地 Gradio 页面。默认地址是 `http://127.0.0.1:7860/`。

## 环境变量配置

`SETTINGS.yaml` 支持 `${ENV.VAR_NAME}` 语法。

- `UI` 这类项目自身配置由本项目解析
- `AGENT_SETTINGS` 这类 Agently 配置会原样透传给 Agently 的 `auto_load_env` 能力处理

示例：

```yaml
AGENT_SETTINGS:
  provider: "OpenAICompatible"
  options:
    base_url: ${ENV.DEEPSEEK_BASE_URL}
    model: ${ENV.DEEPSEEK_DEFAULT_MODEL}
    auth:
      api_key: ${ENV.DEEPSEEK_API_KEY}

UI:
  server_port: ${ENV.APP_PORT}
```

## 运行效果图

下图展示的是默认双摄像头配置下的运行效果。

<img width="480" alt="talk-to-control" src="https://github.com/user-attachments/assets/f6a09285-0620-4918-a577-d628c0bf4102" />

## 扩展更多控制能力

你可以通过三步扩展新的设备与控制器。

1. 在 `SETTINGS.yaml` 中增加设备初始状态。

示例：增加两个灯

```yaml
INITIAL_STATUS:
  light_status:
    light_a:
      power: 1
      brightness: 50
    light_b:
      power: 0
      brightness: 50
```

2. 在 `controllers/controllers.py` 中增加控制函数。

```python
def control_light_power(light_name, target_power):
    power_status = ("Off", "On")
    print(f"⚙️ [Turn On/Off Light]: {light_name} -> Power:{power_status[target_power]}")
    return {"light_name": light_name, "power": target_power}


def control_light_brightness(light_name, brightness):
    print(f"⚙️ [Adjust Light Brightness]: {light_name} -> Brightness:{brightness}")
    return {"light_name": light_name, "brightness": brightness}
```

3. 在 `SETTINGS.yaml` 中注册控制器。

```yaml
CONTROLLERS:
  control_light_power:
    desc: "turn on or off a target light"
    args:
      light_name:
        $type: "'light_a' | 'light_b'"
        $desc: "[Required]"
      target_power:
        $type: "int"
        $desc: "[Required] 0 - Off, 1 - On"
    func: "control_light_power"
    get:
      - "light_status"
    set:
      "light_status.<$light_name>.power": "<$power>"

  control_light_brightness:
    desc: "adjust a target light's brightness"
    args:
      light_name:
        $type: "'light_a' | 'light_b'"
        $desc: "[Required]"
      brightness:
        $type: "int"
        $desc: "[Required] Range: 0-100"
```

## 当前 v4 版本说明

当前根目录是 **Agently v4** 版本，实现基于：

- **TriggerFlow** 编排
- **Gradio** 聊天界面
- Agently v4 风格模型配置，同时兼容旧版 `MODEL_*` 字段

原 Agently v3 版本已经归档到 [`/v3`](./v3)。

## 当前版本优化点

相对于之前的根目录实现，当前版本补充了这些优化：

- **更细粒度的聊天流式输出**，不再只做粗粒度整块刷新
- **首轮规划直接生成 action args**，很多请求不再需要为每个动作额外再发一次模型请求
- **独立动作并行执行**，例如不同设备资源上的操作可以并发完成
- **支持 `${ENV.VAR}` 配置读取**，方便接入本地或上游环境变量

## 项目结构

- `app.py`：Gradio 入口
- `workflows/talk_to_control.py`：TriggerFlow 主编排逻辑
- `controllers/`：控制器注册与设备动作
- `utils/`：配置加载与聊天历史辅助
- `tests/`：流程与配置测试
- `v3/`：归档的 Agently v3 版本

## 主要依赖

- **Agently AI 应用开发框架**：https://github.com/Maplemx/Agently | https://pypi.org/project/Agently/ | https://agently.tech
- **Gradio**：https://github.com/gradio-app/gradio | https://gradio.app/
