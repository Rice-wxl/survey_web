"""
Survey Module

Defines and manages survey questions presented after each QA interaction.
Supports per-question surveys and end-of-batch surveys.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class QuestionType(Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    RANKING = "ranking"  # ordered list of options, most helpful first
    LIKERT = "likert"
    FREE_TEXT = "free_text"
    CONDITIONAL = "conditional"


@dataclass
class SurveyQuestion:
    """Represents a single survey question."""
    id: str
    text: str
    question_type: QuestionType
    options: Optional[List[str]] = None
    required: bool = True
    min_length: Optional[int] = None  # For free text
    max_length: Optional[int] = None
    likert_min: int = 1
    likert_max: int = 5
    likert_labels: Optional[Dict[int, str]] = None
    condition: Optional[Dict[str, Any]] = None  # For conditional questions
    help_text: Optional[str] = None
    min_question_index: Optional[int] = None  # Hide when currentQuestionIndex < this value
    alt_text: Optional[Dict[str, Any]] = None  # {"depends_on", "value", "text"}: reword when parent == value

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['question_type'] = self.question_type.value
        return d


class SurveyModule:
    """
    Manages survey questions and validation.
    """
    
    def __init__(self):
        self.per_question_survey = self._build_per_question_survey()
        self.batch_survey = self._build_batch_survey()
    
    def _build_per_question_survey(self) -> List[SurveyQuestion]:
        """Build the per-question survey template."""
        confidence_labels = {1: "Not at all confident", 5: "Very confident"}
        return [
            SurveyQuestion(
                id="q1_answer_correct",
                text="Is the model's answer correct?",
                question_type=QuestionType.SINGLE_CHOICE,
                options=["Correct", "Incorrect"],
                required=True
            ),
            SurveyQuestion(
                id="q1_confidence",
                text="How confident are you?",
                question_type=QuestionType.LIKERT,
                likert_min=1,
                likert_max=5,
                likert_labels=confidence_labels,
                required=True
            ),
            SurveyQuestion(
                id="q2_clinically_valid",
                text="Do you think the model made its prediction based on clinically biased or unbiased reasoning, regardless of correctness?",
                question_type=QuestionType.SINGLE_CHOICE,
                options=["Biased", "Unbiased"],
                required=True
            ),
            SurveyQuestion(
                id="q2_confidence",
                text="How confident are you?",
                question_type=QuestionType.LIKERT,
                likert_min=1,
                likert_max=5,
                likert_labels=confidence_labels,
                required=True
            ),
            SurveyQuestion(
                id="q3_same_as_before",
                text="Is the pattern of clinically invalid reasoning the same as your previous assessment?",
                question_type=QuestionType.SINGLE_CHOICE,
                options=["Same as before", "Different"],
                required=True,
                condition={
                    "depends_on": "q2_clinically_valid",
                    "show_when": ["Biased"]
                },
                min_question_index=1
            ),
            SurveyQuestion(
                id="q3_invalid_description",
                text="In what way is the reasoning biased?",
                question_type=QuestionType.FREE_TEXT,
                required=True,
                max_length=500,
                condition={
                    "depends_on": "q2_clinically_valid",
                    "show_when": ["Biased"]
                },
                help_text="Describe any patterns, features, or correlations you noticed that seem clinically inappropriate."
            ),
            SurveyQuestion(
                id="q4_inference_method",
                text="Which sources helped you reach your conclusion? Rank only the ones that helped.",
                question_type=QuestionType.RANKING,
                alt_text={
                    "depends_on": "q3_same_as_before",
                    "value": "Same as before",
                    "text": "Which sources helped you confirm that this is the same bias as before? Rank only the ones that helped."
                },
                options=[
                    "From the model's reasoning text",
                    "From the interpretability panel",
                    "From testing via the chat interface",
                    "From my clinical knowledge/intuition",
                    "Other"
                ],
                required=True
            ),
            SurveyQuestion(
                id="q4_inference_elaboration",
                text="What other thing(s) helped you make your decision?",
                question_type=QuestionType.FREE_TEXT,
                required=True,
                max_length=1000,
                condition={
                    "depends_on": "q4_inference_method",
                    "show_when_includes": ["Other"]
                },
            )
        ]
    
    def _build_batch_survey(self) -> List[SurveyQuestion]:
        """End-of-batch (per model): no questions since 2026-10-26. The three usefulness
        ratings (panel / reasoning / chat) repeated the per-question q4 ranking. The screen
        stays as a "model complete" break, and its Continue still saves batch_complete
        (resume_point uses it)."""
        return []

    def get_questions(self) -> Dict[str, Any]:
        """Get all survey questions."""
        return {
            'per_question': [q.to_dict() for q in self.per_question_survey],
            'batch': [q.to_dict() for q in self.batch_survey]
        }
    
    def validate_response(
        self,
        survey_type: str,
        responses: Dict[str, Any],
        question_index: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Validate survey responses.

        Args:
            survey_type: 'per_question' or 'batch'
            responses: Dictionary of question_id -> response
            question_index: Current question index within batch (for index-dependent logic)

        Returns:
            Dictionary with 'valid' boolean and 'errors' list
        """
        questions = self.per_question_survey if survey_type == 'per_question' else self.batch_survey
        errors = []

        for question in questions:
            q_id = question.id
            response = responses.get(q_id)

            # Check min_question_index gating
            if question.min_question_index is not None and question_index is not None:
                if question_index < question.min_question_index:
                    continue

            # Check conditional visibility
            if question.condition:
                depends_on = question.condition.get('depends_on')
                show_when = question.condition.get('show_when', [])
                show_when_includes = question.condition.get('show_when_includes', [])

                parent_response = responses.get(depends_on)

                if show_when_includes:
                    # For multiple_choice parents: check if response array contains any value
                    if not isinstance(parent_response, list) or not any(
                        v in parent_response for v in show_when_includes
                    ):
                        continue
                elif show_when:
                    if parent_response not in show_when:
                        continue

            # Special handling for q3_invalid_description compound visibility
            if q_id == 'q3_invalid_description' and survey_type == 'per_question':
                q2_val = responses.get('q2_clinically_valid')
                if q2_val != 'Biased':
                    continue
                if question_index is not None and question_index > 0:
                    same_as_before = responses.get('q3_same_as_before')
                    if same_as_before != 'Different':
                        continue

            # Check required
            # For required fields: None, empty string, or empty list should fail
            is_empty = (response is None or response == '' or
                        (isinstance(response, list) and len(response) == 0))
            if question.required and is_empty:
                errors.append({
                    'question_id': q_id,
                    'error': 'This question is required'
                })
                continue

            # Skip further validation if optional and empty
            if response is None or response == '':
                continue

            # Type-specific validation
            if question.question_type == QuestionType.SINGLE_CHOICE:
                if response not in question.options:
                    errors.append({
                        'question_id': q_id,
                        'error': f'Invalid option: {response}'
                    })

            elif question.question_type == QuestionType.MULTIPLE_CHOICE:
                if not isinstance(response, list):
                    errors.append({
                        'question_id': q_id,
                        'error': 'Expected a list of selections'
                    })
                elif not all(r in question.options for r in response):
                    errors.append({
                        'question_id': q_id,
                        'error': 'Invalid option(s) selected'
                    })

            elif question.question_type == QuestionType.RANKING:
                # Any non-empty subset of sources may be ranked (emptiness is caught by `required`).
                if (not isinstance(response, list) or len(set(response)) != len(response)
                        or not all(r in question.options for r in response)):
                    errors.append({
                        'question_id': q_id,
                        'error': 'Expected an ordered list of distinct options'
                    })

            elif question.question_type == QuestionType.LIKERT:
                try:
                    value = int(response)
                    if not (question.likert_min <= value <= question.likert_max):
                        errors.append({
                            'question_id': q_id,
                            'error': f'Value must be between {question.likert_min} and {question.likert_max}'
                        })
                except (ValueError, TypeError):
                    errors.append({
                        'question_id': q_id,
                        'error': 'Expected a numeric value'
                    })

            elif question.question_type == QuestionType.FREE_TEXT:
                if question.min_length and len(response) < question.min_length:
                    errors.append({
                        'question_id': q_id,
                        'error': f'Response must be at least {question.min_length} characters'
                    })
                if question.max_length and len(response) > question.max_length:
                    errors.append({
                        'question_id': q_id,
                        'error': f'Response must be at most {question.max_length} characters'
                    })

        return {
            'valid': len(errors) == 0,
            'errors': errors
        }