import importlib
import importlib.util
import os
import pkgutil
import sys

def load_plugins_from_folder(folder_path: str):
    """Import every non-private Python module in a folder to trigger registration."""
    if not os.path.isdir(folder_path):
        return
    for filename in os.listdir(folder_path):
        if filename.endswith(".py") and not filename.startswith("_"):
            module_name = filename[:-3]
            module_path = os.path.join(folder_path, filename)

            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)


def load_plugins_from_package(package_name: str) -> None:
    """Import all modules below a package to trigger plugin registration."""
    package = importlib.import_module(package_name)
    package_paths = getattr(package, "__path__", None)
    if package_paths is None:
        return
    for module_info in pkgutil.walk_packages(package_paths, prefix=f"{package_name}."):
        name = module_info.name
        if any(part.startswith("_") for part in name.split(".")):
            continue
        importlib.import_module(name)
