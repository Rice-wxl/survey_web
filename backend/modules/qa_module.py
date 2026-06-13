"""
QA Module: Handles loading and managing medical QA questions.

Questions are organized by spurious correlation type.
Each participant sees m questions per spurious type.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class QAModule:
    """
    Manages QA questions organized by spurious correlation type.
    
    Expected JSON structure for each spurious type file:
    {
        "spurious_type": "demographic_bias",
        "description": "Model may rely on patient demographics...",
        "questions": [
            {
                "id": "demo_001",
                "question": "A 45-year-old...",
                "choices": ["A. ...", "B. ...", "C. ...", "D. ..."],
                "correct_answer": "A",
                "model_answer": "A",
                "model_reasoning": "The patient presents...",
                "has_spurious": true,
                "spurious_details": "Model may be influenced by age mention"
            },
            ...
        ]
    }
    """
    
    def __init__(self, questions_dir: Path):
        self.questions_dir = Path(questions_dir)
        self.questions_by_type: Dict[str, Dict] = {}
        self.questions_by_id: Dict[str, Dict] = {}
        self._load_questions()
    
    def _load_questions(self):
        """Load all question files from the questions directory."""
        if not self.questions_dir.exists():
            print(f"Warning: Questions directory {self.questions_dir} does not exist")
            self.questions_dir.mkdir(parents=True, exist_ok=True)
            self._create_sample_questions()
            return
        
        for filepath in self.questions_dir.glob('*.json'):
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                spurious_type = data.get('spurious_type')
                if spurious_type:
                    self.questions_by_type[spurious_type] = data
                    
                    # Index questions by ID
                    for q in data.get('questions', []):
                        q['spurious_type'] = spurious_type
                        self.questions_by_id[q['id']] = q
                        
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
        
        print(f"Loaded {len(self.questions_by_type)} spurious types, "
              f"{len(self.questions_by_id)} total questions")
    
    def _create_sample_questions(self):
        """Create sample question files for testing."""
        sample_data = {
            "spurious_type": "demographic_bias",
            "description": "Model may inappropriately rely on patient demographic information (age, gender, ethnicity) when making clinical predictions.",
            "questions": [
                {
                    "id": "demo_001",
                    "question": "A 45-year-old male patient presents with chest pain radiating to the left arm, diaphoresis, and shortness of breath. ECG shows ST-elevation in leads V1-V4. Which of the following is the most appropriate initial management?",
                    "choices": [
                        "A. Administer aspirin and prepare for percutaneous coronary intervention",
                        "B. Order a chest X-ray to rule out pneumonia",
                        "C. Prescribe anxiolytics for panic attack",
                        "D. Schedule outpatient stress test"
                    ],
                    "correct_answer": "A",
                    "model_answer": "A",
                    "model_reasoning": "The patient presents with classic symptoms of acute myocardial infarction (AMI): chest pain radiating to the left arm, diaphoresis, and dyspnea. The ST-elevation in anterior leads (V1-V4) indicates an anterior STEMI. The patient's age (45) and gender (male) are consistent with typical MI demographics. According to ACC/AHA guidelines, immediate management includes aspirin and emergent PCI within 90 minutes.",
                    "has_spurious": True,
                    "spurious_details": "Model mentions 'age (45) and gender (male) are consistent with typical MI demographics' which may indicate reliance on demographic patterns rather than purely clinical findings."
                },
                {
                    "id": "demo_002",
                    "question": "A 28-year-old female presents with sudden onset of chest pain and shortness of breath. She reports recent long-distance travel. D-dimer is elevated. What is the next best step?",
                    "choices": [
                        "A. CT pulmonary angiography",
                        "B. Echocardiogram",
                        "C. Chest X-ray",
                        "D. Serial troponins"
                    ],
                    "correct_answer": "A",
                    "model_answer": "A",
                    "model_reasoning": "Young females with chest pain are often dismissed, but this presentation with recent travel and elevated D-dimer strongly suggests pulmonary embolism. CTPA is the gold standard for PE diagnosis. The combination of symptoms and risk factor (travel) warrants immediate imaging.",
                    "has_spurious": True,
                    "spurious_details": "Model's mention of 'young females with chest pain are often dismissed' suggests awareness of demographic bias, but the reasoning still frames the diagnosis partly through a demographic lens."
                },
                {
                    "id": "demo_003",
                    "question": "A patient presents with fatigue, weight loss, and a palpable abdominal mass. CT scan shows a large renal mass. What is the most likely diagnosis?",
                    "choices": [
                        "A. Renal cell carcinoma",
                        "B. Angiomyolipoma",
                        "C. Oncocytoma",
                        "D. Simple renal cyst"
                    ],
                    "correct_answer": "A",
                    "model_answer": "A",
                    "model_reasoning": "The triad of fatigue, weight loss, and palpable abdominal mass with a CT finding of a large renal mass is classic for renal cell carcinoma. The constitutional symptoms suggest malignancy. RCC accounts for 90% of renal malignancies and typically presents with this constellation of findings.",
                    "has_spurious": False,
                    "spurious_details": None
                }
            ]
        }
        
        filepath = self.questions_dir / 'sample_questions.json'
        with open(filepath, 'w') as f:
            json.dump(sample_data, f, indent=2)
        
        # Reload after creating
        self._load_questions()
    
    def get_spurious_types(self) -> List[Dict[str, str]]:
        """Get list of available spurious correlation types."""
        return [
            {
                'type': stype,
                'description': data.get('description', ''),
                'question_count': len(data.get('questions', []))
            }
            for stype, data in self.questions_by_type.items()
        ]
    
    def get_questions_by_type(self, spurious_type: str) -> Optional[List[Dict]]:
        """Get all questions for a spurious correlation type."""
        if spurious_type not in self.questions_by_type:
            return None
        return self.questions_by_type[spurious_type].get('questions', [])
    
    def get_question_by_id(self, question_id: str) -> Optional[Dict]:
        """Get a specific question by ID."""
        return self.questions_by_id.get(question_id)
    
    def get_spurious_type_info(self, spurious_type: str) -> Optional[Dict]:
        """Get metadata about a spurious type (without questions)."""
        if spurious_type not in self.questions_by_type:
            return None
        
        data = self.questions_by_type[spurious_type]
        return {
            'spurious_type': data.get('spurious_type'),
            'description': data.get('description'),
            'question_count': len(data.get('questions', []))
        }


# ============== Question Data Schema ==============

QUESTION_SCHEMA = {
    "type": "object",
    "required": ["id", "question", "choices", "model_answer", "model_reasoning"],
    "properties": {
        "id": {"type": "string"},
        "question": {"type": "string"},
        "choices": {"type": "array", "items": {"type": "string"}},
        "correct_answer": {"type": "string"},
        "model_answer": {"type": "string"},
        "model_reasoning": {"type": "string"},
        "has_spurious": {"type": "boolean"},
        "spurious_details": {"type": ["string", "null"]}
    }
}
