"""
Unit tests for the Interpretability Tools module.

Tests cover:
- BaseInterpretabilityTool abstract class
- MockInterpretabilityTool implementation
- TokenAttributionTool (mock mode and real mode)
- Tool registry and factory functions
- Visualization configuration
"""

import pytest
import numpy as np
from pathlib import Path
import sys

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from modules.interp_tools.base_tool import (
    BaseInterpretabilityTool,
    MockInterpretabilityTool,
    InterpretabilityResult
)
from modules.interp_tools.token_attribution import TokenAttributionTool
from modules.interp_tools import (
    TOOL_REGISTRY,
    get_tool_by_name,
    list_available_tools,
    register_tool,
    clear_tool_cache,
    get_tool_from_preset,
    TOOL_PRESETS
)


class TestInterpretabilityResult:
    """Tests for the InterpretabilityResult dataclass."""

    def test_result_creation(self):
        """
        Verifies that InterpretabilityResult can be created with all fields.
        """
        result = InterpretabilityResult(
            tool_name="test_tool",
            display_name="Test Tool",
            result_type="token_attribution",
            data={'tokens': ['a', 'b'], 'attributions': [0.5, 0.7]},
            metadata={'method': 'gradient'}
        )

        assert result.tool_name == "test_tool"
        assert result.display_name == "Test Tool"
        assert result.result_type == "token_attribution"
        assert 'tokens' in result.data

    def test_result_to_dict(self):
        """
        Verifies that to_dict serializes result correctly for JSON.
        """
        result = InterpretabilityResult(
            tool_name="test_tool",
            display_name="Test Tool",
            result_type="heatmap",
            data={'matrix': [[0.1, 0.2], [0.3, 0.4]]}
        )

        d = result.to_dict()

        assert isinstance(d, dict)
        assert d['tool_name'] == "test_tool"
        assert d['metadata'] == {}  # Default when None

    def test_result_metadata_default(self):
        """
        Verifies that metadata defaults to empty dict when None.
        """
        result = InterpretabilityResult(
            tool_name="test",
            display_name="Test",
            result_type="test",
            data={}
        )

        d = result.to_dict()
        assert d['metadata'] == {}


class TestMockInterpretabilityTool:
    """Tests for the MockInterpretabilityTool class."""

    def test_mock_tool_class_attributes(self):
        """
        Verifies that MockInterpretabilityTool has correct class attributes.
        """
        assert MockInterpretabilityTool.name == "mock_tool"
        assert MockInterpretabilityTool.display_name == "Mock Tool (Testing)"
        assert MockInterpretabilityTool.result_type == "token_attribution"

    def test_mock_tool_initialization(self):
        """
        Verifies that MockInterpretabilityTool can be initialized without a model.
        """
        tool = MockInterpretabilityTool(model=None, config={})

        assert tool.model is None
        assert tool.config == {}

    def test_mock_tool_compute_returns_tokens_and_attributions(self):
        """
        Verifies that compute returns tokens and attribution scores.
        """
        tool = MockInterpretabilityTool()
        result = tool.compute(
            input_text="This is a test input",
            output_text="Model output text"
        )

        assert 'tokens' in result, "Should return tokens"
        assert 'attributions' in result, "Should return attributions"
        assert len(result['tokens']) == len(result['attributions']), \
            "Tokens and attributions should have same length"

    def test_mock_tool_attributions_normalized(self):
        """
        Verifies that mock attributions are normalized to [0, 1].
        """
        tool = MockInterpretabilityTool()
        result = tool.compute(
            input_text="This is a longer test input with multiple words",
            output_text="Output"
        )

        attributions = result['attributions']
        assert all(0 <= a <= 1 for a in attributions), \
            "All attributions should be in [0, 1]"
        assert max(attributions) == 1.0, \
            "Maximum attribution should be normalized to 1.0"

    def test_mock_tool_limits_tokens(self):
        """
        Verifies that mock tool limits the number of tokens to prevent huge outputs.
        """
        tool = MockInterpretabilityTool()
        # Create a very long input
        long_input = " ".join(["word"] * 100)
        result = tool.compute(
            input_text=long_input,
            output_text="Output"
        )

        assert len(result['tokens']) <= 50, "Should limit tokens to 50"

    def test_mock_tool_visualization_config(self):
        """
        Verifies that get_visualization_config returns correct structure.
        """
        tool = MockInterpretabilityTool()
        config = tool.get_visualization_config()

        assert 'type' in config
        assert config['type'] == 'token_highlight'
        assert 'color_scale' in config
        assert 'interactive' in config
        assert 'legend' in config

    def test_mock_tool_get_info(self):
        """
        Verifies that get_info returns tool metadata.
        """
        tool = MockInterpretabilityTool()
        info = tool.get_info()

        assert info['name'] == 'mock_tool'
        assert info['display_name'] == 'Mock Tool (Testing)'
        assert 'description' in info
        assert info['result_type'] == 'token_attribution'


class TestTokenAttributionTool:
    """Tests for the TokenAttributionTool class."""

    def test_token_attribution_class_attributes(self):
        """
        Verifies that TokenAttributionTool has correct class attributes.
        """
        assert TokenAttributionTool.name == "token_attribution"
        assert TokenAttributionTool.display_name == "Token Attribution"
        assert TokenAttributionTool.result_type == "token_attribution"

    def test_token_attribution_default_config(self):
        """
        Verifies default configuration values.
        """
        tool = TokenAttributionTool()

        assert tool.method == 'gradient'  # Default method
        assert tool.num_steps == 50  # For integrated gradients

    def test_token_attribution_custom_config(self):
        """
        Verifies that custom config is applied.
        """
        tool = TokenAttributionTool(config={
            'method': 'attention',
            'num_steps': 100,
            'aggregate_layers': False
        })

        assert tool.method == 'attention'
        assert tool.num_steps == 100
        assert tool.aggregate_layers is False

    def test_token_attribution_mock_mode_without_model(self):
        """
        Verifies that tool works in mock mode when no model is provided.
        This allows testing the frontend without loading a real model.
        """
        tool = TokenAttributionTool(model=None)
        result = tool.compute(
            input_text="Test patient presents with symptoms",
            output_text="Diagnosis is condition A"
        )

        assert 'tokens' in result
        assert 'attributions' in result
        assert result['method'] == 'mock'
        assert result['visualization_type'] == 'token_highlight'

    def test_token_attribution_mock_keyword_highlighting(self):
        """
        Verifies that mock mode gives higher attribution to medical keywords.
        This simulates realistic attribution patterns for testing.
        """
        tool = TokenAttributionTool(model=None)
        result = tool.compute(
            input_text="patient symptom diagnosis treatment age male",
            output_text="Output"
        )

        tokens = result['tokens']
        attributions = result['attributions']

        # Find indices of keywords
        keyword_indices = [i for i, t in enumerate(tokens)
                          if t.lower() in ['patient', 'symptom', 'diagnosis', 'treatment']]
        demographic_indices = [i for i, t in enumerate(tokens)
                              if t.lower() in ['age', 'male']]

        # Keywords should generally have higher attribution in mock mode
        if keyword_indices:
            keyword_attrs = [attributions[i] for i in keyword_indices]
            # At least one keyword should have moderate-high attribution
            assert any(a > 0.3 for a in keyword_attrs)

    def test_token_attribution_normalize_attributions(self):
        """
        Verifies that _normalize_attributions works correctly.
        """
        tool = TokenAttributionTool()

        # Test normal case
        attrs = np.array([0.1, 0.5, 0.9])
        normalized = tool._normalize_attributions(attrs)
        assert normalized.min() == 0.0
        assert normalized.max() == 1.0

        # Test edge case: all same values
        attrs = np.array([0.5, 0.5, 0.5])
        normalized = tool._normalize_attributions(attrs)
        assert all(n == 0 for n in normalized), "All same values should normalize to zeros"

    def test_token_attribution_visualization_config(self):
        """
        Verifies visualization config structure for frontend rendering.
        """
        tool = TokenAttributionTool()
        config = tool.get_visualization_config()

        assert config['type'] == 'token_highlight'
        assert 'color_scale' in config
        assert config['color_scale']['type'] == 'sequential'
        assert 'colors' in config['color_scale']
        assert config['interactive'] is True
        assert config['show_scores'] is True
        assert 'legend' in config

    def test_token_attribution_validate_input(self):
        """
        Verifies that input validation works correctly.
        """
        tool = TokenAttributionTool()

        assert tool.validate_input("valid input", "valid output") is True
        assert tool.validate_input("", "output") is False
        assert tool.validate_input("input", "") is False
        assert tool.validate_input("", "") is False


class TestToolRegistry:
    """Tests for the tool registry and factory functions."""

    def test_tool_registry_contains_default_tools(self):
        """
        Verifies that TOOL_REGISTRY contains the expected default tools.
        """
        assert 'token_attribution' in TOOL_REGISTRY
        assert 'mock_tool' in TOOL_REGISTRY

    def test_get_tool_by_name_valid(self):
        """
        Verifies that get_tool_by_name returns correct tool instance.
        """
        tool = get_tool_by_name('mock_tool', use_cache=False)

        assert tool is not None
        assert isinstance(tool, MockInterpretabilityTool)

    def test_get_tool_by_name_invalid(self):
        """
        Verifies that get_tool_by_name returns None for invalid names.
        """
        tool = get_tool_by_name('nonexistent_tool')

        assert tool is None

    def test_get_tool_by_name_with_config(self):
        """
        Verifies that custom config is passed to tool.
        """
        tool = get_tool_by_name(
            'token_attribution',
            config={'method': 'attention'},
            use_cache=False
        )

        assert tool.method == 'attention'

    def test_get_tool_by_name_caching(self):
        """
        Verifies that tool instances are cached when use_cache=True.
        """
        clear_tool_cache()

        tool1 = get_tool_by_name('mock_tool', use_cache=True)
        tool2 = get_tool_by_name('mock_tool', use_cache=True)

        assert tool1 is tool2, "Should return same cached instance"

    def test_get_tool_by_name_no_caching(self):
        """
        Verifies that new instances are created when use_cache=False.
        """
        tool1 = get_tool_by_name('mock_tool', use_cache=False)
        tool2 = get_tool_by_name('mock_tool', use_cache=False)

        assert tool1 is not tool2, "Should return different instances"

    def test_list_available_tools(self):
        """
        Verifies that list_available_tools returns info for all registered tools.
        """
        tools = list_available_tools()

        assert isinstance(tools, list)
        assert len(tools) >= 2  # At least mock_tool and token_attribution

        # Check structure
        for tool_info in tools:
            assert 'name' in tool_info
            assert 'display_name' in tool_info
            assert 'description' in tool_info
            assert 'result_type' in tool_info

    def test_list_available_tools_names(self):
        """
        Verifies that expected tools are listed.
        """
        tools = list_available_tools()
        tool_names = [t['name'] for t in tools]

        assert 'mock_tool' in tool_names
        assert 'token_attribution' in tool_names

    def test_register_tool_valid(self):
        """
        Verifies that new tools can be registered dynamically.
        """
        # Create a custom tool class
        class CustomTool(BaseInterpretabilityTool):
            name = "custom_test_tool"
            display_name = "Custom Test"
            description = "A custom test tool"
            result_type = "custom"

            def compute(self, input_text, output_text, **kwargs):
                return {'custom': 'data'}

            def get_visualization_config(self):
                return {'type': 'custom'}

        # Register it
        register_tool('custom_test_tool', CustomTool)

        assert 'custom_test_tool' in TOOL_REGISTRY

        # Clean up
        del TOOL_REGISTRY['custom_test_tool']

    def test_register_tool_invalid_class(self):
        """
        Verifies that registering non-BaseInterpretabilityTool raises error.
        """
        class NotATool:
            pass

        with pytest.raises(TypeError):
            register_tool('invalid', NotATool)

    def test_clear_tool_cache(self):
        """
        Verifies that clear_tool_cache removes cached instances.
        """
        # Cache a tool
        tool1 = get_tool_by_name('mock_tool', use_cache=True)

        # Clear cache
        clear_tool_cache()

        # Get again - should be new instance
        tool2 = get_tool_by_name('mock_tool', use_cache=True)

        assert tool1 is not tool2


class TestToolPresets:
    """Tests for tool configuration presets."""

    def test_presets_defined(self):
        """
        Verifies that expected presets are defined.
        """
        assert 'token_attribution_gradient' in TOOL_PRESETS
        assert 'token_attribution_ig' in TOOL_PRESETS
        assert 'token_attribution_attention' in TOOL_PRESETS

    def test_preset_structure(self):
        """
        Verifies preset structure contains tool and config.
        """
        for name, preset in TOOL_PRESETS.items():
            assert 'tool' in preset, f"Preset {name} should have 'tool'"
            assert 'config' in preset, f"Preset {name} should have 'config'"

    def test_get_tool_from_preset_valid(self):
        """
        Verifies that get_tool_from_preset creates correctly configured tool.
        """
        tool = get_tool_from_preset('token_attribution_attention')

        assert tool is not None
        assert isinstance(tool, TokenAttributionTool)
        assert tool.method == 'attention'

    def test_get_tool_from_preset_invalid(self):
        """
        Verifies that invalid preset name returns None.
        """
        tool = get_tool_from_preset('nonexistent_preset')

        assert tool is None

    def test_get_tool_from_preset_ig_config(self):
        """
        Verifies integrated gradients preset has correct config.
        """
        tool = get_tool_from_preset('token_attribution_ig')

        assert tool.method == 'integrated_gradients'
        assert tool.num_steps == 50


class TestToolEdgeCases:
    """Tests for edge cases and error handling."""

    def test_compute_with_empty_input(self):
        """
        Verifies behavior with empty input text.
        """
        tool = MockInterpretabilityTool()
        result = tool.compute(input_text="", output_text="output")

        # Should handle gracefully
        assert 'tokens' in result
        assert len(result['tokens']) == 0 or result['tokens'] == []

    def test_compute_with_special_characters(self):
        """
        Verifies that special characters in input are handled.
        """
        tool = MockInterpretabilityTool()
        result = tool.compute(
            input_text="Test with special chars: @#$%^&*()",
            output_text="Output"
        )

        assert 'tokens' in result
        assert 'attributions' in result

    def test_compute_with_unicode(self):
        """
        Verifies that unicode characters are handled.
        """
        tool = MockInterpretabilityTool()
        result = tool.compute(
            input_text="Test with unicode: \u00e9\u00e8\u00ea",
            output_text="Output"
        )

        assert 'tokens' in result

    def test_tool_with_none_config(self):
        """
        Verifies that None config is handled gracefully.
        """
        tool = TokenAttributionTool(model=None, config=None)

        # Should use defaults
        assert tool.method == 'gradient'

    def test_compute_with_question_id(self):
        """
        Verifies that question_id parameter is accepted.
        """
        tool = MockInterpretabilityTool()
        result = tool.compute(
            input_text="Test input",
            output_text="Output",
            question_id="test_001"
        )

        assert 'tokens' in result  # Should work without errors
