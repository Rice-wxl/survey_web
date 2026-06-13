"""
Unit tests for the QA Module (qa_module.py).

Tests cover:
- Loading questions from JSON files
- Retrieving questions by spurious type
- Retrieving individual questions by ID
- Handling missing or malformed data
- Automatic sample question generation
"""

import pytest
import json
from pathlib import Path
import sys

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from modules.qa_module import QAModule, QUESTION_SCHEMA


class TestQAModuleInitialization:
    """Tests for QAModule initialization and question loading."""

    def test_init_with_existing_questions_directory(self, sample_questions_file):
        """
        Verifies that QAModule correctly loads questions from an existing directory.
        The module should populate questions_by_type and questions_by_id dictionaries.
        """
        qa = QAModule(sample_questions_file)

        # Verify questions were loaded
        assert len(qa.questions_by_type) > 0, "Should load at least one spurious type"
        assert len(qa.questions_by_id) > 0, "Should index questions by ID"

    def test_init_with_nonexistent_directory_creates_samples(self, temp_dir):
        """
        Verifies that QAModule creates sample questions when directory doesn't exist.
        This ensures new installations have working demo data.
        """
        questions_dir = temp_dir / "nonexistent_questions"

        qa = QAModule(questions_dir)

        # Directory should be created
        assert questions_dir.exists(), "Should create questions directory"
        # Sample questions should be generated
        assert len(qa.questions_by_type) > 0, "Should create sample questions"

    def test_init_with_empty_directory(self, temp_dir):
        """
        Verifies behavior when questions directory exists but is empty.
        Should handle gracefully without errors.
        """
        questions_dir = temp_dir / "empty_questions"
        questions_dir.mkdir(parents=True)

        qa = QAModule(questions_dir)

        assert len(qa.questions_by_type) == 0, "Should have no spurious types"
        assert len(qa.questions_by_id) == 0, "Should have no questions"

    def test_loads_multiple_spurious_types(self, multiple_spurious_types_dir):
        """
        Verifies that QAModule correctly loads multiple spurious type files.
        Each file should be indexed separately by its spurious_type field.
        """
        qa = QAModule(multiple_spurious_types_dir)

        assert len(qa.questions_by_type) == 2, "Should load both spurious types"
        assert "demographic_bias" in qa.questions_by_type
        assert "temporal_bias" in qa.questions_by_type

    def test_handles_malformed_json_gracefully(self, temp_dir):
        """
        Verifies that malformed JSON files don't crash the module.
        Invalid files should be skipped with a warning.
        """
        questions_dir = temp_dir / "questions"
        questions_dir.mkdir(parents=True)

        # Create a malformed JSON file
        malformed_file = questions_dir / "malformed.json"
        with open(malformed_file, 'w') as f:
            f.write("{invalid json content")

        # Should not raise an exception
        qa = QAModule(questions_dir)
        assert qa.questions_by_type is not None

    def test_skips_files_without_spurious_type(self, temp_dir):
        """
        Verifies that JSON files without a spurious_type field are skipped.
        Only properly formatted question files should be loaded.
        """
        questions_dir = temp_dir / "questions"
        questions_dir.mkdir(parents=True)

        # Create a JSON file without spurious_type
        invalid_file = questions_dir / "invalid.json"
        with open(invalid_file, 'w') as f:
            json.dump({"questions": []}, f)

        qa = QAModule(questions_dir)
        assert len(qa.questions_by_type) == 0


class TestQAModuleRetrieval:
    """Tests for question retrieval methods."""

    def test_get_spurious_types_returns_correct_structure(self, sample_questions_file):
        """
        Verifies get_spurious_types returns list with type, description, and count.
        Each entry should contain metadata about available spurious types.
        """
        qa = QAModule(sample_questions_file)
        spurious_types = qa.get_spurious_types()

        assert isinstance(spurious_types, list)
        assert len(spurious_types) > 0

        # Check structure of first entry
        first_type = spurious_types[0]
        assert 'type' in first_type, "Should include type identifier"
        assert 'description' in first_type, "Should include description"
        assert 'question_count' in first_type, "Should include question count"

    def test_get_spurious_types_accurate_count(self, sample_questions_file, sample_questions_data):
        """
        Verifies that question_count matches actual number of questions.
        """
        qa = QAModule(sample_questions_file)
        spurious_types = qa.get_spurious_types()

        expected_count = len(sample_questions_data['questions'])
        actual_count = spurious_types[0]['question_count']
        assert actual_count == expected_count

    def test_get_questions_by_type_valid_type(self, sample_questions_file):
        """
        Verifies retrieval of questions for a valid spurious type.
        Should return a list of question dictionaries.
        """
        qa = QAModule(sample_questions_file)
        questions = qa.get_questions_by_type("test_bias")

        assert questions is not None, "Should return questions for valid type"
        assert isinstance(questions, list)
        assert len(questions) == 2, "Should return all questions in the type"

    def test_get_questions_by_type_invalid_type_returns_none(self, sample_questions_file):
        """
        Verifies that requesting a non-existent spurious type returns None.
        """
        qa = QAModule(sample_questions_file)
        questions = qa.get_questions_by_type("nonexistent_type")

        assert questions is None, "Should return None for invalid type"

    def test_get_question_by_id_valid_id(self, sample_questions_file):
        """
        Verifies retrieval of a specific question by its ID.
        Should return the full question dictionary with all fields.
        """
        qa = QAModule(sample_questions_file)
        question = qa.get_question_by_id("test_001")

        assert question is not None, "Should return question for valid ID"
        assert question['id'] == "test_001"
        assert 'question' in question
        assert 'choices' in question
        assert 'model_answer' in question
        assert 'model_reasoning' in question

    def test_get_question_by_id_invalid_id_returns_none(self, sample_questions_file):
        """
        Verifies that requesting a non-existent question ID returns None.
        """
        qa = QAModule(sample_questions_file)
        question = qa.get_question_by_id("nonexistent_id")

        assert question is None, "Should return None for invalid ID"

    def test_get_question_by_id_includes_spurious_type(self, sample_questions_file):
        """
        Verifies that retrieved questions include their spurious_type.
        This is added during loading for cross-referencing.
        """
        qa = QAModule(sample_questions_file)
        question = qa.get_question_by_id("test_001")

        assert 'spurious_type' in question, "Should include spurious_type field"
        assert question['spurious_type'] == "test_bias"

    def test_get_spurious_type_info_valid_type(self, sample_questions_file):
        """
        Verifies get_spurious_type_info returns metadata without questions.
        Useful for displaying category information without loading all questions.
        """
        qa = QAModule(sample_questions_file)
        info = qa.get_spurious_type_info("test_bias")

        assert info is not None
        assert 'spurious_type' in info
        assert 'description' in info
        assert 'question_count' in info
        # Should NOT include the full questions list
        assert 'questions' not in info

    def test_get_spurious_type_info_invalid_type(self, sample_questions_file):
        """
        Verifies get_spurious_type_info returns None for invalid type.
        """
        qa = QAModule(sample_questions_file)
        info = qa.get_spurious_type_info("nonexistent_type")

        assert info is None


class TestQAModuleDataIntegrity:
    """Tests for data integrity and consistency."""

    def test_all_questions_have_required_fields(self, sample_questions_file):
        """
        Verifies that all loaded questions contain required fields.
        Required fields: id, question, choices, model_answer, model_reasoning.
        """
        qa = QAModule(sample_questions_file)
        required_fields = ['id', 'question', 'choices', 'model_answer', 'model_reasoning']

        for q_id, question in qa.questions_by_id.items():
            for field in required_fields:
                assert field in question, f"Question {q_id} missing required field: {field}"

    def test_choices_is_list(self, sample_questions_file):
        """
        Verifies that the choices field is always a list.
        """
        qa = QAModule(sample_questions_file)

        for q_id, question in qa.questions_by_id.items():
            assert isinstance(question['choices'], list), f"Question {q_id} choices should be a list"
            assert len(question['choices']) > 0, f"Question {q_id} should have at least one choice"

    def test_question_ids_are_unique(self, multiple_spurious_types_dir):
        """
        Verifies that question IDs are unique across all spurious types.
        Duplicate IDs would cause incorrect lookups.
        """
        qa = QAModule(multiple_spurious_types_dir)

        # Get all question IDs from all types
        all_ids = []
        for stype in qa.questions_by_type:
            questions = qa.get_questions_by_type(stype)
            all_ids.extend([q['id'] for q in questions])

        # Check for duplicates
        assert len(all_ids) == len(set(all_ids)), "Question IDs should be unique"


class TestQAModuleSampleGeneration:
    """Tests for sample question generation."""

    def test_creates_sample_questions_file(self, temp_dir):
        """
        Verifies that sample questions are written to a file.
        """
        questions_dir = temp_dir / "new_questions"
        qa = QAModule(questions_dir)

        # Check that a sample file was created
        json_files = list(questions_dir.glob("*.json"))
        assert len(json_files) > 0, "Should create sample questions file"

    def test_sample_questions_are_valid(self, temp_dir):
        """
        Verifies that generated sample questions have valid structure.
        """
        questions_dir = temp_dir / "new_questions"
        qa = QAModule(questions_dir)

        # Sample should have questions
        assert len(qa.questions_by_id) > 0, "Should generate sample questions"

        # Each question should be valid
        for q_id, question in qa.questions_by_id.items():
            assert 'question' in question
            assert 'choices' in question
            assert len(question['choices']) == 4, "Sample questions should have 4 choices"
