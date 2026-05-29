import importlib.util
import os
import sys

def load_plugins_from_folder(folder_path: str):
    """Import every non-private Python module in a folder to trigger registration."""
    for filename in os.listdir(folder_path):
        if filename.endswith(".py") and not filename.startswith("_"):
            module_name = filename[:-3]
            module_path = os.path.join(folder_path, filename)

            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
