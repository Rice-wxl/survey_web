"""
Base class for interpretability tools.
All interpretability tools should inherit from this class.

This design allows easy swapping of different tools per question/batch.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class InterpretabilityResult:
    """Standard result format for all interpretability tools."""
    tool_name: str
    display_name: str
    result_type: str  # 'token_attribution', 'heatmap', 'concept_scores', etc.
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict:
        return {
            'tool_name': self.tool_name,
            'display_name': self.display_name,
            'result_type': self.result_type,
            'data': self.data,
            'metadata': self.metadata or {}
        }


class BaseInterpretabilityTool(ABC):
    """
    Abstract base class for interpretability tools.
    
    To add a new tool:
    1. Create a new file in interp_tools/
    2. Inherit from BaseInterpretabilityTool
    3. Implement the required methods
    4. Register in __init__.py
    """
    
    # Override these in subclasses
    name: str = "base_tool"
    display_name: str = "Base Tool"
    description: str = "Base interpretability tool"
    result_type: str = "generic"
    
    def __init__(self, model=None, config: Dict = None):
        """
        Initialize the tool.
        
        Args:
            model: Optional model instance (some tools need direct model access)
            config: Tool-specific configuration
        """
        self.model = model
        self.config = config or {}
        self._initialize()
    
    def _initialize(self):
        """
        Override for tool-specific initialization.
        Called after __init__.
        """
        pass
    
    @abstractmethod
    def compute(
        self,
        input_text: str,
        output_text: str,
        question_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compute interpretability analysis.
        
        Args:
            input_text: The input text (question + choices)
            output_text: The model's output (answer + reasoning)
            question_id: Optional question identifier
            **kwargs: Additional tool-specific arguments
            
        Returns:
            Dictionary with tool-specific results
        """
        pass
    
    @abstractmethod
    def get_visualization_config(self) -> Dict[str, Any]:
        """
        Return configuration for frontend visualization.
        
        Returns:
            Dictionary with visualization settings:
            - type: 'token_highlight', 'heatmap', 'bar_chart', etc.
            - color_scale: color configuration
            - interactive: whether the viz supports interaction
            - legend: legend configuration
        """
        pass
    
    def get_info(self) -> Dict[str, str]:
        """Get tool metadata."""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'result_type': self.result_type
        }
    
    def validate_input(self, input_text: str, output_text: str) -> bool:
        """
        Validate inputs before computation.
        Override for tool-specific validation.
        """
        if not input_text or not output_text:
            return False
        return True


class MockInterpretabilityTool(BaseInterpretabilityTool):
    """
    Mock tool for testing frontend without real model.
    """
    
    name = "mock_tool"
    display_name = "Mock Tool (Testing)"
    description = "Generates random attributions for testing"
    result_type = "token_attribution"
    
    def compute(
        self,
        input_text: str,
        output_text: str,
        question_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        import random
        
        # Simple tokenization (split by whitespace)
        tokens = input_text.split()[:50]  # Limit for display
        
        # Generate mock attributions
        attributions = [random.random() for _ in tokens]
        
        # Normalize to [0, 1]
        max_attr = max(attributions) if attributions else 1
        attributions = [a / max_attr for a in attributions]
        
        return {
            'tokens': tokens,
            'attributions': attributions,
            'method': 'mock_random',
            'visualization_type': 'token_highlight'
        }
    
    def get_visualization_config(self) -> Dict[str, Any]:
        return {
            'type': 'token_highlight',
            'color_scale': {
                'low': 'rgba(59, 130, 246, 0.1)',
                'high': 'rgba(59, 130, 246, 0.9)'
            },
            'interactive': True,
            'show_scores': True,
            'legend': {
                'show': True,
                'labels': ['Low Attribution', 'High Attribution']
            }
        }
