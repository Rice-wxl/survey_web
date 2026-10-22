# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Interpretability Study Interface - A web-based platform for conducting user studies on LLM interpretability tools in medical QA contexts. Evaluates whether medical QA models make predictions based on clinically sound factors or spurious correlations.

## Read readme.md first

It is the current source of truth (modes, data export, participants, serving). The older
sections below describing GPT-2 `model_server.py`, `qa_module.py`, `interp_tools/` and
`data/questions/` are gone: items/readouts are precomputed by `backend/build_items.py`,
chat goes to vLLM via `serve.sh`, and `app.py` holds the plan/gate/blinding logic.

Python env: `/projects/frink/wang.xil/med_spurious/spurious_inject/finetuning/train/bin/python`
(has Flask). Frontend Jest deps are not installed (NFS makes npm installs crawl).


## Development Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
cd backend
pip install -r requirements.txt
python check_setup.py  # Verify installation

# Run main Flask app (port 5000)
python app.py

# Run separate model server (port 8000, optional)
python model_server.py
```

No build system for frontend - vanilla JavaScript served directly.

## Testing

```bash
# Backend tests (pytest)
cd backend
pip install pytest  # if not already installed
pytest                       # Run all tests
pytest tests/test_qa_module.py  # Run specific test file
pytest -v                    # Verbose output
pytest --tb=short            # Short traceback

# Frontend tests (Jest)
cd frontend
npm install                  # Install Jest (first time only)
npm test                     # Run all tests
npm run test:watch           # Watch mode
npm run test:coverage        # With coverage report
```


## Architecture

```
survey_web/
├── backend/                    # Python Flask API
│   ├── app.py                 # Main Flask app, API endpoints
│   ├── model_server.py        # Model inference server (singleton pattern)
│   ├── config.py              # All configuration (server, model, study settings)
│   ├── modules/
│   │   ├── qa_module.py       # Question loading from JSON
│   │   ├── survey_module.py   # Survey question definitions
│   │   └── interp_tools/      # Interpretability tool implementations
│   │       ├── base_tool.py   # Abstract base class for tools
│   │       └── token_attribution.py  # Gradient/attention attribution
│   └── data/
│       ├── questions/         # JSON files with medical QA by spurious type
│       └── responses/         # JSONL participant logs
│
└── frontend/                   # Vanilla JS + Tailwind CSS (CDN)
    ├── index.html             # Entry point, all HTML templates
    └── js/
        ├── app.js             # Main controller, study flow orchestration
        ├── modules/           # UI components (qaDisplay, chatInterface, interpTools, surveyModule)
        └── utils/             # api.js (fetch wrapper), timer.js
```

## Key API Endpoints

- `POST /api/session/start` - Initialize participant session
- `GET /api/qa/questions/<type>` - Get questions by spurious correlation type
- `POST /api/model/chat` - Chat with model for interactive probing
- `POST /api/interp/compute` - Compute interpretability analysis
- `POST /api/survey/submit` - Submit per-question survey responses

## Study Flow

1. Introduction → Participant ID entry
2. Per spurious correlation type: load questions, assign interpretability tool
3. Per question: display QA, show interpretability visualization, enable chat, collect survey
4. End-of-batch survey (tool usefulness rating)
5. Completion screen

## Adding New Interpretability Tools

1. Create new file in `backend/modules/interp_tools/`
2. Inherit from `BaseInterpretabilityTool` (see `base_tool.py`)
3. Implement required methods: `compute()`, `format_result()`, `get_visualization_type()`
4. Register in `interp_tools/__init__.py`

## Configuration

All settings in `backend/config.py`:
- `ServerConfig`: host, port, debug mode
- `ModelConfig`: model path, device (CPU/CUDA), generation params
- `StudyConfig`: questions per type, enabled tools
- `PathConfig`: data directories

## Data Formats

**Questions** (`backend/data/questions/*.json`):
```json
{
  "spurious_type": "type_name",
  "questions": [{
    "id": "q001",
    "question": "...",
    "choices": ["A", "B", "C", "D"],
    "model_answer": "A",
    "model_reasoning": "...",
    "spurious_indicators": ["..."]
  }]
}
```

**Responses**: JSONL files per participant in `backend/data/responses/`
