import os
import json
import aiohttp
from typing import Any, Literal, TypedDict, Optional, List
from datetime import datetime
from pydantic.v1 import UUID4
from uagents import Model, Protocol, Context
from uuid import uuid4
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

# ==================== AI PROTOCOLS ====================

class GeneratePostRequest(Model):
    topic: str
    include_hashtags: bool = True
    language: str = "en"
    include_image: bool = False

class GeneratePostResponse(Model):
    text: str
    hashtags: List[str] = []
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None  # URL from image generation agent
    error: Optional[str] = None

class GenerateImageRequest(Model):
    topic: str

class GenerateImageResponse(Model):
    image_prompt: str
    image_url: Optional[str] = None  # URL from image generation agent
    error: Optional[str] = None

# ==================== LINKEDIN PROTOCOLS ====================

class LinkedInAuthRequest(Model):
    user_id: str

class LinkedInAuthResponse(Model):
    auth_url: str

class LinkedInCallbackRequest(Model):
    code: str
    state: str

class LinkedInCallbackResponse(Model):
    message: str
    profile: Optional[dict] = None
    error: Optional[str] = None

class LinkedInPostRequest(Model):
    user_id: str
    text: str
    image_base64: Optional[str] = None

class LinkedInPostResponse(Model):
    message: str
    post_id: Optional[str] = None
    error: Optional[str] = None

class LinkedInAIPostRequest(Model):
    user_id: str
    topic: str
    include_image: bool = False
    language: str = "en"

class LinkedInAIPostResponse(Model):
    text: str
    hashtags: List[str] = []
    image_url: Optional[str] = None  # URL from image generation agent
    error: Optional[str] = None

class LinkedInConnectionStatusRequest(Model):
    user_id: str

class LinkedInConnectionStatusResponse(Model):
    is_connected: bool
    profile: Optional[dict] = None
    expires_at: Optional[str] = None

# ==================== SCHEDULER PROTOCOLS ====================

class CreateScheduleRequest(Model):
    user_id: str
    topic: str
    schedule: str  # cron expression
    include_image: bool = False
    custom_text: Optional[str] = None

class CreateScheduleResponse(Model):
    message: str
    schedule_id: Optional[str] = None
    next_post_at: Optional[str] = None
    error: Optional[str] = None

class GetSchedulesRequest(Model):
    user_id: str

class GetSchedulesResponse(Model):
    schedules: List[dict] = []
    error: Optional[str] = None

class ScheduleActionRequest(Model):
    user_id: str
    schedule_id: str
    action: str  # "activate", "deactivate", "delete"

class ScheduleActionResponse(Model):
    message: str
    error: Optional[str] = None

# ==================== TASKS PROTOCOLS ====================

class CreateTaskRequest(Model):
    user_id: str
    db_name: str
    title: str
    description: Optional[str] = None
    status: str = "draft"

class CreateTaskResponse(Model):
    message: str
    task_id: Optional[str] = None
    error: Optional[str] = None

class GetTasksRequest(Model):
    user_id: str
    db_name: str

class GetTasksResponse(Model):
    tasks: List[dict] = []
    error: Optional[str] = None

class GetTaskRequest(Model):
    user_id: str
    db_name: str
    task_id: str

class GetTaskResponse(Model):
    task: Optional[dict] = None
    error: Optional[str] = None

class UpdateTaskRequest(Model):
    user_id: str
    db_name: str
    task_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class UpdateTaskResponse(Model):
    message: str
    task: Optional[dict] = None
    error: Optional[str] = None

class DeleteTaskRequest(Model):
    user_id: str
    db_name: str
    task_id: str

class DeleteTaskResponse(Model):
    message: str
    error: Optional[str] = None

# ==================== SOCIAL PROTOCOLS ====================

class WhatsAppMessageRequest(Model):
    to: str
    text: str

class WhatsAppMessageResponse(Model):
    message: str
    error: Optional[str] = None

class TwitterAuthRequest(Model):
    pass

class TwitterAuthResponse(Model):
    auth_url: str

class TwitterCallbackRequest(Model):
    code: str

class TwitterCallbackResponse(Model):
    message: str
    error: Optional[str] = None

# ==================== CHAT PROTOCOL ====================

def create_text_chat(text: str, end_session: bool = False) -> ChatMessage:
    content = [TextContent(type="text", text=text)]
    if end_session:
        content.append(EndSessionContent(type="end-session"))
    return ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=content,
    )

# Define protocols
# Use the chat protocol spec - it defines AgentChatProtocol:0.3.0
# The name/version will be overridden by the spec, which is expected
chat_proto = Protocol(name="SmartPostAIChatProtocol", version="0.1.0", spec=chat_protocol_spec)

ai_proto = Protocol(name="AIServiceProtocol", version="0.1.0")
linkedin_proto = Protocol(name="LinkedInServiceProtocol", version="0.1.0")
scheduler_proto = Protocol(name="SchedulerServiceProtocol", version="0.1.0")
tasks_proto = Protocol(name="TasksServiceProtocol", version="0.1.0")
social_proto = Protocol(name="SocialServiceProtocol", version="0.1.0")

