# Agently-Talk-to-Control

**English | [中文](./README_CN.md)**

## Introduction

**Agently-Talk-to-Control** is an open-source chat text to control actions agentic workflow showcase project powered by [Agently AI application development framework](https://github.com/Maplemx/Agently).

This project presents how to create a complex agentic workflow to **analyse user requirement in natural language** and decide to:

- **directly answer user's question with current environment information** or


- **make and execute an operation plan with one or many operation actions** or

- **reject user's request with explanation or even suggestion**

## How to Use

- Step 1. Clone this repo: `git clone git@github.com:AgentEra/Agently-Talk-to-Control.git`

- Step 2. Edit `SETTINGS.yaml` to fill in your model's API Key or change to other model [[View Agently Supported Models]](https://agently.tech/guides/model_settings/index.html)

- Step 3. Run python script: `python app.py` [[Install Python from Python Official Website]](https://www.python.org/)

- Step 4. Open Gradio UI page in your explorer: `http://127.0.0.1:7860/` by default

## Run Result Screenshot with Default Settings

The image down below is a run result screenshot with the default settings of this project that only contain 2 cameras in component pool to be controlled. 

<img width="480" alt="talk-to-control" src="https://github.com/user-attachments/assets/f6a09285-0620-4918-a577-d628c0bf4102" />

## Try Extend Controllers

Of course, as a showcase project, developers can extend more controllers and components to be controlled as followed.

- Step 1. Add component initial status into `SETTINGS.yaml`

    For example: add 2 lights initial status

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

- Step 2. Add controller functions into `controllers/controllers.py`

    For example: add 2 controller functions of light control

    ```python
    def control_light_power(light_name, target_power):
        power_status = ("Off", "On")
        print(f"⚙️ [Turn On/Off Light]: { light_name } -> Power:{ power_status[target_power] }")
        return { "light_name": light_name, "power": target_power }

    def control_light_brightness(light_name, brightness):
        print(f"⚙️ [Adjust Light Brightness]: { light_name } -> Brightness:{ brightness }")
        return { "light_name": light_name, "brightness": brightness }
    ```

- Step 3. Add controller settings into `SETTINGS.yaml` according status settings in step 1 and controller functions' definitions in step 2.

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
            # Will get environment information from target key before calling operation
            get:
                - "light_status"
            # Will update environment information to target key with target value
            # Placeholder <$variable_name> will be replaced by key values in controller function's return dict
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

OK, now 2 light components have been added to component pool. Let's try to talk to control them.

<img width="480" alt="extend-controllers" src="https://github.com/user-attachments/assets/45c0532d-edea-4ec1-9bad-6028c77f8d48">

Everything seems to be great! Enjoy it!

## Mainly Dependencies

- **Agently AI Development Framework**: https://github.com/Maplemx/Agently | https://pypi.org/project/Agently/ | https://Agently.tech

- **Gradio**: https://github.com/gradio-app/gradio | https://gradio.app/

---

Please ⭐️ this repo and [Agently](https://github.com/Maplemx/Agently) main repo if you like it! Thank you very much!

> 💬 WeChat Group（加入微信群）:
>
>  [Click Here to Apply](https://doc.weixin.qq.com/forms/AIoA8gcHAFMAScAhgZQABIlW6tV3l7QQf) or Scan the QR Code Down Below
>
> <img width="120" alt="image" src="https://github.com/Maplemx/Agently/assets/4413155/7f4bc9bf-a125-4a1e-a0a4-0170b718c1a6">
