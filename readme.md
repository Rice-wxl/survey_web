# Interpretability Study Interface

A modular web-based interface for conducting user studies on LLM interpretability tools in medical QA contexts.

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt
```

### 2. Configure Your Model

Edit `backend/config.py` to point to your model:

```python
class ModelConfig:
    MODEL_PATH = './models/your-finetuned-model'
    DEVICE = 'cuda'  # or 'cpu'
```

### 3. Add Your Questions

Create JSON files in `backend/data/questions/`:

```json
{
  "spurious_type": "demographic_bias",
  "description": "Model may rely on patient demographics...",
  "questions": [
    {
      "id": "demo_001",
      "question": "A 45-year-old male patient...",
      "choices": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "model_answer": "A",
      "model_reasoning": "The patient presents...",
      "has_spurious": true
    }
  ]
}
```

### 4. Run the Server

```bash
cd backend
python app.py
```

Open `http://localhost:5000` in your browser.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Browser)                      │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│  QA Display │ Interp Tool │    Chat     │     Survey       │
│   Module    │   Module    │   Module    │     Module       │
└──────┬──────┴──────┬──────┴──────┬──────┴────────┬─────────┘
       │             │             │               │
       └─────────────┴─────────────┴───────────────┘
                           │
                      REST API
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                    Backend (Flask)                           │
├─────────────┬─────────────┬─────────────┬──────────────────┤
│  QA Module  │ Interp Tools│   Survey    │  Model Server    │
│             │  (Swappable)│   Module    │  (Your Model)    │
└─────────────┴─────────────┴─────────────┴──────────────────┘
```

---

## Module Overview

### QA Module (`modules/qa_module.py`)
- Loads questions organized by spurious correlation type
- Provides question retrieval by type or ID
- Sample questions auto-generated on first run

### Interpretability Tools (`modules/interp_tools/`)
- **Base class**: `BaseInterpretabilityTool` - inherit from this
- **Token Attribution**: Gradient-based, integrated gradients, attention
- **Registry**: Add new tools in `__init__.py`

### Survey Module (`modules/survey_module.py`)
- Per-question survey (after each QA)
- Batch survey (after each spurious type)
- Validation and conditional question logic

### Model Server (`model_server.py`)
- Wraps your custom model
- Handles chat interactions
- Can run as separate process if needed

---

## Adding New Interpretability Tools

1. Create `modules/interp_tools/my_tool.py`:

```python
from .base_tool import BaseInterpretabilityTool

class MyTool(BaseInterpretabilityTool):
    name = "my_tool"
    display_name = "My Custom Tool"
    
    def compute(self, input_text, output_text, **kwargs):
        # Your implementation
        return {
            'visualization_type': 'token_highlight',
            'tokens': [...],
            'attributions': [...]
        }
    
    def get_visualization_config(self):
        return {'type': 'token_highlight', ...}
```

2. Register in `modules/interp_tools/__init__.py`:

```python
from .my_tool import MyTool
TOOL_REGISTRY['my_tool'] = MyTool
```

3. Add frontend renderer in `js/modules/interpTools.js` if needed.

---

## Running Model on Separate Server

If your model needs dedicated GPU resources:

```bash
# Terminal 1: Model server
cd backend
python model_server.py  # Runs on port 8000

# Terminal 2: Main app
python app.py  # Runs on port 5000
```

Update `config.py`:
```python
MODEL_SERVER_URL = 'http://localhost:8000'
```

---

## Data Output

Responses saved to `backend/data/responses/{participant_id}.jsonl`:

```json
{"question_id": "demo_001", "survey_responses": {...}, "timing": {...}}
{"question_id": "demo_002", "survey_responses": {...}, "timing": {...}}
{"type": "batch_complete", "usefulness_rating": 4, ...}
```

---

## Study Flow

1. **Introduction** → Participant ID entry
2. **For each spurious type:**
   - Assign interpretability tool (rotated)
   - **For each question:**
     - Display QA + model response
     - Show interpretability visualization
     - Enable chat interaction
     - Collect per-question survey
   - Collect batch survey (tool usefulness)
3. **Completion** screen

---

## Customization Points

| What | Where |
|------|-------|
| Add questions | `backend/data/questions/*.json` |
| Add interp tools | `backend/modules/interp_tools/` |
| Modify survey | `backend/modules/survey_module.py` |
| Change model | `backend/model_server.py` |
| Styling | `frontend/css/styles.css` |
| UI components | `frontend/js/modules/` |
