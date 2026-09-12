"""
SmartPostAI Agent - Social Media Automation Agent

Built for MNEE Hackathon: Programmable Money for Agents, Commerce, and Automated Finance
Track: AI & Agent Payments
Contract Address: 0x8ccedbAe4916b79da7F3F612EfB2EB93A2bFD6cF
Hackathon Deadline: January 13, 2026
"""

import os
from enum import Enum
from typing import Dict, Any, Optional
from uagents import Agent, Context, Model
from uagents.experimental.quota import QuotaProtocol, RateLimit
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent, StartSessionContent, EndSessionContent, ChatAcknowledgement
from supabase import create_client, Client
from dotenv import load_dotenv

from protocol import (
    chat_proto,
)
from services.ai import AIService
from linkedin_service import LinkedInService
from tasks_service import TasksService
from scheduler_service import SchedulerService
# from payment_service import PaymentService  # Deleted for MVP
# from mnee_service import MneeService  # Deleted for MVP
from rest_models import (
    HealthRESTResponse,
)
import time
load_dotenv()

# Context variables are now in utils.auth - import them
# They will be set by the patched ASGI handler below

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase_client: Optional[Client] = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

supabase_admin: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase_admin = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
else:
    supabase_admin = supabase_client

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET") or os.getenv("JWT_SECRET", "supersecret")

# Import handlers and utils
from handlers.payment_handlers import register_payment_handlers
from handlers.mnee_handlers import register_mnee_handlers
from handlers.auth_handlers import register_auth_handlers
from handlers.wallet_handlers import register_wallet_handlers
from handlers.ai_handlers import register_ai_handlers
from handlers.protocol_handlers import register_protocol_handlers, register_chat_protocol, register_health_protocol
from handlers.linkedin_handlers import register_linkedin_handlers
from handlers.scheduler_handlers import register_scheduler_handlers
from handlers.task_handlers import register_task_handlers
from handlers.template_handlers import register_template_handlers
from handlers.post_handlers import register_post_handlers
from handlers.analytics_handlers import register_analytics_handlers
from handlers.tip_handlers import register_tip_handlers
# Slack integration temporarily disabled
# from handlers.slack_handlers import register_slack_handlers
# from slack_service import SlackService
# from slack_bot import SlackBot
from utils.auth import set_jwt_secret, _request_headers, _request_query_params

set_jwt_secret(JWT_SECRET)

ai_service = AIService(agent_context=None)
linkedin_service = LinkedInService(supabase_client, supabase_admin)
tasks_service = TasksService(supabase_client)
# payment_service = PaymentService(supabase_client, supabase_admin)  # Deleted for MVP
scheduler_service = SchedulerService(supabase_client, supabase_admin, ai_service, None)  # No payment service for MVP
# mnee_service = MneeService()  # Deleted for MVP
# Slack integration temporarily disabled
# slack_service = SlackService(supabase_client, supabase_admin)
# slack_bot = SlackBot(slack_service, ai_service, linkedin_service, payment_service, scheduler_service, supabase_admin)

AGENT_NAME = "SmartPostAI"
agent = Agent(
    name=AGENT_NAME,
    mailbox=True,
    port=int(os.getenv("PORT", "8000")),
    seed=os.getenv("AGENT_SEED", "0000000000000000000000000000000000000000000000000000000000000000--"),
)

# Monkey-patch uagents ASGI handler
def _patch_asgi_handler():
    from uagents import asgi
    original_handle_rest = asgi.ASGIServer._handle_rest
    
    async def patched_handle_rest(self, headers, handlers, send, receive):
        headers_dict = {}
        for key, value in headers.items():
            if isinstance(key, bytes):
                key_str = key.decode('utf-8').lower()
            else:
                key_str = str(key).lower()
            
            if isinstance(value, bytes):
                value_str = value.decode('utf-8')
            elif isinstance(value, list):
                value_str = value[0].decode('utf-8') if isinstance(value[0], bytes) else str(value[0])
            else:
                value_str = str(value)
            
            headers_dict[key_str] = value_str
        
        from utils.auth import _request_headers, _request_query_params
        _request_headers.set(headers_dict)
        
        query_params = {}
        if hasattr(self, '_last_scope'):
            scope = self._last_scope
            query_string = scope.get('query_string', b'')
            if query_string:
                from urllib.parse import parse_qs, unquote
                parsed = parse_qs(query_string.decode('utf-8'))
                query_params = {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
        _request_query_params.set(query_params)
        
        raw_contents = await asgi._read_asgi_body(receive)
        
        # Store raw body for Slack commands (form-urlencoded)
        from utils.auth import _request_body
        _request_body.set(raw_contents)
        
        received_request = None
        
        if len(handlers) > 1:
            if b"x-uagents-address" not in headers:
                await self._asgi_send(
                    send=send,
                    status_code=400,
                    body={"error": "missing header: x-uagents-address"},
                )
                return
            destination = headers[b"x-uagents-address"].decode()
            rest_handler = handlers.get(destination)
        else:
            destination, rest_handler = handlers.popitem()
        
        if not rest_handler:
            await self._asgi_send(send=send, status_code=404, body={"error": "not found"})
            return
        
        if rest_handler.method == "POST":
            # Check content type for form-urlencoded (Slack commands)
            content_type_header = headers.get(b'content-type', b'').decode('utf-8', errors='ignore').lower()
            is_form_urlencoded = 'application/x-www-form-urlencoded' in content_type_header
            
            if rest_handler.request_model is not None:
                if not raw_contents:
                    await self._asgi_send(
                        send=send, status_code=400, body={"error": "No request body found"}
                    )
                    return
                
                # Handle form-urlencoded for Slack commands
                if is_form_urlencoded and rest_handler.endpoint == "/slack/commands":
                    # Parse form-urlencoded data and create model
                    try:
                        from urllib.parse import parse_qs
                        body_str = raw_contents.decode('utf-8') if isinstance(raw_contents, bytes) else str(raw_contents)
                        form_data = parse_qs(body_str)
                        slack_data = {k: v[0] if isinstance(v, list) and len(v) > 0 else v for k, v in form_data.items()}
                        
                        # Create request model from form data
                        received_request = rest_handler.request_model(
                            token=slack_data.get("token", ""),
                            team_id=slack_data.get("team_id", ""),
                            team_domain=slack_data.get("team_domain"),
                            channel_id=slack_data.get("channel_id", ""),
                            channel_name=slack_data.get("channel_name"),
                            user_id=slack_data.get("user_id", ""),
                            user_name=slack_data.get("user_name"),
                            command=slack_data.get("command", ""),
                            text=slack_data.get("text"),
                            response_url=slack_data.get("response_url"),
                            trigger_id=slack_data.get("trigger_id"),
                        )
                    except Exception as err:
                        await self._asgi_send(send=send, status_code=400, body={"error": f"Failed to parse form data: {str(err)}"})
                        return
                else:
                    # Normal JSON parsing
                    try:
                        received_request = rest_handler.request_model.model_validate_json(raw_contents)
                    except asgi.ValidationErrorV1 as err:
                        e = dict(err.errors().pop())
                        await self._asgi_send(send=send, status_code=400, body=e)
                        return
        
        from uagents import dispatch
        handler_response = await dispatch.dispatcher.dispatch_rest(
            destination=destination,
            method=rest_handler.method,
            endpoint=rest_handler.endpoint,
            message=received_request,
        )
        
        if isinstance(handler_response, str) and (handler_response.strip().startswith('<!DOCTYPE') or handler_response.strip().startswith('<html')):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/html; charset=utf-8"]],
            })
            await send({
                "type": "http.response.body",
                "body": handler_response.encode('utf-8')
            })
            return
        
        try:
            if not isinstance(handler_response, dict) and not isinstance(handler_response, rest_handler.response_model):
                raise ValueError({"error": "Handler response must be a dict or a model"})
            validated_response = rest_handler.response_model.model_validate(handler_response)
        except (asgi.ValidationErrorV1, ValueError) as err:
            await self._asgi_send(
                send=send,
                status_code=500,
                body={"error": "Handler response does not match response schema."},
            )
            return
        
        await self._asgi_send(send=send, body=validated_response.model_dump())
    
    original_call = asgi.ASGIServer.__call__
    
    async def patched_call(self, scope, receive, send):
        self._last_scope = scope
        return await original_call(self, scope, receive, send)
    
    asgi.ASGIServer.__call__ = patched_call
    asgi.ASGIServer._handle_rest = patched_handle_rest

_patch_asgi_handler()

# ==================== PROTOCOL HANDLERS ====================
register_protocol_handlers(agent, ai_service, linkedin_service, scheduler_service, tasks_service)
register_chat_protocol(agent, chat_proto, ai_service)
register_health_protocol(agent, AGENT_NAME)

# ==================== REST ENDPOINTS ====================
# All REST endpoints registered via handler modules

@agent.on_rest_get("/api/health", HealthRESTResponse)
async def handle_health_rest(ctx: Context) -> Dict[str, Any]:
    """Health check via REST"""
    return {
        "status": "healthy",
        "agent_name": AGENT_NAME,
        "timestamp": int(time.time()),
    }

# ==================== SCHEDULER BACKGROUND TASK ====================

@agent.on_interval(period=60.0)
async def check_scheduled_posts(ctx: Context):
    """Periodically check and execute scheduled posts"""
    await scheduler_service.handle_scheduled_posts(ctx)

# ==================== REGISTER HANDLERS ====================

register_auth_handlers(agent, supabase_client, supabase_admin)
register_wallet_handlers(agent, supabase_client, supabase_admin)
register_ai_handlers(agent, ai_service, None, supabase_admin, scheduler_service)  # No payment service for MVP
# register_payment_handlers(agent, payment_service, mnee_service)  # Deleted for MVP
# register_mnee_handlers(agent, mnee_service)  # Deleted for MVP
register_linkedin_handlers(agent, linkedin_service, ai_service, None, supabase_admin, scheduler_service)  # No payment service for MVP
register_scheduler_handlers(agent, scheduler_service, None)  # No payment service for MVP
register_task_handlers(agent, tasks_service)
register_template_handlers(agent, None, supabase_admin)  # No payment service for MVP
register_post_handlers(agent, ai_service, linkedin_service, None, supabase_admin)  # No payment service for MVP
register_analytics_handlers(agent, supabase_admin)
# register_tip_handlers(agent, payment_service, mnee_service, supabase_admin)  # Deleted for MVP
# Slack integration temporarily disabled
# register_slack_handlers(agent, slack_service, slack_bot, payment_service, supabase_admin)

# ==================== AGENT STARTUP ====================

@agent.on_event("startup")
async def startup_handler(ctx: Context):
    """Initialize services with agent context on startup"""
    global ai_service
    ai_service = AIService(agent_context=ctx)
    global scheduler_service
    scheduler_service = SchedulerService(supabase_client, supabase_admin, ai_service, None)  # No payment service for MVP

if __name__ == "__main__":
    agent.run()

