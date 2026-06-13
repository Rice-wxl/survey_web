"""
Main Flask server for the interpretability study.
Handles API endpoints for QA, model inference, and data collection.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime
from pathlib import Path

from modules.qa_module import QAModule
from modules.survey_module import SurveyModule
from modules.interp_tools import get_tool_by_name, list_available_tools
from config import Config

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# Initialize modules
qa_module = QAModule(Config.QUESTIONS_DIR)
survey_module = SurveyModule()

# Store active sessions
sessions = {}


# ============== Static Files ==============

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(app.static_folder, path)


# ============== Session Management ==============

@app.route('/api/session/start', methods=['POST'])
def start_session():
    """Initialize a new participant session."""
    data = request.json
    
    participant_id = data.get('participant_id')
    # Auto-generate ID if not provided or empty
    if not participant_id:
        participant_id = f"P_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    session = {
        'participant_id': participant_id,
        'start_time': datetime.now().isoformat(),
        'current_spurious_type': None,
        'current_question_idx': 0,
        'assigned_tool': None,
        'responses': []
    }
    sessions[participant_id] = session
    
    return jsonify({
        'success': True,
        'participant_id': participant_id,
        'available_tools': list_available_tools()
    })


@app.route('/api/session/<participant_id>/assign_tool', methods=['POST'])
def assign_tool(participant_id):
    """Assign an interpretability tool for the current question batch."""
    data = request.json
    tool_name = data.get('tool_name')
    
    if participant_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    sessions[participant_id]['assigned_tool'] = tool_name
    return jsonify({'success': True, 'assigned_tool': tool_name})


# ============== QA Module Endpoints ==============

@app.route('/api/qa/spurious_types', methods=['GET'])
def get_spurious_types():
    """Get list of available spurious correlation types."""
    return jsonify({
        'spurious_types': qa_module.get_spurious_types()
    })


@app.route('/api/qa/questions/<spurious_type>', methods=['GET'])
def get_questions(spurious_type):
    """Get all questions for a spurious correlation type."""
    questions = qa_module.get_questions_by_type(spurious_type)
    if questions is None:
        return jsonify({'error': 'Spurious type not found'}), 404
    
    # Return metadata only, not full content (for progress tracking)
    return jsonify({
        'spurious_type': spurious_type,
        'total_questions': len(questions),
        'question_ids': [q['id'] for q in questions]
    })


@app.route('/api/qa/question/<question_id>', methods=['GET'])
def get_question(question_id):
    """Get a specific question with model response."""
    question = qa_module.get_question_by_id(question_id)
    if question is None:
        return jsonify({'error': 'Question not found'}), 404
    
    return jsonify(question)


# ============== Model Inference Endpoints ==============

@app.route('/api/model/chat', methods=['POST'])
def model_chat():
    """
    Handle interactive chat with the model.
    This endpoint connects to your custom model server.
    """
    data = request.json
    user_input = data.get('message')
    context = data.get('context', {})  # Original question context
    participant_id = data.get('participant_id')
    
    # Import here to avoid circular imports
    from model_server import get_model_response
    
    try:
        response = get_model_response(
            user_input=user_input,
            context=context
        )
        
        # Log the interaction
        if participant_id and participant_id in sessions:
            sessions[participant_id].setdefault('chat_logs', []).append({
                'timestamp': datetime.now().isoformat(),
                'user_input': user_input,
                'model_response': response['response'],
                'question_context': context.get('question_id')
            })
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============== Interpretability Tools Endpoints ==============

@app.route('/api/interp/compute', methods=['POST'])
def compute_interpretation():
    """
    Compute interpretability analysis for a given input.
    Tool is dynamically selected based on session assignment.
    """
    data = request.json
    tool_name = data.get('tool_name')
    question_id = data.get('question_id')
    model_input = data.get('model_input')
    model_output = data.get('model_output')
    
    # Get model instance for tools that need it
    from model_server import get_model
    try:
        model = get_model()
    except Exception as e:
        print(f"Warning: Could not load model for interpretability: {e}")
        model = None

    tool = get_tool_by_name(tool_name, model=model)
    if tool is None:
        return jsonify({'error': f'Tool {tool_name} not found'}), 404
    
    try:
        result = tool.compute(
            input_text=model_input,
            output_text=model_output,
            question_id=question_id
        )
        return jsonify({
            'tool_name': tool_name,
            'tool_display_name': tool.display_name,
            'result': result
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/interp/tools', methods=['GET'])
def get_available_tools():
    """List all available interpretability tools."""
    return jsonify({
        'tools': list_available_tools()
    })


# ============== Survey Endpoints ==============

@app.route('/api/survey/questions', methods=['GET'])
def get_survey_questions():
    """Get the survey questions template."""
    return jsonify(survey_module.get_questions())


@app.route('/api/survey/submit', methods=['POST'])
def submit_survey():
    """Submit survey response for a question."""
    data = request.json
    participant_id = data.get('participant_id')
    question_id = data.get('question_id')
    responses = data.get('responses')
    timing_data = data.get('timing_data', {})
    
    if participant_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    response_record = {
        'question_id': question_id,
        'timestamp': datetime.now().isoformat(),
        'tool_used': sessions[participant_id].get('assigned_tool'),
        'survey_responses': responses,
        'timing': timing_data
    }
    
    sessions[participant_id]['responses'].append(response_record)
    
    # Save to file
    save_response(participant_id, response_record)
    
    return jsonify({'success': True})


@app.route('/api/survey/batch_complete', methods=['POST'])
def complete_batch():
    """Submit end-of-batch survey (tool usefulness)."""
    data = request.json
    participant_id = data.get('participant_id')
    spurious_type = data.get('spurious_type')
    tool_name = data.get('tool_name')
    usefulness_rating = data.get('usefulness_rating')
    comments = data.get('comments', '')
    
    if participant_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    batch_record = {
        'type': 'batch_complete',
        'spurious_type': spurious_type,
        'tool_name': tool_name,
        'usefulness_rating': usefulness_rating,
        'comments': comments,
        'timestamp': datetime.now().isoformat()
    }
    
    sessions[participant_id]['responses'].append(batch_record)
    save_response(participant_id, batch_record)
    
    return jsonify({'success': True})


@app.route('/api/survey/end_of_study', methods=['POST'])
def end_of_study_survey():
    """Submit end-of-study survey."""
    data = request.json
    participant_id = data.get('participant_id')
    most_helpful_interface = data.get('most_helpful_interface')
    comments = data.get('comments', '')

    if participant_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404

    record = {
        'type': 'end_of_study',
        'most_helpful_interface': most_helpful_interface,
        'comments': comments,
        'timestamp': datetime.now().isoformat()
    }

    sessions[participant_id]['responses'].append(record)
    save_response(participant_id, record)

    return jsonify({'success': True})


# ============== Data Export ==============

@app.route('/api/export/<participant_id>', methods=['GET'])
def export_session(participant_id):
    """Export all data for a participant session."""
    if participant_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify(sessions[participant_id])


# ============== Helper Functions ==============

def save_response(participant_id, record):
    """Save response to file."""
    responses_dir = Path(Config.RESPONSES_DIR)
    responses_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = responses_dir / f"{participant_id}.jsonl"
    with open(filepath, 'a') as f:
        f.write(json.dumps(record) + '\n')


if __name__ == '__main__':
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
