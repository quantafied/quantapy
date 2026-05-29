from quantapy.registry.constants import VALID_COMPONENT_CATEGORIES

COMPONENT_REGISTRY = {}

def register_component(category: str, function: str, source: str = None, **metadata):
    """Register a component class under category/function/source keys."""
    def decorator(cls):
        """Add a class to the global component registry."""
        cat = category
        func = function
        src = (source or "default")

        if cat not in VALID_COMPONENT_CATEGORIES:
            raise ValueError(f"Invalid category '{cat}'. Must be one of: {VALID_COMPONENT_CATEGORIES}")

        COMPONENT_REGISTRY.setdefault(cat, {})
        COMPONENT_REGISTRY[cat].setdefault(func, {})
        COMPONENT_REGISTRY[cat][func][src] = cls  # Store class directly, no wrapper
        return cls
    return decorator
