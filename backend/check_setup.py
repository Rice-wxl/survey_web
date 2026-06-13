#!/usr/bin/env python
"""Diagnostic script to check setup."""

import sys
from pathlib import Path

def check_files():
    """Check all required files exist."""
    base = Path(__file__).parent
    
    required_files = [
        'app.py',
        'config.py',
        'model_server.py',
        'modules/__init__.py',
        'modules/qa_module.py',
        'modules/survey_module.py',
        'modules/interp_tools/__init__.py',
        'modules/interp_tools/base_tool.py',
        'modules/interp_tools/token_attribution.py',
        'data/questions/sample_questions.json',
    ]
    
    frontend_base = base.parent / 'frontend'
    frontend_files = [
        'index.html',
        'css/styles.css',
        'js/app.js',
        'js/utils/api.js',
        'js/utils/timer.js',
        'js/modules/qaDisplay.js',
        'js/modules/interpTools.js',
        'js/modules/chatInterface.js',
        'js/modules/surveyModule.js',
    ]
    
    print("Checking backend files...")
    all_good = True
    for f in required_files:
        path = base / f
        if path.exists():
            print(f"  ✓ {f}")
        else:
            print(f"  ✗ {f} MISSING")
            all_good = False
    
    print("\nChecking frontend files...")
    for f in frontend_files:
        path = frontend_base / f
        if path.exists():
            print(f"  ✓ {f}")
        else:
            print(f"  ✗ {f} MISSING")
            all_good = False
    
    return all_good

def check_imports():
    """Check Python imports work."""
    print("\nChecking Python imports...")
    try:
        import flask
        print("  ✓ flask")
    except ImportError:
        print("  ✗ flask - run: pip install flask")
        return False
    
    try:
        from flask_cors import CORS
        print("  ✓ flask-cors")
    except ImportError:
        print("  ✗ flask-cors - run: pip install flask-cors")
        return False
    
    try:
        import torch
        print(f"  ✓ torch ({torch.__version__})")
    except ImportError:
        print("  ✗ torch - run: pip install torch")
        return False
    
    try:
        import transformers
        print(f"  ✓ transformers ({transformers.__version__})")
    except ImportError:
        print("  ✗ transformers - run: pip install transformers")
        return False
    
    return True

def check_model():
    """Check model can be loaded."""
    print("\nChecking model loading...")
    try:
        from config import ModelConfig
        print(f"  Model path: {ModelConfig.MODEL_PATH}")
        print(f"  Device: {ModelConfig.DEVICE}")
        
        from transformers import AutoTokenizer, AutoModelForCausalLM
        
        print("  Loading tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(ModelConfig.MODEL_PATH)
        print("  ✓ Tokenizer loaded")
        
        print("  Loading model (this may take a moment)...")
        model = AutoModelForCausalLM.from_pretrained(ModelConfig.MODEL_PATH)
        print("  ✓ Model loaded")
        
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    print("=" * 50)
    print("Interpretability Study Setup Check")
    print("=" * 50)
    
    files_ok = check_files()
    imports_ok = check_imports()
    
    if imports_ok:
        model_ok = check_model()
    else:
        model_ok = False
        print("\nSkipping model check due to missing imports.")
    
    print("\n" + "=" * 50)
    if files_ok and imports_ok and model_ok:
        print("All checks passed! Run: python app.py")
    else:
        print("Some checks failed. Please fix the issues above.")
    print("=" * 50)

if __name__ == '__main__':
    main()