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
                options=["Yes", "No"],
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
                text="Do you think the model made its prediction based on clinically valid reasoning, regardless of correctness?",
                question_type=QuestionType.SINGLE_CHOICE,
                options=["Yes", "No"],
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
                    "show_when": ["No"]
                },
                min_question_index=1
            ),
            SurveyQuestion(
                id="q3_invalid_description",
                text="In what way is the reasoning clinically invalid?",
                question_type=QuestionType.FREE_TEXT,
                required=True,
                max_length=500,
                condition={
                    "depends_on": "q2_clinically_valid",
                    "show_when": ["No"]
                },
                help_text="Describe any patterns, features, or correlations you noticed that seem clinically inappropriate."
            ),
            SurveyQuestion(
                id="q4_inference_method",
                text="How did you arrive at your conclusion? (Select all that apply)",
                question_type=QuestionType.MULTIPLE_CHOICE,
                options=[
                    "From the model's reasoning text",
                    "From the interpretability interface visualization",
                    "From testing via the chat interface",
                    "From my clinical knowledge/intuition",
                    "Other"
                ],
                required=True
            ),
            SurveyQuestion(
                id="q4_inference_elaboration",
                text="Please elaborate on how you reached your conclusion:",
                question_type=QuestionType.FREE_TEXT,
                required=False,
                max_length=1000,
                condition={
                    "depends_on": "q4_inference_method",
                    "show_when_includes": ["Other"]
                },
                help_text="Describe your thought process and what evidence most influenced your assessment."
            )
        ]
    
    def _build_batch_survey(self) -> List[SurveyQuestion]:
        """Build the end-of-batch survey template."""
        return [
            SurveyQuestion(
                id="batch_q1_tool_usefulness",
                text="The interpretability interface was helpful in determining whether the model uses clinically valid reasoning in this batch of questions.",
                question_type=QuestionType.LIKERT,
                likert_min=1,
                likert_max=5,
                likert_labels={
                    1: "Strongly Disagree",
                    2: "Disagree",
                    3: "Neutral",
                    4: "Agree",
                    5: "Strongly Agree"
                },
                required=True
            ),
            SurveyQuestion(
                id="batch_q2_tool_clarity",
                text="The interpretability interface's visualizations were clear and easy to understand.",
                question_type=QuestionType.LIKERT,
                likert_min=1,
                likert_max=5,
                likert_labels={
                    1: "Strongly Disagree",
                    2: "Disagree",
                    3: "Neutral",
                    4: "Agree",
                    5: "Strongly Agree"
                },
                required=True
            ),
            SurveyQuestion(
                id="batch_q3_chat_usefulness",
                text="The interactive chat feature was helpful in understanding the model's behavior in this batch of questions.",
                question_type=QuestionType.LIKERT,
                likert_min=1,
                likert_max=5,
                likert_labels={
                    1: "Strongly Disagree",
                    2: "Disagree",
                    3: "Neutral",
                    4: "Agree",
                    5: "Strongly Agree"
                },
                required=True
            ),
            SurveyQuestion(
                id="batch_q4_comments",
                text="Any additional comments on the interpretability tool or the evaluation process?",
                question_type=QuestionType.FREE_TEXT,
                required=False,
                max_length=2000
            )
        ]
    
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
                if q2_val != 'No':
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