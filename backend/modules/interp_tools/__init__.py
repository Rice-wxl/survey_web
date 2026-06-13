"""
Interpretability Tools Module

This module provides a registry of available interpretability tools.
Tools can be dynamically loaded and swapped per question/batch.

To add a new tool:
1. Create a new file (e.g., my_tool.py)
2. Implement a class inheriting from BaseInterpretabilityTool
3. Register it in TOOL_REGISTRY below
"""

from typing import Dict, List, Optional, Type
from .base_tool import BaseInterpretabilityTool, MockInterpretabilityTool
from .token_attribution import TokenAttributionTool

# ============== Tool Registry ==============
# Add new tools here as they are implemented

TOOL_REGISTRY: Dict[str, Type[BaseInterpretabilityTool]] = {
    'token_attribution': TokenAttributionTool,
    'mock_tool': MockInterpretabilityTool,
    # Future tools:
    # 'attention_visualization': AttentionVisualizationTool,
    # 'concept_activation': ConceptActivationTool,
    # 'layer_attribution': LayerAttributionTool,
}

# Tool instances cache (for tools that need initialization)
_tool_instances: Dict[str, BaseInterpretabilityTool] = {}


def get_tool_by_name(
    tool_name: str,
    model=None,
    config: Dict = None,
    use_cache: bool = True
) -> Optional[BaseInterpretabilityTool]:
    """
    Get an interpretability tool by name.
    
    Args:
        tool_name: Name of the tool (key in TOOL_REGISTRY)
        model: Optional model instance for tools that need direct access
        config: Tool-specific configuration
        use_cache: Whether to reuse existing tool instances
        
    Returns:
        Tool instance or None if not found
    """
    if tool_name not in TOOL_REGISTRY:
        return None
    
    cache_key = f"{tool_name}_{id(model)}"
    
    if use_cache and cache_key in _tool_instances:
        return _tool_instances[cache_key]
    
    tool_class = TOOL_REGISTRY[tool_name]
    tool_instance = tool_class(model=model, config=config or {})
    
    if use_cache:
        _tool_instances[cache_key] = tool_instance
    
    return tool_instance


def list_available_tools() -> List[Dict[str, str]]:
    """
    List all available interpretability tools.
    
    Returns:
        List of tool info dictionaries
    """
    tools = []
    for name, tool_class in TOOL_REGISTRY.items():
        # Create temporary instance to get info
        temp_tool = tool_class(model=None, config={})
        tools.append(temp_tool.get_info())
    return tools


def register_tool(name: str, tool_class: Type[BaseInterpretabilityTool]):
    """
    Register a new interpretability tool.
    
    Args:
        name: Unique name for the tool
        tool_class: Tool class (must inherit from BaseInterpretabilityTool)
    """
    if not issubclass(tool_class, BaseInterpretabilityTool):
        raise TypeError("Tool class must inherit from BaseInterpretabilityTool")
    
    TOOL_REGISTRY[name] = tool_class


def clear_tool_cache():
    """Clear the tool instance cache."""
    _tool_instances.clear()


# ============== Tool Configuration Presets ==============
# Predefined configurations for common use cases

TOOL_PRESETS = {
    'token_attribution_gradient': {
        'tool': 'token_attribution',
        'config': {'method': 'gradient'}
    },
    'token_attribution_ig': {
        'tool': 'token_attribution',
        'config': {'method': 'integrated_gradients', 'num_steps': 50}
    },
    'token_attribution_attention': {
        'tool': 'token_attribution',
        'config': {'method': 'attention', 'aggregate_layers': True}
    },
}


def get_tool_from_preset(preset_name: str, model=None) -> Optional[BaseInterpretabilityTool]:
    """
    Get a tool configured with a preset.
    
    Args:
        preset_name: Name of the preset
        model: Optional model instance
        
    Returns:
        Configured tool instance
    """
    if preset_name not in TOOL_PRESETS:
        return None
    
    preset = TOOL_PRESETS[preset_name]
    return get_tool_by_name(
        preset['tool'],
        model=model,
        config=preset.get('config', {}),
        use_cache=False  # Don't cache preset instances
    )
