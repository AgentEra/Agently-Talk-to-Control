import re
import Agently

workflow = Agently.Workflow()
op_workflow = Agently.Workflow()

# Replace placeholders to update environment information
def replace_placeholders(origin_text, key_values):
    def replace(match):
        key = match.group(1)
        return key_values.get(key, match.group(0))
    
    pattern = r'<\$(\w+)>'
    return (
        key_values[origin_text[2:-1]]
        if origin_text.startswith("<$") and origin_text.endswith(">")
        else re.sub(pattern, replace, origin_text)
    )

# Define workflow chunks
@workflow.chunk()
def init_data(inputs, storage):
    storage.set("user_input", inputs["default"])
    return

@workflow.chunk()
def make_op_plan(inputs, storage):
    agent = storage.get("$agent")
    return (
        agent
            .chat_history(storage.get("chat_history", []))
            .input(storage.get("user_input"))
            .info({
                "current_equipment_status": workflow.public_storage.get("status"),
                "operation_dict": workflow.public_storage.get("controller_desc_info"),
            })
            .output({                
                "can_reply_directly": ("bool", "can you reply {input} directly according {info.current_equipment_status}?"),
                "direct_reply": ("str", "if {output.can_reply_directly} == true, generate reply, else output null."),
                "action_plan": (
                    [{
                        "purpose": ("str", "specify user one step operating purpose from {input}, must include key matters according {info}"),
                        "key_factors": ([("str", )], "specify this step's key factors, object name, quantity, etc."),
                        "op_name": ("str", "key name FROM {info.operation_dict} ONLY!!!"),
                    }],
                    "if {output.can_reply_directly} == false, " +
                    "make operating plan according {input} and split operation according {info.operation_dict} in correct orders, " +
                    "else output [].\n" +
                    "IF MULTIPLE DEVICE COMPONENTS NEED TO BE OPERATED THROUGH INSTRUCTIONS, " +
                    "EACH ACTION INSTRUCTION CAN ONLY SPECIFY ONE COMPONENT\n" +
                    "For example: when user said 'all cameras' you should separate cameras into camera 1, camera 2, etc.",
                    "YOU CAN USE OPERATIONS FROM {info.operation_dict} ONLY!!!"
                ),
                "can_not_do": ("str", "if you can not accomplish {input}, explain why, else output ''.")
            })
            .start()
    )

@workflow.chunk()
def direct_reply(inputs, storage):
    app = storage.get("$app")
    app.emit_delta("[Directly Reply]: " + inputs["default"]["direct_reply"])
    return

@workflow.chunk()
def can_not_do_reply(inputs, storage):
    app = storage.get("$app")
    app.emit_delta("[Can Not Apply]: " + inputs["default"]["can_not_do"])
    return

@op_workflow.chunk()
def init_data(inputs, storage):
    storage.set("purpose", inputs["default"]["purpose"])
    storage.set("key_factors", inputs["default"]["key_factors"])
    storage.set("op_name", inputs["default"]["op_name"])
    return

@op_workflow.chunk()
def prepare_env_info(inputs, storage):
    info_dict = {}
    get_list = workflow.public_storage.get(f"controller_info.{ storage.get('op_name') }.get", [])
    for info_name in get_list:
        info_dict.update({ info_name: workflow.public_storage.get(f"status.{ info_name }") })
    return info_dict

@op_workflow.chunk()
def generate_calling_info(inputs, storage):
    agent = storage.get("$agent")
    app = storage.get("$app")
    app.emit_delta(f"[Operation]: { storage.get('purpose') }\n\n")
    return (
        agent
            .input({
                "purpose": storage.get("purpose"),
                "key_factors": storage.get("key_factors"),
            })
            .info(inputs["default"])
            .instruct([
                "generate operation calling parameter values to achieve {input} purpose.",
                "output language: Chinese",
            ])
            .output({
                "can_do": ("bool", "judge if operation can be done according {info}"),
                "explanation": ("str | null", "if {can_do}==false, generate explanation why the operation can no be done and operation suggestions in language {input} used."),
                "suggestion_order": ("str | null", "if {can_do}==false, generate order you suggest user to say, do not use args name directly, use natural language to point to args."),
                "args": (
                    workflow.public_storage.get(f"controller_info.{ storage.get('op_name') }.args"),
                    "if {can_do}==true, generate args"
                ),
            })
            .start()
    )

@op_workflow.chunk()
def call_op(inputs, storage):
    return workflow.public_storage.get(f"controller_info.{ storage.get('op_name') }.func")(**inputs["default"]["args"])

@op_workflow.chunk()
def update_env_info(inputs, storage):
    app = storage.get("$app")
    set_dict = workflow.public_storage.get(f"controller_info.{ storage.get('op_name') }.set")
    for key, value in set_dict.items():
        target_key = replace_placeholders(key, inputs["default"])
        target_value = replace_placeholders(value, inputs["default"])
        workflow.public_storage.set(f"status.{ target_key }", target_value)
        app.emit_delta("[Operation Result]: " + f"{ target_key } = { target_value }" + "\n\n")
    return

@op_workflow.chunk()
def set_skip_data(inputs, storage):
    workflow.public_storage.set("skip", True)
    workflow.public_storage.set("explanation", inputs["default"]["explanation"])
    workflow.public_storage.set("suggestion_order", inputs["default"]["suggestion_order"])
    return

@workflow.chunk()
def return_value(inputs, storage):
    app = storage.get("$app")
    skip = workflow.public_storage.get("skip")
    explanation = workflow.public_storage.get("explanation")
    suggestion_order = workflow.public_storage.get("suggestion_order")
    workflow.public_storage.set("explanation", None)
    workflow.public_storage.set("suggestion_order", None)
    workflow.public_storage.set("skip", False)
    if skip:
        app.emit_delta("[Can Not Apply]: " + explanation + "\n\n")
        app.emit_delta("[Suggestion]: " + suggestion_order + "\n\n")
    return

def print_result(inputs, storage):
    app = storage.get("$app")
    app.emit_delta(inputs["default"] + "\n\n")
    return inputs["default"]

# Define Workflow
(
    op_workflow
        .connect_to("init_data")
        .if_condition(lambda return_value, storage: not workflow.public_storage.get("skip"))
            .connect_to("prepare_env_info")
            .connect_to("generate_calling_info")
            .if_condition(lambda return_value, storage: return_value["can_do"])
                .connect_to("call_op")
                .connect_to("update_env_info")
                .connect_to("END")
            .else_condition()
                .connect_to("set_skip_data")
                .connect_to("END")
            .end_condition()
        .end_condition()
)
(
    workflow
        .connect_to("init_data")
        .connect_to("make_op_plan")
        .if_condition(lambda return_value, storage: return_value["can_reply_directly"])
            .connect_to("direct_reply")
            .connect_to("END")
        .elif_condition(lambda return_value, storage: "can_not_do" in return_value and len(return_value["can_not_do"]) > 0)
            .connect_to("can_not_do_reply")
            .connect_to("END")
        .else_condition()
            .connect_to(lambda inputs, storage: inputs["default"]["action_plan"])
            .loop_with(op_workflow)
            .connect_to("return_value")
            .connect_to("END")
        .end_condition()
)