"""Configuration settings for the interpretability study."""

import os
from pathlib import Path


class Config:
    HOST = os.getenv('HOST', '127.0.0.1')
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    BASE_DIR = Path(__file__).parent
    ORGANISMS_DIR = BASE_DIR / 'data' / 'organisms'   # written by build_items.py
    # tutorial.json if present, else the dev stub (same schema as an organism file)
    TUTORIAL_DIR = BASE_DIR / 'data' / 'tutorial'
    RESPONSES_DIR = Path(os.getenv('RESPONSES_DIR', BASE_DIR / 'data' / 'responses'))
    # {"<token>": {"pid": "P01", "schedule": 0}} -- gitignored; see readme.md
    PARTICIPANTS_FILE = Path(os.getenv('PARTICIPANTS_FILE', BASE_DIR / 'participants.json'))
    AUTH = os.getenv('STUDY_AUTH', 'on') != 'off'      # off only for local dev

    # Batch order is fixed; the schedule (app.SCHEDULES) permutes it per participant.
    ORGANISMS = ['young_agg', 'female_RA', 'asian_dosages']
    CONDITIONS = ['blackbox', 'jlens', 'sae', 'lrp']   # lrp = AttnLRP word heatmap (2026-11-07)
    # = the survey panel size (3 spurious / 2 cf / 2 controlled since 2026-11-05). A smaller
    # value subsamples per variant (app.build_plan), a leftover of the 10-item audit panels.
    ITEMS_PER_ORGANISM = int(os.getenv('ITEMS_PER_ORGANISM', 7))

    # Live chat: vLLM OpenAI-compatible server with one LoRA per organism key.
    VLLM_URL = os.getenv('VLLM_URL', 'http://127.0.0.1:8000')
    BASE_MODEL = 'meta-llama/Llama-3.1-8B-Instruct'   # vLLM served name; tutorial chat
    CHAT_MAX_TOKENS = int(os.getenv('CHAT_MAX_TOKENS', 1024))
    CHAT_MAX_TURNS = int(os.getenv('CHAT_MAX_TURNS', 15))   # user turns per conversation (frontend MAX_TURNS)
    CF_MAX_TOKENS = 2048   # a counterfactual's first reply: the cached responses' token cap
    # Same sampling as the cached responses (agent_audit/config.py GEN).
    GEN = dict(temperature=0.6, top_p=0.9, repetition_penalty=1.2)
