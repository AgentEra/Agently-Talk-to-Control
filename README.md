# Agently-Talk-to-Control

**English | [中文](./README_CN.md)**

## Introduction

**Agently-Talk-to-Control** is an open-source natural-language-to-control workflow demo built with the [Agently AI application framework](https://github.com/Maplemx/Agently).

The project shows how to turn a user request in natural language into one of three outcomes:

- **reply directly** from current environment state
- **plan and execute one or multiple control actions**
- **reject the request** with explanation and suggestion

Typical scenarios include:

- smart home input understanding
- device control after speech-to-text in manufacturing, monitoring, or medical assistance
- enterprise environments with many standardized control APIs that still need natural-language understanding

## What It Can Do

With the default settings, the project manages a small device pool with two cameras and can:

- understand user intent from free-form chat
- inspect current device status before deciding what to do
- split a complex request into ordered control actions
- execute controller functions and write the result back into shared status
- show intermediate planning and execution output in the chat UI

## How to Use

1. Clone this repo:

```bash
git clone git@github.com:AgentEra/Agently-Talk-to-Control.git
cd Agently-Talk-to-Control
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure `SETTINGS.yaml`.

Recommended Agently v4-style model config:

```yaml
AGENT_SETTINGS:
  provider: "OpenAICompatible"
  options:
    base_url: ${ENV.DEEPSEEK_BASE_URL}
    model: ${ENV.DEEPSEEK_DEFAULT_MODEL}
    auth:
      api_key: ${ENV.DEEPSEEK_API_KEY}
```

4. Start the app:

```bash
python app.py
```

5. Open the local Gradio page shown in the terminal. By default it runs on `http://127.0.0.1:7860/`.

## Environment Variables

`SETTINGS.yaml` supports `${ENV.VAR_NAME}` syntax.

Project-side fields such as `UI` are resolved by this repo, and Agently-side model settings are passed through to Agently's `auto_load_env` support.

Example:

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

## Run Result Screenshot

The screenshot below shows the default two-camera setup in action.

<img width="480" alt="talk-to-control" src="https://github.com/user-attachments/assets/f6a09285-0620-4918-a577-d628c0bf4102" />

## Extend Controllers

You can extend the device pool and controller set with three steps.

1. Add initial device state to `SETTINGS.yaml`.

Example: add two lights

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

2. Add controller functions to `controllers/controllers.py`.

```python
def control_light_power(light_name, target_power):
    power_status = ("Off", "On")
    print(f"⚙️ [Turn On/Off Light]: {light_name} -> Power:{power_status[target_power]}")
    return {"light_name": light_name, "power": target_power}


def control_light_brightness(light_name, brightness):
    print(f"⚙️ [Adjust Light Brightness]: {light_name} -> Brightness:{brightness}")
    return {"light_name": light_name, "brightness": brightness}
```

3. Register the controllers in `SETTINGS.yaml`.

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

## Agently v4 Version

The current root project is the **Agently v4** implementation, based on:

- **TriggerFlow** for orchestration
- **Gradio** for the chat UI
- Agently v4-style model settings with backward compatibility for older `MODEL_*` fields

The original Agently v3 version is archived under [`/v3`](./v3).

## Optimization Highlights

Compared with the earlier root version of this repo, the current implementation includes:

- **true incremental chat updates** in the Gradio UI instead of coarse block updates
- **first-pass action arg generation**, so many requests avoid a second model call per action
- **parallel execution for independent actions**, such as operations targeting different device resources
- **environment-backed config loading**, including `${ENV.VAR}` support in `SETTINGS.yaml`

## Project Structure

- `app.py`: Gradio entrypoint
- `workflows/talk_to_control.py`: TriggerFlow orchestration
- `controllers/`: controller registry and device actions
- `utils/`: config loading and chat-history helpers
- `tests/`: flow and config tests
- `v3/`: archived Agently v3 implementation

## Main Dependencies

- **Agently AI Development Framework**: https://github.com/Maplemx/Agently | https://pypi.org/project/Agently/ | https://agently.tech
- **Gradio**: https://github.com/gradio-app/gradio | https://gradio.app/
