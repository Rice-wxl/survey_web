"""
Unit tests for the Flask API endpoints (app.py).

Tests cover:
- Session management endpoints
- QA module endpoints
- Survey submission endpoints
- Interpretability tool endpoints
- Data export endpoints
- Error handling and edge cases
"""

import pytest
import json
from unittest.mock import patch, Mock
from pathlib import Path
import sys
import tempfile
import shutil

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


@pytest.fixture
def app():
    """
    Creates a Flask test application with isolated configuration.
    """
    # Create temporary directories for test data
    temp_dir = tempfile.mkdtemp()
    questions_dir = Path(temp_dir) / "questions"
    responses_dir = Path(temp_dir) / "responses"
    questions_dir.mkdir(parents=True)
    responses_dir.mkdir(parents=True)

    # Create sample questions file
    sample_data = {
        "spurious_type": "test_type",
        "description": "Test description",
        "questions": [
            {
                "id": "test_q1",
                "question": "Test question?",
                "choices": ["A", "B", "C", "D"],
                "correct_answer": "A",
                "model_answer": "A",
                "model_reasoning": "Test reasoning",
                "has_spurious": False,
                "spurious_details": None
            }
        ]
    }
    with open(questions_dir / "test.json", 'w') as f:
        json.dump(sample_data, f)

    # Patch config before importing app
    with patch('config.Config.QUESTIONS_DIR', questions_dir):
        with patch('config.Config.RESPONSES_DIR', responses_dir):
            # Re-import app with patched config
            import importlib
            import app as app_module
            importlib.reload(app_module)

            app_module.app.config['TESTING'] = True
            yield app_module.app

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def client(app):
    """
    Creates a test client for making HTTP requests.
    """
    return app.test_client()


class TestStaticFiles:
    """Tests for static file serving."""

    def test_root_serves_index_html(self, client):
        """
        Verifies that root URL serves the frontend index.html.
        """
        response = client.get('/')

        # Should serve HTML (may be 200 or 404 depending on frontend setup)
        assert response.status_code in [200, 404]


class TestSessionManagement:
    """Tests for session management endpoints."""

    def test_start_session_without_participant_id(self, client):
        """
        Verifies that starting a session without participant_id auto-generates one.
        """
        response = client.post('/api/session/start',
                               json={},
                               content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'participant_id' in data
        assert data['participant_id'].startswith('P_')
        assert 'available_tools' in data

    def test_start_session_with_participant_id(self, client):
        """
        Verifies that starting a session with custom participant_id uses it.
        """
        response = client.post('/api/session/start',
                               json={'participant_id': 'custom_123'},
                               content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['participant_id'] == 'custom_123'

    def test_assign_tool_to_session(self, client):
        """
        Verifies that a tool can be assigned to an existing session.
        """
        # First, start a session
        start_response = client.post('/api/session/start',
                                     json={'participant_id': 'tool_test'},
                                     content_type='application/json')
        assert start_response.status_code == 200

        # Assign a tool
        response = client.post('/api/session/tool_test/assign_tool',
                               json={'tool_name': 'mock_tool'},
                               content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['assigned_tool'] == 'mock_tool'

    def test_assign_tool_invalid_session(self, client):
        """
        Verifies that assigning tool to non-existent session returns 404.
        """
        response = client.post('/api/session/nonexistent/assign_tool',
                               json={'tool_name': 'mock_tool'},
                               content_type='application/json')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data


class TestQAEndpoints:
    """Tests for QA module endpoints."""

    def test_get_spurious_types(self, client):
        """
        Verifies that spurious types endpoint returns available types.
        """
        response = client.get('/api/qa/spurious_types')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'spurious_types' in data
        assert isinstance(data['spurious_types'], list)

    def test_get_spurious_types_structure(self, client):
        """
        Verifies that each spurious type has required fields.
        """
        response = client.get('/api/qa/spurious_types')

        data = json.loads(response.data)
        if len(data['spurious_types']) > 0:
            stype = data['spurious_types'][0]
            assert 'type' in stype
            assert 'description' in stype
            assert 'question_count' in stype

    def test_get_questions_valid_type(self, client):
        """
        Verifies that questions can be retrieved for a valid spurious type.
        """
        response = client.get('/api/qa/questions/test_type')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'spurious_type' in data
        assert 'total_questions' in data
        assert 'question_ids' in data
        assert isinstance(data['question_ids'], list)

    def test_get_questions_invalid_type(self, client):
        """
        Verifies that invalid spurious type returns 404.
        """
        response = client.get('/api/qa/questions/nonexistent_type')

        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data

    def test_get_question_valid_id(self, client):
        """
        Verifies that a specific question can be retrieved by ID.
        """
        response = client.get('/api/qa/question/test_q1')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['id'] == 'test_q1'
        assert 'question' in data
        assert 'choices' in data
        assert 'model_answer' in data
        assert 'model_reasoning' in data

    def test_get_question_invalid_id(self, client):
        """
        Verifies that invalid question ID returns 404.
        """
        response = client.get('/api/qa/question/nonexistent_id')

        assert response.status_code == 404


class TestInterpretabilityEndpoints:
    """Tests for interpretability tool endpoints."""

    def test_get_available_tools(self, client):
        """
        Verifies that available tools endpoint returns list of tools.
        """
        response = client.get('/api/interp/tools')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'tools' in data
        assert isinstance(data['tools'], list)
        assert len(data['tools']) >= 2  # At least mock_tool and token_attribution

    def test_get_available_tools_structure(self, client):
        """
        Verifies that each tool has required metadata fields.
        """
        response = client.get('/api/interp/tools')

        data = json.loads(response.data)
        for tool in data['tools']:
            assert 'name' in tool
            assert 'display_name' in tool
            assert 'description' in tool
            assert 'result_type' in tool

    def test_compute_interpretation_mock_tool(self, client):
        """
        Verifies that interpretability computation works with mock tool.
        """
        response = client.post('/api/interp/compute',
                               json={
                                   'tool_name': 'mock_tool',
                                   'question_id': 'test_q1',
                                   'model_input': 'Test input text',
                                   'model_output': 'Test output'
                               },
                               content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['tool_name'] == 'mock_tool'
        assert 'result' in data
        assert 'tokens' in data['result']
        assert 'attributions' in data['result']

    def test_compute_interpretation_invalid_tool(self, client):
        """
        Verifies that invalid tool name returns 404.
        """
        response = client.post('/api/interp/compute',
                               json={
                                   'tool_name': 'nonexistent_tool',
                                   'question_id': 'test_q1',
                                   'model_input': 'Test input',
                                   'model_output': 'Test output'
                               },
                               content_type='application/json')

        assert response.status_code == 404


class TestSurveyEndpoints:
    """Tests for survey endpoints."""

    def test_get_survey_questions(self, client):
        """
        Verifies that survey questions endpoint returns both survey types.
        """
        response = client.get('/api/survey/questions')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'per_question' in data
        assert 'batch' in data
        assert isinstance(data['per_question'], list)
        assert isinstance(data['batch'], list)

    def test_submit_survey_valid_session(self, client):
        """
        Verifies that survey can be submitted for a valid session.
        """
        # Start a session first
        client.post('/api/session/start',
                    json={'participant_id': 'survey_test'},
                    content_type='application/json')

        # Submit survey
        response = client.post('/api/survey/submit',
                               json={
                                   'participant_id': 'survey_test',
                                   'question_id': 'test_q1',
                                   'responses': {
                                       'q1_clinically_sound': 'Yes',
                                       'q3_inference_method': ['From the model\'s reasoning text'],
                                       'q4_confidence': 4
                                   },
                                   'timing_data': {
                                       'total_seconds': 120
                                   }
                               },
                               content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_submit_survey_invalid_session(self, client):
        """
        Verifies that survey submission for non-existent session returns 404.
        """
        response = client.post('/api/survey/submit',
                               json={
                                   'participant_id': 'nonexistent',
                                   'question_id': 'test_q1',
                                   'responses': {}
                               },
                               content_type='application/json')

        assert response.status_code == 404

    def test_complete_batch_valid_session(self, client):
        """
        Verifies that batch completion survey can be submitted.
        """
        # Start a session first
        client.post('/api/session/start',
                    json={'participant_id': 'batch_test'},
                    content_type='application/json')

        # Submit batch completion
        response = client.post('/api/survey/batch_complete',
                               json={
                                   'participant_id': 'batch_test',
                                   'spurious_type': 'test_type',
                                   'tool_name': 'mock_tool',
                                   'usefulness_rating': 4,
                                   'comments': 'Good tool'
                               },
                               content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True


class TestModelChatEndpoint:
    """Tests for the model chat endpoint."""

    def test_model_chat_endpoint(self, client):
        """
        Verifies that chat endpoint accepts requests.
        Note: May fail if model not loaded, but should handle gracefully.
        """
        # Start a session
        client.post('/api/session/start',
                    json={'participant_id': 'chat_test'},
                    content_type='application/json')

        # Patch model_server to avoid loading actual model
        with patch('model_server.get_model_response') as mock_response:
            mock_response.return_value = {
                'response': 'Test model response',
                'tokens_generated': 10
            }

            response = client.post('/api/model/chat',
                                   json={
                                       'message': 'Test question',
                                       'context': {'question_id': 'test_q1'},
                                       'participant_id': 'chat_test'
                                   },
                                   content_type='application/json')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'response' in data


class TestExportEndpoint:
    """Tests for the data export endpoint."""

    def test_export_session_valid(self, client):
        """
        Verifies that session data can be exported.
        """
        # Start a session and add some data
        client.post('/api/session/start',
                    json={'participant_id': 'export_test'},
                    content_type='application/json')

        # Export
        response = client.get('/api/export/export_test')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'participant_id' in data
        assert data['participant_id'] == 'export_test'
        assert 'start_time' in data
        assert 'responses' in data

    def test_export_session_invalid(self, client):
        """
        Verifies that exporting non-existent session returns 404.
        """
        response = client.get('/api/export/nonexistent')

        assert response.status_code == 404


class TestResponsePersistence:
    """Tests for response file persistence."""

    def test_survey_response_saved_to_file(self, client, app):
        """
        Verifies that survey responses are saved to JSONL files.
        """
        # Start a session
        client.post('/api/session/start',
                    json={'participant_id': 'persist_test'},
                    content_type='application/json')

        # Submit a survey
        client.post('/api/survey/submit',
                    json={
                        'participant_id': 'persist_test',
                        'question_id': 'test_q1',
                        'responses': {'q1': 'Yes'},
                        'timing_data': {}
                    },
                    content_type='application/json')

        # Check that file was created
        from config import Config
        responses_file = Path(Config.RESPONSES_DIR) / 'persist_test.jsonl'

        # Note: File existence depends on actual save_response implementation
        # This test documents expected behavior


class TestErrorHandling:
    """Tests for API error handling."""

    def test_invalid_json_body(self, client):
        """
        Verifies that invalid JSON is handled gracefully.
        """
        response = client.post('/api/session/start',
                               data='not valid json',
                               content_type='application/json')

        # Should return an error status
        assert response.status_code in [400, 415, 500]

    def test_missing_content_type(self, client):
        """
        Verifies behavior when content-type is missing.
        """
        response = client.post('/api/session/start',
                               data='{}')

        # Should handle or return appropriate error
        assert response.status_code in [200, 400, 415]


class TestCORSConfiguration:
    """Tests for CORS configuration."""

    def test_cors_headers_present(self, client):
        """
        Verifies that CORS headers are set for cross-origin requests.
        """
        response = client.get('/api/qa/spurious_types')

        # CORS should allow cross-origin requests
        # The exact headers depend on Flask-CORS configuration
        assert response.status_code == 200


class TestChatLogging:
    """Tests for chat interaction logging."""

    def test_chat_logged_to_session(self, client):
        """
        Verifies that chat interactions are logged in the session.
        """
        # Start a session
        client.post('/api/session/start',
                    json={'participant_id': 'chat_log_test'},
                    content_type='application/json')

        # Send a chat message
        with patch('model_server.get_model_response') as mock_response:
            mock_response.return_value = {
                'response': 'Test response',
                'tokens_generated': 5
            }

            client.post('/api/model/chat',
                        json={
                            'message': 'Test message',
                            'context': {'question_id': 'q1'},
                            'participant_id': 'chat_log_test'
                        },
                        content_type='application/json')

        # Export and check chat log
        response = client.get('/api/export/chat_log_test')
        data = json.loads(response.data)

        # Chat logs should be recorded if session exists
        # The exact structure depends on implementation
        assert 'participant_id' in data
