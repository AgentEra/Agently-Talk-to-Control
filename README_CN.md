# Agently-Talk-to-Control（Agently自然语言→控制）

**[English](./README.md) | 中文**

## 简介

Agently-Talk-to-Control是一个基于[Agently AI 应用开发框架](https://github.com/Maplemx/Agently)开发的开源自然语言转控制操作的Agentic工作流展示项目。

该项目展示了如何使用Agently AI 应用开发框架提供的各项能力创建一个复杂的Agentic工作流来**分析用户通过自然语言表达的需求**并决定是应该：

- **直接基于当前环境信息回答用户的问题**或
- **制定并执行包含一个或多个操作步骤的计划**或
- **拒绝用户的要求，并给出解释，甚至是修正的建议**

该项目的适用场景包括：

- 作为智能家居的输入理解模块，理解和处理用户的复杂输入表达并完成指令执行
- 作为制造、监视、医疗辅助等设备的语音转文字后的辅助理解模块，帮助操作者在作业过程中对设备进行辅助控制
- 作为输入理解和行动规划模块，在企业办公等具有较多规范行动请求接口的场景中，帮助理解和规划用户的复杂输入表达并抽取标准信息进行请求
- ……

## 使用方法

- 步骤 1：克隆此仓库：`git clone git@github.com:AgentEra/Agently-Talk-to-Control.git`
- 步骤 2：编辑`SETTINGS.yaml`，填写你的模型API KEY或切换到其他模型 [查看Agently框架支持的模型](https://github.com/AgentEra/Agently-Daily-News-Collector/blob/main/SETTINGS.yaml)
- 步骤 3：运行 Python 脚本：`python app.py` 如果您没有安装Python，可以[从Python官方网站安装](https://www.python.org/)
- 步骤 4：在浏览器中打开 Gradio UI 页面：默认地址为`http://127.0.0.1:7860/`

## 使用默认配置的运行效果图

下图为仅使用默认配置（设备池中只包括两个摄像头）的情况下，运行的效果：

<img width="480" alt="talk-to-control" src="https://github.com/user-attachments/assets/f6a09285-0620-4918-a577-d628c0bf4102" />

## 扩展更多的控制能力

当然了，本项目支持开发者通过简单的操作扩展解决方案的控制能力：

- 步骤 1. 如果想要扩展新的设备，将设备的初始状态添加到 `SETTINGS.yaml`

    我们以向设备池中添加两个灯为例：

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

- 步骤 2. 将控制方法函数添加到`controllers/controllers.py`

    ```python
    def control_light_power(light_name, target_power):
        power_status = ("Off", "On")
        print(f"⚙️ [Turn On/Off Light]: { light_name } -> Power:{ power_status[target_power] }")
        return { "light_name": light_name, "power": target_power }

    def control_light_brightness(light_name, brightness):
        print(f"⚙️ [Adjust Light Brightness]: { light_name } -> Brightness:{ brightness }")
        return { "light_name": light_name, "brightness": brightness }
    ```

- 步骤 3. 根据步骤1中的设备状态设置和步骤2中的控制方法函数定义，将控制器设置添加到`SETTINGS.yaml`

    ```yaml
    CONTROLLERS:
        control_light_power:
            desc: "turn on or off a target light"
            args:
                light_name:
                    $type: "'light_a', 'light_b'"
                    $desc: "[Required]"
                target_power:
                    $type: "int"
                    $desc: "[Required]0 - Off, 1 - On"
            func: "control_light_power"
            # 将在生成控制函数调用参数值前，从环境中取出指定字段的值作为补充信息
            get:
                - "light_status"
            # 将在控制函数调用结束后，更新环境信息
            # 占位符<$variable_name>将被控制函数的返回结果字典里的对应字段值替代
            set:
                "light_status.<$light_name>.power": "<$power>"
        control_light_brightness:
            desc: "adjust a target light's brightness"
            args:
                light_name:
                    $type: "'light_a', 'light_b'"
                    $desc: "[Required]"
                brightness:
                    $type: "int"
                    $desc: "[Required] Range: 0(darkest)-100(brightest)"
    ```

通过上面三步，我们就成功向设备池中添加了2个灯的状态及控制方法。现在，我们就试试通过Gradio界面来进行自然语言控制吧！

<img width="480" alt="extend-controllers" src="https://github.com/user-attachments/assets/45c0532d-edea-4ec1-9bad-6028c77f8d48">

不错不错，看起来很棒，能够很好地拆解规划复杂的指令。

## 主要依赖说明

- **Agently AI应用开发框架**：https://github.com/Maplemx/Agently | https://pypi.org/project/Agently/ | http://Agently.cn

- **Gradio**: https://github.com/gradio-app/gradio | https://gradio.app/

---

如果您喜欢这个项目，请为本项目以及[Agently框架主仓库](https://github.com/Maplemx/Agently)点亮⭐️。

> 💬 加入Agently AI应用开发框架开发者讨论微信群:
>
>  [点击此处申请](https://doc.weixin.qq.com/forms/AIoA8gcHAFMAScAhgZQABIlW6tV3l7QQf)或扫描下方二维码申请
>
> <img width="120" alt="image" src="https://github.com/Maplemx/Agently/assets/4413155/7f4bc9bf-a125-4a1e-a0a4-0170b718c1a6">
