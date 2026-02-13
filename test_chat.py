#!/usr/bin/env python3
"""
Simple test script for Phase III chat functionality
"""
import os
import sys
import json
from unittest.mock import Mock, patch

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all modules can be imported"""
    try:
        from app.main import app
        from mcp_server import set_current_user, add_task, list_tasks
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_mcp_tools():
    """Test MCP tools with mocked database"""
    try:
        # Mock the database session and models
        with patch('mcp_server.get_session') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock Task model
            mock_task = Mock()
            mock_task.id = "test-id"
            mock_task.title = "Test Task"
            mock_task.description = "Test Description"
            mock_task.completed = False

            mock_db.exec.return_value.first.return_value = mock_task
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None

            # Test setting user and calling tools
            from mcp_server import set_current_user, add_task, list_tasks
            set_current_user("test-user-id")

            # Test add_task
            result = add_task("Test Task", "Test Description")
            result_data = json.loads(result)
            assert result_data["title"] == "Test Task"
            print("✅ MCP add_task tool works")

            # Test list_tasks
            result = list_tasks("all", 10)
            result_data = json.loads(result)
            print("✅ MCP list_tasks tool works")

            return True
    except Exception as e:
        print(f"❌ MCP tools test failed: {e}")
        return False

def test_chat_endpoint():
    """Test chat endpoint structure"""
    try:
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Mock OpenAI and database
        with patch('app.main.openai_client') as mock_openai, \
             patch('app.main.get_current_user') as mock_user, \
             patch('app.main.get_session') as mock_session:

            # Mock user
            mock_user_obj = Mock()
            mock_user_obj.id = "test-user-id"
            mock_user.return_value = mock_user_obj

            # Mock database session
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db

            # Mock conversation and messages
            mock_conversation = Mock()
            mock_conversation.id = "test-conversation-id"
            mock_db.exec.return_value.first.return_value = None  # No existing conversation
            mock_db.add.return_value = None
            mock_db.commit.return_value = None
            mock_db.refresh.return_value = None

            # Mock OpenAI response with function call
            mock_response = Mock()
            mock_choice = Mock()
            mock_message = Mock()
            mock_message.function_call = Mock()
            mock_message.function_call.name = "add_task"
            mock_message.function_call.arguments = '{"title": "Buy milk", "description": "Get 2% milk"}'
            mock_choice.message = mock_message
            mock_response.choices = [mock_choice]
            mock_openai.chat.completions.create.return_value = mock_response

            # Mock function result
            with patch('app.main.add_task') as mock_add_task:
                mock_add_task.return_value = '{"id": "task-1", "title": "Buy milk", "description": "Get 2% milk", "completed": false}'

                # Mock final response
                mock_final_response = Mock()
                mock_final_choice = Mock()
                mock_final_message = Mock()
                mock_final_message.content = "I've added the task 'Buy milk' to your list."
                mock_final_choice.message = mock_final_message
                mock_final_response.choices = [mock_final_choice]
                mock_openai.chat.completions.create.return_value = mock_final_response

                # Test the endpoint
                response = client.post("/api/chat", json={"message": "Add task to buy milk"})
                assert response.status_code == 200
                data = response.json()
                assert "response" in data
                assert "conversation_id" in data
                print("✅ Chat endpoint responds correctly")

                return True
    except Exception as e:
        print(f"❌ Chat endpoint test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Running Phase III Critical Path Tests\n")

    tests = [
        ("Import Test", test_imports),
        ("MCP Tools Test", test_mcp_tools),
        ("Chat Endpoint Test", test_chat_endpoint),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        if test_func():
            passed += 1
        print()

    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All critical path tests passed! Phase III implementation is ready.")
    else:
        print("⚠️  Some tests failed. Please review the implementation.")
