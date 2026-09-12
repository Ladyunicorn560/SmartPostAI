"""Slack REST handlers"""
from typing import Dict, Any
from uagents import Context
from rest_models import (
    SlackAuthRESTRequest,
    SlackAuthRESTResponse,
    SlackCallbackRESTRequest,
    SlackCallbackRESTResponse,
    SlackStatusRESTResponse,
    SlackCommandRESTRequest,
    SlackCommandRESTResponse,
    SlackEventRESTRequest,
    SlackEventRESTResponse,
    SlackDisconnectRESTRequest,
)
from utils.auth import _get_user_id_from_token, _request_query_params, _request_body
import json
from urllib.parse import parse_qs

def register_slack_handlers(agent, slack_service, slack_bot, payment_service, supabase_admin):
    """Register Slack-related REST handlers"""
    
    @agent.on_rest_get("/slack/connect", SlackAuthRESTResponse)
    async def handle_slack_connect_frontend(ctx: Context) -> SlackAuthRESTResponse:
        """Get Slack OAuth URL - Frontend version"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return SlackAuthRESTResponse(auth_url="", error="Authentication required")
            
            if not slack_service.client_id or not slack_service.redirect_uri:
                return SlackAuthRESTResponse(auth_url="", error="Slack service not configured")
            
            result = slack_service.generate_auth_url(user_id)
            
            if "error" in result:
                return SlackAuthRESTResponse(auth_url="", error=result["error"])
            
            auth_url = result.get("auth_url", "")
            if not auth_url:
                return SlackAuthRESTResponse(auth_url="", error="Failed to generate OAuth URL")
            
            return SlackAuthRESTResponse(auth_url=auth_url, error=None)
        except Exception as e:
            return SlackAuthRESTResponse(auth_url="", error=str(e))
    
    @agent.on_rest_get("/slack/callback", SlackCallbackRESTResponse)
    async def handle_slack_callback_get(ctx: Context):
        """Handle Slack OAuth callback redirect (GET) - Returns HTML redirect"""
        try:
            query_params = _request_query_params.get({})
            code = query_params.get('code')
            state = query_params.get('state')
            error = query_params.get('error')
            
            import os
            frontend_url = os.getenv("FRONTEND_URL", "")
            if not frontend_url:
                frontend_url = "/dashboard"
            
            base_redirect = f"{frontend_url}/dashboard"
            redirect_url = base_redirect
            
            if error:
                redirect_url = f"{base_redirect}?slack=error&message={error}"
            elif not code or not state:
                redirect_url = f"{base_redirect}?slack=error&message=Missing+authorization+code"
            else:
                result = await slack_service.handle_callback(code, state)
                
                if result.get("error"):
                    redirect_url = f"{base_redirect}?slack=error&message={result['error']}"
                else:
                    redirect_url = f"{base_redirect}?slack=connected&team={result.get('team_name', '')}"
            
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0; url={redirect_url}">
    <script>window.location.href = "{redirect_url}";</script>
    <title>Redirecting...</title>
</head>
<body>
    <p>Redirecting to dashboard... <a href="{redirect_url}">Click here if not redirected</a></p>
</body>
</html>"""
            
            return html_content
        except Exception as e:
            import os
            import traceback
            frontend_url = os.getenv("FRONTEND_URL", "/dashboard")
            error_url = f"{frontend_url}/dashboard?slack=error&message={str(e)}"
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0; url={error_url}">
    <script>window.location.href = "{error_url}";</script>
</head>
<body>
    <p>Redirecting... <a href="{error_url}">Click here</a></p>
</body>
</html>"""
            return html_content
    
    @agent.on_rest_post("/slack/callback", SlackCallbackRESTRequest, SlackCallbackRESTResponse)
    async def handle_slack_callback_post(ctx: Context, req: SlackCallbackRESTRequest) -> SlackCallbackRESTResponse:
        """Handle Slack OAuth callback - POST version"""
        try:
            if req.error:
                return SlackCallbackRESTResponse(success=False, error=req.error)
            
            if not req.code or not req.state:
                return SlackCallbackRESTResponse(success=False, error="Missing authorization code or state")
            
            result = await slack_service.handle_callback(req.code, req.state)
            
            if result.get("error"):
                return SlackCallbackRESTResponse(
                    success=False,
                    error=result.get("error")
                )
            
            return SlackCallbackRESTResponse(
                success=True,
                team_id=result.get("team_id"),
                team_name=result.get("team_name")
            )
        except Exception as e:
            return SlackCallbackRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_get("/slack/status", SlackStatusRESTResponse)
    async def handle_slack_status(ctx: Context) -> SlackStatusRESTResponse:
        """Get Slack connection status"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return SlackStatusRESTResponse(is_connected=False, error="Authentication required")
            
            if not supabase_admin:
                return SlackStatusRESTResponse(is_connected=False, error="Database not configured")
            
            result = supabase_admin.table("slack_connections").select("*").eq("user_id", user_id).order("connected_at", desc=True).limit(1).execute()
            
            if result.data and len(result.data) > 0:
                connection = result.data[0]
                return SlackStatusRESTResponse(
                    is_connected=True,
                    team_id=connection.get("team_id"),
                    team_name=connection.get("team_name"),
                    connected_at=connection.get("connected_at")
                )
            
            return SlackStatusRESTResponse(is_connected=False, error=None)
        except Exception as e:
            return SlackStatusRESTResponse(is_connected=False, error=str(e))
    
    @agent.on_rest_post("/slack/disconnect", SlackDisconnectRESTRequest, SlackStatusRESTResponse)
    async def handle_slack_disconnect(ctx: Context, req: SlackDisconnectRESTRequest) -> SlackStatusRESTResponse:
        """Disconnect Slack workspace"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return SlackStatusRESTResponse(is_connected=False, error="Authentication required")
            
            if not supabase_admin:
                return SlackStatusRESTResponse(is_connected=False, error="Database not configured")
            
            # Delete all Slack connections for this user
            supabase_admin.table("slack_connections").delete().eq("user_id", user_id).execute()
            
            return SlackStatusRESTResponse(is_connected=False, error=None)
        except Exception as e:
            return SlackStatusRESTResponse(is_connected=False, error=str(e))
    
    @agent.on_rest_post("/slack/commands", SlackCommandRESTRequest, SlackCommandRESTResponse)
    async def handle_slack_command(ctx: Context, req: SlackCommandRESTRequest = None) -> SlackCommandRESTResponse:
        """Handle Slack slash commands
        
        Slack sends commands as application/x-www-form-urlencoded, not JSON.
        The agent.py patched handler will parse form data and create SlackCommandRESTRequest.
        """
        try:
            # If req is None or doesn't have expected fields, try to parse from raw body
            if not req or not hasattr(req, 'command') or not req.command:
                # Fallback: Get raw body from context
                raw_body = _request_body.get(b'')
                
                if not raw_body:
                    return SlackCommandRESTResponse(
                        response_type="ephemeral",
                        text="❌ No request data received."
                    )
                
                # Parse form-urlencoded data
                body_str = raw_body.decode('utf-8') if isinstance(raw_body, bytes) else str(raw_body)
                form_data = parse_qs(body_str)
                slack_data = {k: v[0] if isinstance(v, list) and len(v) > 0 else v for k, v in form_data.items()}
                
                # Create request object from form data
                req = SlackCommandRESTRequest(
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
            
            if not req.command or not req.user_id or not req.team_id:
                return SlackCommandRESTResponse(
                    response_type="ephemeral",
                    text="❌ Invalid command request. Missing required fields."
                )
            
            if not supabase_admin:
                return SlackCommandRESTResponse(
                    response_type="ephemeral",
                    text="Service unavailable. Please try again later."
                )
            
            # Find user by Slack user_id
            slack_conn = supabase_admin.table("slack_connections").select("user_id").eq("slack_user_id", req.user_id).eq("team_id", req.team_id).limit(1).execute()
            
            if not slack_conn.data or len(slack_conn.data) == 0:
                return SlackCommandRESTResponse(
                    response_type="ephemeral",
                    text="❌ Slack account not connected. Please connect your Slack workspace in the dashboard first."
                )
            
            user_id = slack_conn.data[0].get("user_id")
            
            # Handle command
            result = await slack_bot.handle_command(
                command=req.command,
                text=req.text or "",
                user_id=user_id,
                channel=req.channel_id,
                team_id=req.team_id
            )
            
            # Return as SlackCommandRESTResponse model
            # result is already a dict with response_type, text, blocks, etc.
            return SlackCommandRESTResponse(
                response_type=result.get("response_type", "ephemeral"),
                text=result.get("text", ""),
                blocks=result.get("blocks"),
                error=result.get("error")
            )
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return SlackCommandRESTResponse(
                response_type="ephemeral",
                text=f"❌ Error processing command: {str(e)}\n\nDebug: {error_details[:200]}"
            )
    
    @agent.on_rest_post("/slack/events", SlackEventRESTRequest, SlackEventRESTResponse)
    async def handle_slack_events(ctx: Context, req: SlackEventRESTRequest) -> SlackEventRESTResponse:
        """Handle Slack Events API (for interactive components, etc.)"""
        try:
            # URL verification challenge
            if req.type == "url_verification":
                return SlackEventRESTResponse(challenge=req.challenge)
            
            # Handle other events
            event = req.event or {}
            event_type = event.get("type")
            
            # Handle app_mention, message events, etc.
            if event_type == "app_mention":
                # Bot was mentioned
                pass
            
            return SlackEventRESTResponse(ok=True)
        except Exception as e:
            return SlackEventRESTResponse(ok=False, error=str(e))

