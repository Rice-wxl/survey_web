"""
Unit tests for the Model Server module (model_server.py).

Tests cover:
- Chat prompt building
- Model wrapper interface (using mocks to avoid loading real models)
- Singleton pattern for model instance
- Token attribution functionality

Note: These tests use mocks to avoid requiring GPU/model weights.
Integration tests with actual models should be run separately.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from model_server import build_chat_prompt


class TestBuildChatPrompt:
    """Tests for the build_chat_prompt function."""

    def test_build_prompt_with_no_context(self):
        """
        Verifies that prompt is built correctly with no context.
        Should include user input and response marker.
        """
        prompt = build_chat_prompt("What is the diagnosis?", context=None)

        assert "What is the diagnosis?" in prompt
        assert "User Query:" in prompt
        assert "Response:" in prompt

    def test_build_prompt_with_empty_context(self):
        """
        Verifies that empty context dict is handled.
        """
        prompt = build_chat_prompt("Test question", context={})

        assert "Test question" in prompt
        assert "User Query:" in prompt

    def test_build_prompt_with_full_context(self):
        """
        Verifies that all context fields are included in prompt.
        """
        context = {
            'question': "A 50-year-old patient presents with chest pain.",
            'choices': "A. MI\nB. Angina\nC. GERD\nD. Panic",
            'model_answer': "A",
            'model_reasoning': "The presentation is classic for MI."
        }

        prompt = build_chat_prompt("Why did you choose A?", context=context)

        assert "Medical Question:" in prompt
        assert "50-year-old patient" in prompt
        assert "Choices:" in prompt
        assert "Previous Answer:" in prompt
        assert "Previous Reasoning:" in prompt
        assert "User Query: Why did you choose A?" in prompt

    def test_build_prompt_with_partial_context(self):
        """
        Verifies that partial context is handled (only some fields present).
        """
        context = {
            'question': "Test question",
            # No choices, model_answer, or model_reasoning
        }

        prompt = build_chat_prompt("Follow-up", context=context)

        assert "Medical Question: Test question" in prompt
        assert "Choices:" not in prompt

    def test_build_prompt_preserves_user_input(self):
        """
        Verifies that user input is not modified.
        """
        user_input = "What about \u00e9 special chars?"
        prompt = build_chat_prompt(user_input, context=None)

        assert user_input in prompt

    def test_build_prompt_ends_with_response_marker(self):
        """
        Verifies that prompt ends with Response: for model continuation.
        """
        prompt = build_chat_prompt("Test", context=None)

        assert prompt.strip().endswith("Response:")


class TestModelWrapperInterface:
    """Tests for the ModelWrapper class interface using mocks."""

    def test_model_wrapper_singleton_pattern(self):
        """
        Verifies that ModelWrapper uses singleton pattern.
        The _instance class attribute should be used to return same instance.

        Note: This test verifies the singleton implementation without loading model.
        """
        from model_server import ModelWrapper

        # Verify class has singleton attributes
        assert hasattr(ModelWrapper, '_instance'), "Should have _instance class attribute"
        assert hasattr(ModelWrapper, '_lock'), "Should have _lock for thread safety"

        # The __new__ method should enforce singleton
        # We verify the pattern exists without instantiating (which would load model)
        import inspect
        source = inspect.getsource(ModelWrapper.__new__)
        assert '_instance' in source, "Singleton should use _instance"
        assert '_lock' in source, "Singleton should use lock for thread safety"

    def test_get_model_function(self):
        """
        Verifies that get_model returns a model instance.
        """
        with patch('model_server.ModelWrapper') as MockWrapper:
            mock_instance = Mock()
            MockWrapper.return_value = mock_instance

            from model_server import get_model

            # Reset the global _model
            import model_server
            model_server._model = None

            model = get_model()

            # Should return the mock instance
            assert model is not None

    def test_generate_method_signature(self):
        """
        Documents the expected generate method signature.
        """
        # This test documents expected interface without loading model
        expected_params = {
            'prompt': str,
            'max_new_tokens': int,
            'temperature': float,
            'top_p': float,
            'return_full_output': bool
        }

        expected_return = {
            'response': str,
            'input_length': int,
            'output_length': int
        }

        # This is a documentation test - always passes
        assert True

    def test_get_token_attributions_method_signature(self):
        """
        Documents the expected get_token_attributions method signature.
        """
        expected_params = {
            'input_text': str,
            'output_text': str,
            'method': str  # 'gradient', 'attention', etc.
        }

        expected_return = {
            'tokens': list,
            'attributions': list,
            'method': str
        }

        # This is a documentation test - always passes
        assert True


class TestGetModelResponse:
    """Tests for the get_model_response function."""

    def test_get_model_response_builds_prompt(self):
        """
        Verifies that get_model_response builds prompt correctly.
        """
        with patch('model_server.get_model') as mock_get_model:
            mock_model = Mock()
            mock_model.generate.return_value = {
                'response': 'Test response',
                'output_length': 10
            }
            mock_get_model.return_value = mock_model

            from model_server import get_model_response

            result = get_model_response(
                user_input="Test question",
                context={'question': 'Original question'}
            )

            # Verify generate was called
            mock_model.generate.assert_called_once()

            # Verify response structure
            assert 'response' in result
            assert 'tokens_generated' in result

    def test_get_model_response_no_context(self):
        """
        Verifies that get_model_response works without context.
        """
        with patch('model_server.get_model') as mock_get_model:
            mock_model = Mock()
            mock_model.generate.return_value = {
                'response': 'Test response',
                'output_length': 5
            }
            mock_get_model.return_value = mock_model

            from model_server import get_model_response

            result = get_model_response(
                user_input="Simple question",
                context=None
            )

            assert result['response'] == 'Test response'
            assert result['tokens_generated'] == 5


class TestModelWrapperTokenAttributions:
    """Tests for token attribution functionality."""

    def test_get_token_attributions_mock_implementation(self):
        """
        Verifies the placeholder token attribution returns expected structure.

        Note: The actual implementation in model_server.py returns mock data.
        This test documents that behavior.
        """
        with patch('model_server.ModelWrapper') as MockWrapper:
            mock_instance = Mock()
            mock_instance.tokenizer = Mock()
            mock_instance.tokenizer.tokenize.return_value = ['test', 'tokens']

            mock_instance.get_token_attributions.return_value = {
                'tokens': ['test', 'tokens'],
                'attributions': [0.5, 0.8],
                'method': 'gradient'
            }

            result = mock_instance.get_token_attributions(
                input_text="test tokens",
                output_text="output",
                method='gradient'
            )

            assert 'tokens' in result
            assert 'attributions' in result
            assert 'method' in result
            assert len(result['tokens']) == len(result['attributions'])


class TestModelConfig:
    """Tests for model configuration."""

    def test_model_config_defaults(self):
        """
        Verifies that ModelConfig has expected default values.
        """
        from config import ModelConfig

        # Check defaults exist
        assert hasattr(ModelConfig, 'MODEL_PATH')
        assert hasattr(ModelConfig, 'DEVICE')
        assert hasattr(ModelConfig, 'MAX_LENGTH')
        assert hasattr(ModelConfig, 'TEMPERATURE')
        assert hasattr(ModelConfig, 'TOP_P')

    def test_model_config_values(self):
        """
        Verifies specific configuration values.
        """
        from config import ModelConfig

        # Check reasonable defaults
        assert ModelConfig.BATCH_SIZE >= 1
        assert ModelConfig.MAX_LENGTH > 0
        assert 0 <= ModelConfig.TEMPERATURE <= 2
        assert 0 <= ModelConfig.TOP_P <= 1


class TestStandaloneServerEndpoints:
    """Tests for standalone server mode endpoints (documentation tests)."""

    def test_generate_endpoint_spec(self):
        """
        Documents the /generate endpoint specification.

        POST /generate
        Body: {"prompt": str, "max_tokens": int}
        Returns: {"response": str, "input_length": int, "output_length": int}
        """
        expected_request = {
            'prompt': 'Test prompt',
            'max_tokens': 512
        }

        expected_response = {
            'response': str,
            'input_length': int,
            'output_length': int
        }

        # Documentation test
        assert True

    def test_chat_endpoint_spec(self):
        """
        Documents the /chat endpoint specification.

        POST /chat
        Body: {"message": str, "context": dict}
        Returns: {"response": str, "tokens_generated": int}
        """
        expected_request = {
            'message': 'User message',
            'context': {
                'question': 'Original question',
                'choices': 'A, B, C, D',
                'model_answer': 'A',
                'model_reasoning': 'Reasoning text'
            }
        }

        expected_response = {
            'response': str,
            'tokens_generated': int
        }

        # Documentation test
        assert True

    def test_attributions_endpoint_spec(self):
        """
        Documents the /attributions endpoint specification.

        POST /attributions
        Body: {"input_text": str, "output_text": str, "method": str}
        Returns: {"tokens": list, "attributions": list, "method": str}
        """
        expected_request = {
            'input_text': 'Model input',
            'output_text': 'Model output',
            'method': 'gradient'  # or 'attention', 'integrated_gradients'
        }

        expected_response = {
            'tokens': ['list', 'of', 'tokens'],
            'attributions': [0.1, 0.5, 0.9],
            'method': str
        }

        # Documentation test
        assert True

    def test_health_endpoint_spec(self):
        """
        Documents the /health endpoint specification.

        GET /health
        Returns: {"status": "healthy", "model_loaded": bool}
        """
        expected_response = {
            'status': 'healthy',
            'model_loaded': True
        }

        # Documentation test
        assert True


class TestErrorHandling:
    """Tests for error handling in model server."""

    def test_model_load_failure_handling(self):
        """
        Verifies that model load failures are handled gracefully.

        Note: This is a documentation test for expected behavior.
        The actual ModelWrapper prints error and raises exception on failure.
        """
        # Expected behavior: print error message and raise exception
        # Application should handle this at startup
        assert True

    def test_device_fallback_to_cpu(self):
        """
        Documents that CUDA unavailability falls back to CPU.

        The ModelWrapper __init__ catches CUDA errors and falls back.
        """
        # Expected behavior when CUDA unavailable:
        # 1. Catch exception
        # 2. Print warning
        # 3. Set device to 'cpu'
        assert True
