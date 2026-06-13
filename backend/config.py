"""
Configuration settings for the interpretability study.
"""

import os
from pathlib import Path


class Config:
    # Server settings
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Paths
    BASE_DIR = Path(__file__).parent
    QUESTIONS_DIR = BASE_DIR / 'data' / 'questions'
    RESPONSES_DIR = BASE_DIR / 'data' / 'responses'
    
    # Model settings
    MODEL_SERVER_URL = os.getenv('MODEL_SERVER_URL', 'http://localhost:8000')
    MODEL_NAME = os.getenv('MODEL_NAME', 'your-custom-model')
    MODEL_MAX_TOKENS = int(os.getenv('MODEL_MAX_TOKENS', 512))
    
    # Study settings
    QUESTIONS_PER_SPURIOUS_TYPE = int(os.getenv('QUESTIONS_PER_TYPE', 5))
    
    # Available interpretability tools (can be toggled)
    ENABLED_TOOLS = [
        'token_attribution',
        # 'attention_visualization',  # Uncomment when implemented
        # 'concept_activation',        # Uncomment when implemented
    ]


class ModelConfig:
    """Configuration specific to your custom model."""
    
    # Path to model weights or HuggingFace model ID
    MODEL_PATH = 'openai-community/gpt2'

    # Tokenizer settings
    TOKENIZER_PATH = MODEL_PATH
    
    # Inference settings
    DEVICE = "cpu"
    BATCH_SIZE = 1
    MAX_LENGTH = 2048
    
    # Generation settings
    TEMPERATURE = float(os.getenv('TEMPERATURE', 0.7))
    TOP_P = float(os.getenv('TOP_P', 0.9))
    DO_SAMPLE = True
