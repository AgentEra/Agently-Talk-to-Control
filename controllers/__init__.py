from __future__ import annotations

import copy
import importlib
from typing import Any


def create_controller_info(controller_settings: dict[str, Any]):
    controller_info = copy.deepcopy(controller_settings)
    controllers = importlib.import_module(".controllers", package="controllers")

    for controller_name, config in controller_info.items():
        controller_info[controller_name]["func"] = getattr(controllers, config["func"])
        controller_args = {}
        for arg_name, arg_config in config.get("args", {}).items():
            controller_args[arg_name] = (
                arg_config.get("$type", "str"),
                arg_config.get("$desc", ""),
            )
        controller_info[controller_name]["args"] = controller_args

    controller_desc_info = {}
    for controller_name, config in controller_info.items():
        controller_desc_info[controller_name] = {
            "desc": config["desc"],
            "args": list(config["args"].keys()),
        }

    return controller_info, controller_desc_info
