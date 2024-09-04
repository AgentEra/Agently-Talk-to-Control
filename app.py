import Agently
import utils.yaml_reader as yaml
from utils.logger import Logger
from utils.path import root_path
from controllers import create_controller_info
from workflows.workflows import workflow

# Settings and Logger
SETTINGS = yaml.read(f"{ root_path }/SETTINGS.yaml")
logger = Logger(
    console_level = "DEBUG" if SETTINGS.DEBUG else "INFO",
    path = f"{ root_path }/logs/Agently_talk_to_control.log"
)

# Create Agent
MODEL_CLIENT = SETTINGS.MODEL_CLIENT if SETTINGS.MODEL_CLIENT else "OAIClient"
agent = (
    Agently.create_agent()
        .set_settings("current_model", MODEL_CLIENT)
        .set_settings(f"model.{ MODEL_CLIENT }.auth", SETTINGS.MODEL_AUTH if SETTINGS.MODEL_AUTH else {})
)
if hasattr(SETTINGS, "DEBUG"):
    agent.set_settings("is_debug", SETTINGS.DEBUG)
if hasattr(SETTINGS, "MODEL_URL"):
    agent.set_settings(f"model.{ MODEL_CLIENT }.url", SETTINGS.MODEL_URL)
if hasattr(SETTINGS, "MODEL_OPTIONS"):
    agent.set_settings(f"model.{ MODEL_CLIENT }.options", SETTINGS.MODEL_OPTIONS)
if hasattr(SETTINGS, "PROXY"):
    agent.set_settings("proxy", SETTINGS.PROXY)

controller_info, controller_desc_info = create_controller_info(SETTINGS.CONTROLLERS)

workflow.public_storage.update_by_dict({
    "status": SETTINGS.INITIAL_STATUS,
    "controller_info": controller_info,
    "controller_desc_info": controller_desc_info,
})

app = Agently.AppConnector()

def message_handler(message, chat_history):
    try:
        workflow.start(message, storage = {
            "$app": app,
            "$agent": agent,
            "chat_history": chat_history,
        })
        app.emit_done()
    except Exception as e:
        logger.error(f"Error: { str(e) }", exc_info=True)
        app.emit_delta("[Error]: " + str(e))
        app.emit_done()

(
    app.use_app("gradio")
        .set_message_handler(message_handler)
        .run(launch={"server_name": "0.0.0.0"})
)