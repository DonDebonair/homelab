import types
from typing import Any

def module_to_clean_dict(mod: types.ModuleType) -> dict[str, Any]:
    """
    Converts a module to a dictionary of its public, non-callable attributes.
    """
    return {
        key: value
        for key, value in vars(mod).items()
        if not key.startswith('_') and not callable(value)
    }

def normalize_vars(variables: dict[str, Any] | types.ModuleType) -> dict[str, Any]:
    """
    Accepts either a dict or a module and returns a cleaned dict representation.
    """
    if isinstance(variables, dict):
        return variables
    elif isinstance(variables, types.ModuleType):
        return module_to_clean_dict(variables)
    else:
        raise TypeError(f"Expected dict or module, got {type(variables)}")
