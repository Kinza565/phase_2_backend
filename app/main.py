import sys
from pathlib import Path

# Add backend directory to path to find mcp_server
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import openai
from openai import OpenAI
import os
import json
from datetime import datetime
from sqlmodel import Session, select

from .config import CORS_ORIGINS
from .database import create_tables, get_db
from .routers import auth, tasks
from .models import Conversation, Message, MessageRole, User
from mcp_server import set_current_user, add_task, list_tasks, update_task, delete_task, complete_task
from .routers.auth import get_current_user

# Create FastAPI app
app = FastAPI(
    title="Hackathon Todo API",
    description="Multi-user Todo Full-Stack Web Application API with AI Chatbot",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Pydantic models for chat
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    conversation_id: str = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])

# Create tables on startup
@app.on_event("startup")
def on_startup():
    create_tables()

@app.get("/")
def read_root():
    return {"message": "Hackathon Todo API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI-powered chat endpoint using OpenAI Agents SDK with MCP tools."""

    # Set current user for MCP tools
    set_current_user(str(current_user.id))

    # Get or create conversation
    conversation = None
    if request.conversation_id:
        conversation = db.exec(select(Conversation).where(
            Conversation.id == request.conversation_id,
            Conversation.user_id == str(current_user.id)
        )).first()

    if not conversation:
        conversation = Conversation(user_id=str(current_user.id))
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Save user message
    user_message = Message(
        conversation_id=conversation.id,
        user_id=str(current_user.id),
        role=MessageRole.USER,
        content=request.message
    )
    db.add(user_message)
    db.commit()

    # Get conversation history for context
    messages = db.exec(select(Message).where(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at)).all()

    # Prepare messages for OpenAI
    openai_messages = []
    for msg in messages:
        openai_messages.append({
            "role": msg.role.value,
            "content": msg.content
        })

    # Add system prompt
    system_prompt = """
    You are an AI assistant for a todo application. You can help users manage their tasks using these tools:
    - add_task: Create a new task
    - list_tasks: List user's tasks (can filter by status: all, completed, pending)
    - update_task: Update an existing task
    - delete_task: Delete a task
    - complete_task: Mark a task as complete

    Always use the appropriate tool when the user wants to perform task operations.
    Be helpful and conversational, but focus on task management.
    """

    openai_messages.insert(0, {"role": "system", "content": system_prompt})

    try:
        # Call OpenAI with function calling
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=openai_messages,
            functions=[
                {
                    "name": "add_task",
                    "description": "Create a new task for the user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Task title"},
                            "description": {"type": "string", "description": "Task description"}
                        },
                        "required": ["title"]
                    }
                },
                {
                    "name": "list_tasks",
                    "description": "List user's tasks with optional filtering",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string", "enum": ["all", "completed", "pending"]},
                            "limit": {"type": "integer", "description": "Maximum number of tasks to return"}
                        }
                    }
                },
                {
                    "name": "update_task",
                    "description": "Update an existing task",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task ID"},
                            "title": {"type": "string", "description": "New title"},
                            "description": {"type": "string", "description": "New description"},
                            "completed": {"type": "boolean", "description": "Completion status"}
                        },
                        "required": ["task_id"]
                    }
                },
                {
                    "name": "delete_task",
                    "description": "Delete a task",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task ID to delete"}
                        },
                        "required": ["task_id"]
                    }
                },
                {
                    "name": "complete_task",
                    "description": "Mark a task as complete",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string", "description": "Task ID"}
                        },
                        "required": ["task_id"]
                    }
                }
            ],
            function_call="auto"
        )

        # Handle function calls
        if response.choices[0].message.function_call:
            function_call = response.choices[0].message.function_call
            function_name = function_call.name
            function_args = json.loads(function_call.arguments)

            # Execute the MCP tool function
            if function_name == "add_task":
                result = add_task(**function_args)
            elif function_name == "list_tasks":
                result = list_tasks(**function_args)
            elif function_name == "update_task":
                result = update_task(**function_args)
            elif function_name == "delete_task":
                result = delete_task(**function_args)
            elif function_name == "complete_task":
                result = complete_task(**function_args)

            # Get final response from OpenAI with function result
            openai_messages.append(response.choices[0].message)
            openai_messages.append({
                "role": "function",
                "name": function_name,
                "content": result
            })

            final_response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=openai_messages
            )
            assistant_response = final_response.choices[0].message.content
        else:
            assistant_response = response.choices[0].message.content

        # Save assistant response
        assistant_message = Message(
            conversation_id=conversation.id,
            user_id=str(current_user.id),
            role=MessageRole.ASSISTANT,
            content=assistant_response
        )
        db.add(assistant_message)
        db.commit()

        return ChatResponse(
            response=assistant_response,
            conversation_id=conversation.id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")
