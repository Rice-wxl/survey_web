"""
Token Attribution Tool

Computes token-level importance scores using gradient-based methods.
This is a reference implementation - modify based on your specific needs.
"""

import torch
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from .base_tool import BaseInterpretabilityTool


class TokenAttributionTool(BaseInterpretabilityTool):
    """
    Token-level attribution using gradient-based methods.
    
    Supported methods:
    - 'gradient': Simple input gradients
    - 'integrated_gradients': Integrated gradients
    - 'attention': Attention-based attribution
    """
    
    name = "token_attribution"
    display_name = "Token Attribution"
    description = "Highlights tokens based on their influence on the model's prediction"
    result_type = "token_attribution"
    
    def _initialize(self):
        self.method = self.config.get('method', 'gradient')
        self.num_steps = self.config.get('num_steps', 50)  # For integrated gradients
        self.aggregate_layers = self.config.get('aggregate_layers', True)
    
    def compute(
        self,
        input_text: str,
        output_text: str,
        question_id: Optional[str] = None,
        target_token_idx: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compute token attributions.
        
        Args:
            input_text: Input to the model
            output_text: Model's generated output
            question_id: Question identifier
            target_token_idx: Which output token to compute attribution for
                            (default: last token)
        """
        if self.model is None:
            # Return mock data if no model available
            return self._compute_mock(input_text, output_text)
        
        if self.method == 'gradient':
            return self._compute_gradient_attribution(input_text, output_text, target_token_idx)
        elif self.method == 'integrated_gradients':
            return self._compute_integrated_gradients(input_text, output_text, target_token_idx)
        elif self.method == 'attention':
            return self._compute_attention_attribution(input_text, output_text)
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def _compute_gradient_attribution(
        self,
        input_text: str,
        output_text: str,
        target_token_idx: Optional[int] = None
    ) -> Dict[str, Any]:
        """Compute gradient-based attribution."""
        model = self.model.model
        tokenizer = self.model.tokenizer
        device = self.model.device
        
        # Prepare input
        full_text = input_text + output_text
        inputs = tokenizer(full_text, return_tensors='pt').to(device)
        input_ids = inputs['input_ids']
        
        # Get embeddings
        embeddings = model.get_input_embeddings()
        input_embeds = embeddings(input_ids)
        input_embeds.requires_grad_(True)
        
        # Forward pass
        outputs = model(inputs_embeds=input_embeds)
        logits = outputs.logits
        
        # Target: probability of the actual next token
        if target_token_idx is None:
            target_token_idx = -1
        
        target_logit = logits[0, target_token_idx, input_ids[0, target_token_idx + 1]]
        
        # Backward pass
        target_logit.backward()
        
        # Get gradients
        gradients = input_embeds.grad[0].detach()
        
        # Aggregate across embedding dimension
        token_attributions = torch.norm(gradients, dim=-1).cpu().numpy()
        
        # Get tokens
        tokens = tokenizer.convert_ids_to_tokens(input_ids[0])
        
        # Normalize attributions
        token_attributions = self._normalize_attributions(token_attributions)
        
        # Only return input portion
        input_tokens = tokenizer.tokenize(input_text)
        input_length = len(input_tokens)
        
        return {
            'tokens': input_tokens,
            'attributions': token_attributions[:input_length].tolist(),
            'method': 'gradient',
            'visualization_type': 'token_highlight'
        }
    
    def _compute_integrated_gradients(
        self,
        input_text: str,
        output_text: str,
        target_token_idx: Optional[int] = None
    ) -> Dict[str, Any]:
        """Compute integrated gradients attribution."""
        model = self.model.model
        tokenizer = self.model.tokenizer
        device = self.model.device
        
        # Prepare input
        inputs = tokenizer(input_text, return_tensors='pt').to(device)
        input_ids = inputs['input_ids']
        
        # Get embeddings
        embeddings = model.get_input_embeddings()
        input_embeds = embeddings(input_ids)
        
        # Baseline: zero embeddings
        baseline = torch.zeros_like(input_embeds)
        
        # Compute integrated gradients
        scaled_inputs = [
            baseline + (float(i) / self.num_steps) * (input_embeds - baseline)
            for i in range(self.num_steps + 1)
        ]
        
        gradients = []
        for scaled_input in scaled_inputs:
            scaled_input = scaled_input.requires_grad_(True)
            outputs = model(inputs_embeds=scaled_input)
            
            if target_token_idx is None:
                target_token_idx = -1
            
            target_logit = outputs.logits[0, target_token_idx].max()
            target_logit.backward()
            gradients.append(scaled_input.grad[0].detach())
        
        # Average gradients
        avg_gradients = torch.stack(gradients).mean(dim=0)
        
        # Multiply by input difference
        integrated_grads = (input_embeds[0] - baseline[0]).detach() * avg_gradients
        
        # Aggregate
        token_attributions = torch.norm(integrated_grads, dim=-1).cpu().numpy()
        token_attributions = self._normalize_attributions(token_attributions)
        
        tokens = tokenizer.convert_ids_to_tokens(input_ids[0])
        
        return {
            'tokens': tokens,
            'attributions': token_attributions.tolist(),
            'method': 'integrated_gradients',
            'num_steps': self.num_steps,
            'visualization_type': 'token_highlight'
        }
    
    def _compute_attention_attribution(
        self,
        input_text: str,
        output_text: str
    ) -> Dict[str, Any]:
        """Compute attention-based attribution."""
        model = self.model.model
        tokenizer = self.model.tokenizer
        device = self.model.device
        
        # Prepare input
        inputs = tokenizer(input_text, return_tensors='pt').to(device)
        
        # Forward pass with attention outputs
        with torch.no_grad():
            outputs = model(**inputs, output_attentions=True)
        
        # Get attention weights from all layers
        attentions = outputs.attentions  # Tuple of (batch, heads, seq, seq)
        
        # Aggregate: average across layers and heads, focus on last token attending to input
        all_attentions = torch.stack(attentions)  # (layers, batch, heads, seq, seq)
        
        if self.aggregate_layers:
            # Average across layers and heads
            avg_attention = all_attentions.mean(dim=(0, 2))  # (batch, seq, seq)
            # Get attention from last token to all input tokens
            token_attributions = avg_attention[0, -1, :].cpu().numpy()
        else:
            # Return per-layer attention (for more detailed analysis)
            token_attributions = all_attentions[:, 0, :, -1, :].cpu().numpy()
        
        token_attributions = self._normalize_attributions(token_attributions)
        
        tokens = tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])
        
        return {
            'tokens': tokens,
            'attributions': token_attributions.tolist(),
            'method': 'attention',
            'aggregated': self.aggregate_layers,
            'visualization_type': 'token_highlight'
        }
    
    def _compute_mock(self, input_text: str, output_text: str) -> Dict[str, Any]:
        """Generate mock attributions for testing."""
        import random
        
        # Simple word-level tokenization for mock
        tokens = input_text.split()[:100]
        
        # Generate mock attributions with some structure
        attributions = []
        for token in tokens:
            # Higher attribution for certain keywords
            if any(kw in token.lower() for kw in ['patient', 'symptom', 'diagnosis', 'treatment']):
                attributions.append(random.uniform(0.6, 1.0))
            elif any(kw in token.lower() for kw in ['male', 'female', 'age', 'year']):
                # Potentially spurious - medium-high attribution
                attributions.append(random.uniform(0.4, 0.8))
            else:
                attributions.append(random.uniform(0.0, 0.4))
        
        attributions = self._normalize_attributions(np.array(attributions))
        
        return {
            'tokens': tokens,
            'attributions': attributions.tolist(),
            'method': 'mock',
            'visualization_type': 'token_highlight'
        }
    
    def _normalize_attributions(self, attributions: np.ndarray) -> np.ndarray:
        """Normalize attributions to [0, 1]."""
        if attributions.max() == attributions.min():
            return np.zeros_like(attributions)
        return (attributions - attributions.min()) / (attributions.max() - attributions.min())
    
    def get_visualization_config(self) -> Dict[str, Any]:
        return {
            'type': 'token_highlight',
            'color_scale': {
                'type': 'sequential',
                'colors': ['rgba(59, 130, 246, 0.1)', 'rgba(59, 130, 246, 0.9)'],
                'domain': [0, 1]
            },
            'interactive': True,
            'show_scores': True,
            'hover_enabled': True,
            'legend': {
                'show': True,
                'position': 'bottom',
                'labels': ['Low Attribution', 'Medium', 'High Attribution']
            }
        }