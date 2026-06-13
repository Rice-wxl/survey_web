"""
Unit tests for the Survey Module (survey_module.py).

Tests cover:
- Survey question creation and structure
- Question type handling (single choice, multiple choice, Likert, free text)
- Response validation for each question type
- Conditional question logic
- Error handling for invalid responses
"""

import pytest
from pathlib import Path
import sys

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from modules.survey_module import SurveyModule, SurveyQuestion, QuestionType


class TestQuestionType:
    """Tests for the QuestionType enum."""

    def test_question_type_values(self):
        """
        Verifies that all expected question types are defined.
        These types determine how questions are rendered and validated.
        """
        assert QuestionType.SINGLE_CHOICE.value == "single_choice"
        assert QuestionType.MULTIPLE_CHOICE.value == "multiple_choice"
        assert QuestionType.LIKERT.value == "likert"
        assert QuestionType.FREE_TEXT.value == "free_text"
        assert QuestionType.CONDITIONAL.value == "conditional"


class TestSurveyQuestion:
    """Tests for the SurveyQuestion dataclass."""

    def test_survey_question_creation_minimal(self):
        """
        Verifies that a SurveyQuestion can be created with minimal required fields.
        """
        question = SurveyQuestion(
            id="test_q1",
            text="Test question?",
            question_type=QuestionType.SINGLE_CHOICE,
            options=["Yes", "No"]
        )

        assert question.id == "test_q1"
        assert question.text == "Test question?"
        assert question.question_type == QuestionType.SINGLE_CHOICE
        assert question.required is True  # Default value

    def test_survey_question_to_dict(self):
        """
        Verifies that to_dict serializes the question correctly.
        question_type should be converted to string value for JSON compatibility.
        """
        question = SurveyQuestion(
            id="test_q1",
            text="Test question?",
            question_type=QuestionType.LIKERT,
            likert_min=1,
            likert_max=5,
            likert_labels={1: "Low", 5: "High"}
        )

        result = question.to_dict()

        assert result['id'] == "test_q1"
        assert result['question_type'] == "likert"  # String, not enum
        assert result['likert_min'] == 1
        assert result['likert_max'] == 5
        assert result['likert_labels'] == {1: "Low", 5: "High"}

    def test_survey_question_defaults(self):
        """
        Verifies default values for optional fields.
        """
        question = SurveyQuestion(
            id="q1",
            text="Text",
            question_type=QuestionType.FREE_TEXT
        )

        assert question.options is None
        assert question.required is True
        assert question.min_length is None
        assert question.max_length is None
        assert question.likert_min == 1
        assert question.likert_max == 5
        assert question.condition is None
        assert question.help_text is None


class TestSurveyModuleStructure:
    """Tests for SurveyModule initialization and structure."""

    def test_survey_module_initialization(self):
        """
        Verifies that SurveyModule initializes with both survey types.
        """
        survey = SurveyModule()

        assert survey.per_question_survey is not None
        assert survey.batch_survey is not None
        assert len(survey.per_question_survey) > 0
        assert len(survey.batch_survey) > 0

    def test_per_question_survey_has_expected_questions(self):
        """
        Verifies that per-question survey contains the expected questions.
        These questions are asked after each medical QA evaluation.
        """
        survey = SurveyModule()
        question_ids = [q.id for q in survey.per_question_survey]

        # Check for key questions that should be present
        assert 'q1_answer_correct' in question_ids, "Should ask if model answer is correct"
        assert 'q1_confidence' in question_ids, "Should ask confidence for Q1"
        assert 'q2_clinically_valid' in question_ids, "Should ask about clinically valid reasoning"
        assert 'q2_confidence' in question_ids, "Should ask confidence for Q2"
        assert 'q4_inference_method' in question_ids, "Should ask about inference method"

    def test_batch_survey_has_expected_questions(self):
        """
        Verifies that batch survey contains tool evaluation questions.
        These questions are asked at the end of each spurious type batch.
        """
        survey = SurveyModule()
        question_ids = [q.id for q in survey.batch_survey]

        assert 'batch_q1_tool_usefulness' in question_ids, "Should ask about tool usefulness"
        assert 'batch_q2_tool_clarity' in question_ids, "Should ask about tool clarity"
        assert 'batch_q3_chat_usefulness' in question_ids, "Should ask about chat usefulness"

    def test_get_questions_returns_both_types(self):
        """
        Verifies that get_questions returns both survey types as dicts.
        """
        survey = SurveyModule()
        questions = survey.get_questions()

        assert 'per_question' in questions
        assert 'batch' in questions
        assert isinstance(questions['per_question'], list)
        assert isinstance(questions['batch'], list)

    def test_get_questions_serializes_properly(self):
        """
        Verifies that get_questions returns serializable dictionaries.
        All questions should be converted via to_dict for JSON compatibility.
        """
        survey = SurveyModule()
        questions = survey.get_questions()

        # First per-question should be a dict, not SurveyQuestion
        first_q = questions['per_question'][0]
        assert isinstance(first_q, dict)
        assert 'question_type' in first_q
        # question_type should be string, not enum
        assert isinstance(first_q['question_type'], str)


class TestSurveyValidation:
    """Tests for response validation logic."""

    def test_validate_valid_per_question_responses(self):
        """
        Verifies that valid per-question responses pass validation.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is True
        assert len(result['errors']) == 0

    def test_validate_missing_required_field(self):
        """
        Verifies that missing required fields cause validation failure.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            # Missing q2_clinically_valid, q2_confidence, q4_inference_method
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False
        assert len(result['errors']) > 0

        # Check that errors identify the missing fields
        error_ids = [e['question_id'] for e in result['errors']]
        assert 'q2_clinically_valid' in error_ids
        assert 'q4_inference_method' in error_ids

    def test_validate_single_choice_invalid_option(self):
        """
        Verifies that invalid single choice options are rejected.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Invalid Option',  # Not in options
            'q1_confidence': 3,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False
        error_ids = [e['question_id'] for e in result['errors']]
        assert 'q1_answer_correct' in error_ids

    def test_validate_multiple_choice_expects_list(self):
        """
        Verifies that multiple choice responses must be a list.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': 'Not a list',  # Should be a list
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False
        error_ids = [e['question_id'] for e in result['errors']]
        assert 'q4_inference_method' in error_ids

    def test_validate_multiple_choice_invalid_options(self):
        """
        Verifies that multiple choice rejects invalid options in the list.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['Valid', 'Invalid Option'],  # Contains invalid
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False

    def test_validate_likert_out_of_range(self):
        """
        Verifies that Likert responses outside valid range are rejected.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 10,  # Out of range (should be 1-5)
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False
        error_ids = [e['question_id'] for e in result['errors']]
        assert 'q1_confidence' in error_ids

    def test_validate_likert_non_numeric(self):
        """
        Verifies that non-numeric Likert responses are rejected.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 'not a number',
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False

    def test_validate_free_text_max_length(self):
        """
        Verifies that free text maximum length is enforced.
        """
        survey = SurveyModule()
        # q3_invalid_description has max_length of 500
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'No',
            'q2_confidence': 3,
            'q3_invalid_description': 'x' * 600,  # Exceeds 500 chars
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses, question_index=0)

        assert result['valid'] is False


class TestConditionalQuestions:
    """Tests for conditional question visibility logic."""

    def test_conditional_question_hidden_when_condition_not_met(self):
        """
        Verifies that conditional questions are skipped when condition isn't met.
        q3_invalid_description should only show when q2_clinically_valid is 'No'.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',  # conditional questions should be hidden
            'q2_confidence': 3,
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses, question_index=0)

        # Should be valid because conditional questions are hidden
        assert result['valid'] is True

    def test_conditional_question_required_when_condition_met(self):
        """
        Verifies that conditional questions are validated when condition is met.
        When q2_clinically_valid is 'No' at question_index=0, q3_invalid_description is required.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'No',
            'q1_confidence': 4,
            'q2_clinically_valid': 'No',
            'q2_confidence': 3,
            'q3_invalid_description': 'The model relies on demographic factors rather than clinical symptoms.',
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses, question_index=0)

        assert result['valid'] is True

    def test_conditional_question_missing_when_required(self):
        """
        Verifies that q3_invalid_description is required when q2_clinically_valid is 'No'.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'No',
            'q1_confidence': 4,
            'q2_clinically_valid': 'No',
            'q2_confidence': 3,
            # q3_invalid_description is missing
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses, question_index=0)

        assert result['valid'] is False
        error_ids = [e['question_id'] for e in result['errors']]
        assert 'q3_invalid_description' in error_ids

    def test_same_as_before_hidden_at_index_0(self):
        """
        Verifies that q3_same_as_before is hidden at question_index=0.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'No',
            'q2_confidence': 3,
            'q3_invalid_description': 'Uses spurious correlation.',
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses, question_index=0)

        # q3_same_as_before should be skipped at index 0
        assert result['valid'] is True

    def test_same_as_before_shown_at_index_1(self):
        """
        Verifies that q3_same_as_before is required at question_index >= 1 when q2=No.
        Selecting 'Same as before' should skip q3_invalid_description.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'No',
            'q2_confidence': 3,
            'q3_same_as_before': 'Same as before',
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses, question_index=1)

        # q3_invalid_description should be hidden because "Same as before"
        assert result['valid'] is True

    def test_different_requires_description_at_index_1(self):
        """
        Verifies that selecting 'Different' at index >= 1 requires q3_invalid_description.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'No',
            'q2_confidence': 3,
            'q3_same_as_before': 'Different',
            # q3_invalid_description missing
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses, question_index=1)

        assert result['valid'] is False
        error_ids = [e['question_id'] for e in result['errors']]
        assert 'q3_invalid_description' in error_ids

    def test_show_when_includes_for_elaboration(self):
        """
        Verifies that q4_inference_elaboration is required only when 'Other' is selected.
        """
        survey = SurveyModule()
        # Without "Other" - elaboration not required
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses)
        assert result['valid'] is True

        # With "Other" - elaboration is optional (required=False) but should be visible
        responses2 = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['Other'],
        }

        result2 = survey.validate_response('per_question', responses2)
        assert result2['valid'] is True  # elaboration is optional


class TestBatchSurveyValidation:
    """Tests specific to batch survey validation."""

    def test_validate_valid_batch_responses(self):
        """
        Verifies that valid batch survey responses pass validation.
        """
        survey = SurveyModule()
        responses = {
            'batch_q1_tool_usefulness': 4,
            'batch_q2_tool_clarity': 5,
            'batch_q3_chat_usefulness': 3,
            'batch_q4_comments': 'Optional comment'
        }

        result = survey.validate_response('batch', responses)

        assert result['valid'] is True

    def test_validate_batch_optional_comments(self):
        """
        Verifies that batch comments field is optional.
        """
        survey = SurveyModule()
        responses = {
            'batch_q1_tool_usefulness': 4,
            'batch_q2_tool_clarity': 5,
            'batch_q3_chat_usefulness': 3
            # batch_q4_comments omitted - should be optional
        }

        result = survey.validate_response('batch', responses)

        assert result['valid'] is True

    def test_validate_batch_missing_required_likert(self):
        """
        Verifies that missing required Likert questions fail validation.
        """
        survey = SurveyModule()
        responses = {
            'batch_q1_tool_usefulness': 4
            # Missing batch_q2 and batch_q3
        }

        result = survey.validate_response('batch', responses)

        assert result['valid'] is False


class TestValidationErrorMessages:
    """Tests for validation error message quality."""

    def test_error_contains_question_id(self):
        """
        Verifies that errors include the question_id for frontend mapping.
        """
        survey = SurveyModule()
        responses = {}  # All missing

        result = survey.validate_response('per_question', responses)

        for error in result['errors']:
            assert 'question_id' in error
            assert 'error' in error

    def test_error_message_descriptive(self):
        """
        Verifies that error messages are descriptive enough to display.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Invalid'
        }

        result = survey.validate_response('per_question', responses)

        for error in result['errors']:
            assert len(error['error']) > 0, "Error message should not be empty"


class TestEmptyResponses:
    """Tests for handling empty or edge case responses."""

    def test_validate_empty_string_treated_as_missing(self):
        """
        Verifies that empty strings are treated as missing for required fields.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': '',  # Empty string
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False

    def test_validate_empty_list_for_multiple_choice(self):
        """
        Verifies that empty list for required multiple choice fails validation.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': 'Yes',
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': [],  # Empty list
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False

    def test_validate_none_value(self):
        """
        Verifies that None values are treated as missing.
        """
        survey = SurveyModule()
        responses = {
            'q1_answer_correct': None,
            'q1_confidence': 4,
            'q2_clinically_valid': 'Yes',
            'q2_confidence': 3,
            'q4_inference_method': ['From the model\'s reasoning text'],
        }

        result = survey.validate_response('per_question', responses)

        assert result['valid'] is False
