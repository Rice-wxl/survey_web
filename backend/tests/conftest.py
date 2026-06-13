"""
Pytest configuration and shared fixtures for backend tests.

This module provides common test fixtures used across all test modules,
including temporary directories, sample data, and Flask test clients.
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
import sys

# Add backend directory to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


@pytest.fixture
def temp_dir():
    """
    Creates a temporary directory for test files.
    The directory is automatically cleaned up after the test.
    """
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_questions_data():
    """
    Provides sample question data matching the expected JSON schema.
    Used for testing the QA module's loading and retrieval functions.
    """
    return {
        "spurious_type": "test_bias",
        "description": "Test bias type for unit testing",
        "questions": [
            {
                "id": "test_001",
                "question": "A 50-year-old patient presents with symptoms. What is the diagnosis?",
                "choices": [
                    "A. Condition A",
                    "B. Condition B",
                    "C. Condition C",
                    "D. Condition D"
                ],
                "correct_answer": "A",
                "model_answer": "A",
                "model_reasoning": "Based on the symptoms presented, the diagnosis is Condition A.",
                "has_spurious": True,
                "spurious_details": "Model may rely on patient age inappropriately."
            },
            {
                "id": "test_002",
                "question": "What treatment is recommended for this condition?",
                "choices": [
                    "A. Treatment X",
                    "B. Treatment Y",
                    "C. Treatment Z",
                    "D. No treatment"
                ],
                "correct_answer": "B",
                "model_answer": "B",
                "model_reasoning": "Treatment Y is the standard of care.",
                "has_spurious": False,
                "spurious_details": None
            }
        ]
    }


@pytest.fixture
def sample_questions_file(temp_dir, sample_questions_data):
    """
    Creates a temporary JSON file containing sample questions.
    Returns the path to the questions directory.
    """
    questions_dir = temp_dir / "questions"
    questions_dir.mkdir(parents=True, exist_ok=True)

    filepath = questions_dir / "test_questions.json"
    with open(filepath, 'w') as f:
        json.dump(sample_questions_data, f)

    return questions_dir


@pytest.fixture
def multiple_spurious_types_dir(temp_dir):
    """
    Creates a directory with multiple spurious type question files.
    Tests the QA module's ability to load and manage multiple categories.
    """
    questions_dir = temp_dir / "questions"
    questions_dir.mkdir(parents=True, exist_ok=True)

    # Create multiple question files
    spurious_types = [
        {
            "spurious_type": "demographic_bias",
            "description": "Demographic-related biases",
            "questions": [
                {
                    "id": "demo_001",
                    "question": "Test demographic question",
                    "choices": ["A", "B", "C", "D"],
                    "correct_answer": "A",
                    "model_answer": "A",
                    "model_reasoning": "Test reasoning",
                    "has_spurious": True,
                    "spurious_details": "Age bias"
                }
            ]
        },
        {
            "spurious_type": "temporal_bias",
            "description": "Time-related biases",
            "questions": [
                {
                    "id": "temp_001",
                    "question": "Test temporal question",
                    "choices": ["A", "B", "C", "D"],
                    "correct_answer": "B",
                    "model_answer": "B",
                    "model_reasoning": "Test reasoning",
                    "has_spurious": False,
                    "spurious_details": None
                }
            ]
        }
    ]

    for data in spurious_types:
        filepath = questions_dir / f"{data['spurious_type']}.json"
        with open(filepath, 'w') as f:
            json.dump(data, f)

    return questions_dir


@pytest.fixture
def flask_app():
    """
    Creates a Flask test application with test configuration.
    Provides isolated testing environment for API endpoints.
    """
    from app import app
    app.config['TESTING'] = True
    return app


@pytest.fixture
def flask_client(flask_app):
    """
    Creates a Flask test client for making HTTP requests.
    """
    return flask_app.test_client()


@pytest.fixture
def mock_model():
    """
    Creates a mock model object for testing interpretability tools.
    Simulates the model interface without loading actual weights.
    """
    class MockModel:
        def __init__(self):
            self.model = None
            self.tokenizer = MockTokenizer()
            self.device = 'cpu'

    class MockTokenizer:
        def __init__(self):
            self.pad_token = '<pad>'
            self.eos_token = '<eos>'

        def __call__(self, text, return_tensors='pt', **kwargs):
            # Simple mock tokenization
            tokens = text.split()
            return {'input_ids': [[i for i in range(len(tokens))]]}

        def tokenize(self, text):
            return text.split()

        def convert_ids_to_tokens(self, ids):
            return [f"token_{i}" for i in ids]

    return MockModel()


@pytest.fixture
def survey_responses_valid():
    """
    Provides valid survey responses for testing validation logic.
    """
    return {
        'q1_clinically_sound': 'Yes',
        'q3_inference_method': ['From the model\'s reasoning text', 'From my clinical knowledge/intuition'],
        'q4_confidence': 4
    }


@pytest.fixture
def survey_responses_invalid():
    """
    Provides invalid survey responses for testing error handling.
    """
    return {
        'q1_clinically_sound': 'Invalid Option',  # Invalid option
        'q4_confidence': 10  # Out of range
    }
