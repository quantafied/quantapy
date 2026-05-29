# Registry API

QuantaPy uses a global component registry so orchestrators can instantiate
plugins by category, function, and source.

## `register_component`

Location: `quantapy.registry.component_registry.register_component`

Decorator used by modules to register a class:

```python
@register_component(category="Signal", function="Crossover", source="Internal")
class crossover(BaseSignal):
    ...
```

Components are stored as:

```python
COMPONENT_REGISTRY[category][function][source] = cls
```

## `load_plugins_from_folder`

Location: `quantapy.utils.loader.load_plugins_from_folder`

Imports every non-private `.py` file in a folder. Importing a module runs its
registration decorators, which populates `COMPONENT_REGISTRY`.

Example:

```python
load_plugins_from_folder("/path/to/quantapy/modules/strategy")
load_plugins_from_folder("/path/to/quantapy/modules/simulation")
```

