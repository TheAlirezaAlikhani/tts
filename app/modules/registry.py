"""
Module Registry - Factory for creating module instances by name
"""
from typing import Dict, Type
from app.modules.base import BaseModule
from app.modules.hospital import HospitalModule
from app.modules.hotel import HotelModule
from app.modules.internet_sales import InternetSalesModule


# Registry mapping module names to their classes
MODULE_REGISTRY: Dict[str, Type[BaseModule]] = {
    "hospital": HospitalModule,
    "hotel": HotelModule,
    "internet_sales": InternetSalesModule,
}


def get_module_by_name(module_name: str) -> BaseModule:
    """
    Get a module instance by its name
    
    Args:
        module_name: Name of the module (e.g., "hospital", "hotel")
        
    Returns:
        Instance of the requested module
        
    Raises:
        ValueError: If module_name is not found in registry
    """
    if not module_name:
        raise ValueError("Module name is required")
    
    module_class = MODULE_REGISTRY.get(module_name)
    if not module_class:
        available_modules = ", ".join(MODULE_REGISTRY.keys())
        raise ValueError(
            f"Module '{module_name}' not found in registry. "
            f"Available modules: {available_modules}"
        )
    
    return module_class()


def get_available_modules() -> list[str]:
    """
    Get list of all available module names
    
    Returns:
        List of module names
    """
    return list(MODULE_REGISTRY.keys())
