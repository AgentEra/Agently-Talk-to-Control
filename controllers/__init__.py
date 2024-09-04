import copy
import importlib
def create_controller_info(controller_info_settings: dict):
    controller_info_dict = copy.deepcopy(dict(controller_info_settings))
    controllers = importlib.import_module(".controllers", package="controllers")
    for controller_name, controller_info in controller_info_dict.items():
        controller_info_dict[controller_name].update({
            "func": getattr(controllers, controller_info["func"])
        })
        controller_args = {}
        for arg_name, arg_info in controller_info["args"].items():
            controller_args.update({
                arg_name: (arg_info["$type"] if "$type" in arg_info else "", arg_info["$desc"] if "$desc" in arg_info else "")
            })
        controller_info_dict[controller_name].update({ "args": controller_args })
    controller_info_desc_dict = {}
    for controller_name in controller_info_dict.keys():
        controller_info_desc_dict.update({ controller_name: {
            "desc": controller_info_dict[controller_name]["desc"],
            "args": list(controller_info_dict[controller_name].keys())
    } })
    return controller_info_dict, controller_info_desc_dict
