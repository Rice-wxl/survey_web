"""
Custom model server for your post-trained LLM.
This module handles loading and inference with your model.

Modify the ModelWrapper class to match your specific model architecture.
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Dict, Any, Optional
import threading

from config import ModelConfig


class ModelWrapper:
    """
    Wrapper for your custom post-trained model.
    Modify this class to match your model's requirements.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to avoid loading model multiple times."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        print(f"Loading model from {ModelConfig.MODEL_PATH}...")
        
        try:
            self.device = torch.device(ModelConfig.DEVICE)
        except Exception as e:
            print(f"CUDA not available, falling back to CPU: {e}")
            self.device = torch.device('cpu')
        
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                ModelConfig.TOKENIZER_PATH,
                trust_remote_code=True
            )
            
            # Ensure pad token exists
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model
            # Modify this section based on your model type
            self.model = AutoModelForCausalLM.from_pretrained(
                ModelConfig.MODEL_PATH,
                torch_dtype=torch.float16 if 'cuda' in str(self.device) else torch.float32,
                device_map='auto' if 'cuda' in str(self.device) else None,
                trust_remote_code=True
            )
            
            if 'cuda' not in str(self.device):
                self.model = self.model.to(self.device)
            
            self.model.eval()
            self._initialized = True
            print("Model loaded successfully!")
            
        except Exception as e:
            print(f"ERROR loading model: {e}")
            print("Please check MODEL_PATH in config.py")
            raise e
    
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = None,
        top_p: float = None,
        return_full_output: bool = False
    ) -> Dict[str, Any]:
        """
        Generate response from the model.
        
        Args:
            prompt: Input prompt text
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            return_full_output: If True, return input + output
            
        Returns:
            Dictionary with 'response' and optionally 'input_ids', 'output_ids'
        """
        temperature = temperature or ModelConfig.TEMPERATURE
        top_p = top_p or ModelConfig.TOP_P
        
        # Tokenize input
        inputs = self.tokenizer(
            prompt,
            return_tensors='pt',
            truncation=True,
            max_length=ModelConfig.MAX_LENGTH - max_new_tokens
        ).to(self.device)
        
        input_length = inputs['input_ids'].shape[1]
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=ModelConfig.DO_SAMPLE,
                pad_token_id=self.tokenizer.eos_token_id,
                return_dict_in_generate=True,
                output_scores=True
            )
        
        # Decode output
        generated_ids = outputs.sequences[0][input_length:]
        response_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        
        result = {
            'response': response_text,
            'input_length': input_length,
            'output_length': len(generated_ids)
        }
        
        if return_full_output:
            result['full_text'] = self.tokenizer.decode(outputs.sequences[0], skip_special_tokens=True)
            result['input_ids'] = inputs['input_ids'][0].tolist()
            result['output_ids'] = generated_ids.tolist()
        
        return result
    
    def get_token_attributions(
        self,
        input_text: str,
        output_text: str,
        method: str = 'gradient'
    ) -> Dict[str, Any]:
        """
        Compute token-level attributions.
        
        This is a placeholder - implement based on your interpretability method.
        Options: gradient-based, attention-based, etc.
        """
        # Tokenize
        input_tokens = self.tokenizer.tokenize(input_text)
        
        # Placeholder: implement actual attribution computation
        # For now, return mock attributions
        import random
        attributions = [random.random() for _ in input_tokens]
        
        # Normalize
        max_attr = max(attributions) if attributions else 1
        attributions = [a / max_attr for a in attributions]
        
        return {
            'tokens': input_tokens,
            'attributions': attributions,
            'method': method
        }


# Global model instance
_model = None


def get_model() -> ModelWrapper:
    """Get or create the model instance."""
    global _model
    if _model is None:
        _model = ModelWrapper()
    return _model


def get_model_response(
    user_input: str,
    context: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Get response from the model for the chat interface.
    
    Args:
        user_input: User's message/query
        context: Optional context including original question
        
    Returns:
        Dictionary with model response
    """
    model = get_model()
    
    # Build prompt based on context
    prompt = build_chat_prompt(user_input, context)
    
    # Generate response
    result = model.generate(
        prompt=prompt,
        max_new_tokens=ModelConfig.MAX_LENGTH // 4,
        return_full_output=True
    )
    
    return {
        'response': result['response'],
        'tokens_generated': result['output_length']
    }


def build_chat_prompt(user_input: str, context: Dict[str, Any] = None) -> str:
    """
    Build the prompt for chat interaction.
    Modify this to match your model's expected format.
    """
    # Example format - adjust based on your model's training format
    prompt_parts = []
    
    if context:
        # Include original question context
        if 'question' in context:
            prompt_parts.append(f"Medical Question: {context['question']}")
        if 'choices' in context:
            prompt_parts.append(f"Choices: {context['choices']}")
        if 'model_answer' in context:
            prompt_parts.append(f"Previous Answer: {context['model_answer']}")
        if 'model_reasoning' in context:
            prompt_parts.append(f"Previous Reasoning: {context['model_reasoning']}")
        
        prompt_parts.append("")  # Blank line separator
    
    prompt_parts.append(f"User Query: {user_input}")
    prompt_parts.append("Response:")
    
    return "\n".join(prompt_parts)


# ============== Standalone Server Mode ==============

if __name__ == '__main__':
    """
    Run as standalone server for model inference.
    Useful if you want to run the model on a separate machine/GPU.
    """
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    
    app = Flask(__name__)
    CORS(app)
    
    @app.route('/generate', methods=['POST'])
    def generate():
        data = request.json
        prompt = data.get('prompt', '')
        max_tokens = data.get('max_tokens', 512)
        
        model = get_model()
        result = model.generate(prompt, max_new_tokens=max_tokens)
        return jsonify(result)
    
    @app.route('/chat', methods=['POST'])
    def chat():
        data = request.json
        user_input = data.get('message', '')
        context = data.get('context', {})
        
        result = get_model_response(user_input, context)
        return jsonify(result)
    
    @app.route('/attributions', methods=['POST'])
    def attributions():
        data = request.json
        input_text = data.get('input_text', '')
        output_text = data.get('output_text', '')
        method = data.get('method', 'gradient')
        
        model = get_model()
        result = model.get_token_attributions(input_text, output_text, method)
        return jsonify(result)
    
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'healthy', 'model_loaded': _model is not None})
    
    print("Starting model server on port 8000...")
    app.run(host='0.0.0.0', port=8000)