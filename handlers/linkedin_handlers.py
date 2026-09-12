"""LinkedIn REST handlers"""
from typing import Dict, Any
from uagents import Context
from rest_models import (
    LinkedInAuthRESTRequest,
    LinkedInAuthRESTResponse,
    LinkedInCallbackRESTRequest,
    LinkedInCallbackRESTResponse,
    LinkedInCallbackRedirectResponse,
    LinkedInPostRESTRequest,
    LinkedInPostRESTResponse,
    LinkedInStatusRESTResponse,
    LinkedInDisconnectRESTRequest,
    LinkedInDisconnectRESTResponse,
    UploadImageRESTRequest,
    UploadImageRESTResponse,
    LinkedInAIPostRESTRequest,
    LinkedInAIPostRESTResponse,
)
from utils.auth import _get_user_id_from_token, _request_query_params

def register_linkedin_handlers(agent, linkedin_service, ai_service, payment_service, supabase_admin, scheduler_service=None):
    """Register LinkedIn-related REST handlers"""
    
    @agent.on_rest_post("/api/linkedin/auth-url", LinkedInAuthRESTRequest, LinkedInAuthRESTResponse)
    async def handle_linkedin_auth_rest(ctx: Context, req: LinkedInAuthRESTRequest) -> LinkedInAuthRESTResponse:
        """Get LinkedIn auth URL via REST"""
        try:
            result = linkedin_service.generate_auth_url(req.user_id)
            return LinkedInAuthRESTResponse(auth_url=result["auth_url"])
        except Exception as e:
            return LinkedInAuthRESTResponse(auth_url="", error=str(e))
    
    @agent.on_rest_get("/linkedin/connect", LinkedInAuthRESTResponse)
    async def handle_linkedin_connect_frontend(ctx: Context) -> LinkedInAuthRESTResponse:
        """Get LinkedIn OAuth URL - Frontend version"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return LinkedInAuthRESTResponse(auth_url="", error="Authentication required")
            
            if not linkedin_service.client_id or not linkedin_service.redirect_uri:
                return LinkedInAuthRESTResponse(auth_url="", error="LinkedIn service not configured")
            
            result = linkedin_service.generate_auth_url(user_id)
            auth_url = result["auth_url"]
            
            response = LinkedInAuthRESTResponse(auth_url=auth_url, error=None)
            response_dict = response.model_dump()
            response_dict['authUrl'] = auth_url
            return response_dict
        except Exception as e:
            return LinkedInAuthRESTResponse(auth_url="", error=str(e))
    
    @agent.on_rest_get("/linkedin/callback", LinkedInCallbackRedirectResponse)
    async def handle_linkedin_callback_get(ctx: Context):
        """Handle LinkedIn OAuth callback redirect (GET) - Returns HTML redirect"""
        try:
            query_params = _request_query_params.get({})
            code = query_params.get('code')
            state = query_params.get('state')
            error = query_params.get('error')
            
            
            import os
            frontend_url = os.getenv("FRONTEND_URL") or "https://smart-post-ai-frontend.vercel.app"
            
            base_redirect = f"{frontend_url}/dashboard"
            redirect_url = base_redirect
            
            if error:
                redirect_url = f"{base_redirect}?linkedin=error&message={error}"
            elif not code or not state:
                redirect_url = f"{base_redirect}?linkedin=error&message=Missing+authorization+code"
            else:
                result = await linkedin_service.handle_callback(code, state)
                
                if result.get("error"):
                    redirect_url = f"{base_redirect}?linkedin=error&message={result['error']}"
                else:
                    redirect_url = f"{base_redirect}?linkedin=connected"
            
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
            frontend_url = os.getenv("FRONTEND_URL", "")
            if not frontend_url:
                frontend_url = "/dashboard"
            error_url = f"{frontend_url}/dashboard?linkedin=error&message={str(e)}"
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

    @agent.on_rest_get("/auth/linkedin/callback", LinkedInCallbackRedirectResponse)
    async def handle_linkedin_callback_get_alias(ctx: Context):
        try:
            query_params = _request_query_params.get({})
            code = query_params.get('code')
            state = query_params.get('state')
            error = query_params.get('error')
            import os
            frontend_url = os.getenv("FRONTEND_URL", "")
            if not frontend_url:
                raise ValueError("FRONTEND_URL environment variable is required")
            base_redirect = f"{frontend_url}/dashboard"
            redirect_url = base_redirect
            if error:
                redirect_url = f"{base_redirect}?linkedin=error&message={error}"
            elif not code or not state:
                redirect_url = f"{base_redirect}?linkedin=error&message=Missing+authorization+code"
            else:
                result = await linkedin_service.handle_callback(code, state)
                if result.get("error"):
                    redirect_url = f"{base_redirect}?linkedin=error&message={result['error']}"
                else:
                    redirect_url = f"{base_redirect}?linkedin=connected"
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
            frontend_url = os.getenv("FRONTEND_URL", "")
            if not frontend_url:
                frontend_url = "/dashboard"
            error_url = f"{frontend_url}/dashboard?linkedin=error&message={str(e)}"
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
    
    @agent.on_rest_post("/api/linkedin/callback", LinkedInCallbackRESTRequest, LinkedInCallbackRESTResponse)
    async def handle_linkedin_callback_rest(ctx: Context, req: LinkedInCallbackRESTRequest) -> LinkedInCallbackRESTResponse:
        """Handle LinkedIn callback via REST"""
        try:
            result = await linkedin_service.handle_callback(req.code, req.state)
            return LinkedInCallbackRESTResponse(
                message=result.get("message", ""),
                profile=result.get("profile"),
                error=result.get("error"),
            )
        except Exception as e:
            return LinkedInCallbackRESTResponse(message="", error=str(e))
    
    @agent.on_rest_get("/api/linkedin/status", LinkedInStatusRESTResponse)
    async def handle_linkedin_status_rest(ctx: Context, user_id: str = None) -> Dict[str, Any]:
        """Get LinkedIn connection status via REST"""
        try:
            if not user_id:
                user_id = ctx.rest_params.get("user_id") if hasattr(ctx, 'rest_params') else None
            if not user_id:
                return {"error": "user_id is required"}
            
            result = await linkedin_service.get_connection_status(user_id)
            return {
                "is_connected": result.get("is_connected", False),
                "profile": result.get("profile"),
                "expires_at": result.get("expires_at"),
                "error": result.get("error"),
            }
        except Exception as e:
            return {"error": str(e)}
    
    @agent.on_rest_get("/linkedin/status", LinkedInStatusRESTResponse)
    async def handle_linkedin_status_frontend(ctx: Context) -> LinkedInStatusRESTResponse:
        """Get LinkedIn connection status - Frontend version"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return LinkedInStatusRESTResponse(is_connected=False, profile=None, error=None)
            
            result = await linkedin_service.get_connection_status(user_id)
            profile = result.get("profile")
            
            return LinkedInStatusRESTResponse(
                is_connected=result.get("is_connected", False),
                profile=profile,
                expires_at=result.get("expires_at"),
                error=result.get("error"),
            )
        except Exception as e:
            return LinkedInStatusRESTResponse(is_connected=False, profile=None, error=str(e))
    
    @agent.on_rest_post("/api/linkedin/disconnect", LinkedInDisconnectRESTRequest, LinkedInDisconnectRESTResponse)
    async def handle_linkedin_disconnect_rest(ctx: Context, req: LinkedInDisconnectRESTRequest) -> LinkedInDisconnectRESTResponse:
        """Disconnect LinkedIn account via REST"""
        try:
            user_id = req.user_id or await _get_user_id_from_token(ctx)
            if not user_id:
                return LinkedInDisconnectRESTResponse(success=False, error="Authentication required")
            
            # Delete LinkedIn connection from database
            if linkedin_service.supabase_admin:
                result = linkedin_service.supabase_admin.table("linkedin_connections").delete().eq("user_id", user_id).execute()
                
                if result.data is not None:  # Successful deletion (even if no records existed)
                    return LinkedInDisconnectRESTResponse(
                        success=True,
                        message="LinkedIn disconnected successfully"
                    )
                else:
                    return LinkedInDisconnectRESTResponse(success=False, error="Failed to disconnect LinkedIn")
            else:
                return LinkedInDisconnectRESTResponse(success=False, error="Database not configured")
        except Exception as e:
            return LinkedInDisconnectRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_post("/linkedin/disconnect", LinkedInDisconnectRESTRequest, LinkedInDisconnectRESTResponse)
    async def handle_linkedin_disconnect_frontend(ctx: Context, req: LinkedInDisconnectRESTRequest) -> LinkedInDisconnectRESTResponse:
        """Disconnect LinkedIn account - Frontend version"""
        try:
            user_id = req.user_id or await _get_user_id_from_token(ctx)
            if not user_id:
                return LinkedInDisconnectRESTResponse(success=False, error="Authentication required")
            
            # Delete LinkedIn connection from database
            if linkedin_service.supabase_admin:
                result = linkedin_service.supabase_admin.table("linkedin_connections").delete().eq("user_id", user_id).execute()
                
                if result.data is not None:  # Successful deletion (even if no records existed)
                    return LinkedInDisconnectRESTResponse(
                        success=True,
                        message="LinkedIn disconnected successfully"
                    )
                else:
                    return LinkedInDisconnectRESTResponse(success=False, error="Failed to disconnect LinkedIn")
            else:
                return LinkedInDisconnectRESTResponse(success=False, error="Database not configured")
        except Exception as e:
            return LinkedInDisconnectRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_post("/api/linkedin/post", LinkedInPostRESTRequest, LinkedInPostRESTResponse)
    async def handle_linkedin_post_rest(ctx: Context, req: LinkedInPostRESTRequest) -> LinkedInPostRESTResponse:
        """Post to LinkedIn via REST - Free mode for hackathon"""
        try:
            user_id = req.user_id or await _get_user_id_from_token(ctx)
            
            image_url = req.imageUrl if hasattr(req, 'imageUrl') else None
            service_name = "linkedin_post_with_image" if (req.image_base64 or image_url) else "linkedin_post"
            
            if req.image_base64 or image_url:
                if req.image_base64 and (req.image_base64.startswith("http://") or req.image_base64.startswith("https://")):
                    image_url = req.image_base64
                    image_base64 = None
                else:
                    image_base64 = req.image_base64
                
                result = await linkedin_service.post_with_image(req.user_id, req.text, image_base64=image_base64, image_url=image_url)
            else:
                result = await linkedin_service.post_text(req.user_id, req.text)
            
            post_id = result.get("post_id")
            
            return LinkedInPostRESTResponse(
                message=result.get("message", ""),
                post_id=post_id,
                error=result.get("error"),
            )
        except Exception as e:
            return LinkedInPostRESTResponse(message="", error=str(e))
    
    @agent.on_rest_post("/linkedin/upload-image", UploadImageRESTRequest, UploadImageRESTResponse)
    async def handle_upload_image(ctx: Context, req: UploadImageRESTRequest) -> Dict[str, Any]:
        """Upload image to Supabase storage bucket"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"image_url": None, "error": "Authentication required"}
            
            if not supabase_admin:
                return {"image_url": None, "error": "Storage not configured"}
            
            import base64
            import uuid
            
            image_data = req.image_base64
            if image_data.startswith("data:image"):
                image_data = image_data.split(",")[1]
            
            image_bytes = base64.b64decode(image_data)
            
            file_ext = "jpeg"
            mime_type = "image/jpeg"
            
            base64_lower = req.image_base64.lower()
            if "image/png" in base64_lower or "png" in base64_lower.split(",")[0]:
                file_ext = "png"
                mime_type = "image/png"
            elif "image/jpeg" in base64_lower or "jpeg" in base64_lower.split(",")[0] or "jpg" in base64_lower.split(",")[0]:
                file_ext = "jpeg"
                mime_type = "image/jpeg"
            elif "image/webp" in base64_lower or "webp" in base64_lower.split(",")[0]:
                file_ext = "webp"
                mime_type = "image/webp"
            elif "image/gif" in base64_lower or "gif" in base64_lower.split(",")[0]:
                file_ext = "gif"
                mime_type = "image/gif"
            
            filename = f"{user_id}/{uuid.uuid4()}.{file_ext}"
            
            try:
                upload_result = supabase_admin.storage.from_("images").upload(
                    path=filename,
                    file=image_bytes,
                    file_options={"content-type": mime_type}
                )
                
                image_url = supabase_admin.storage.from_("images").get_public_url(filename)
                
                return {"image_url": image_url, "error": None}
            except Exception as upload_error:
                return {"image_url": None, "error": f"Upload failed: {str(upload_error)}"}
                
        except Exception as e:
            import traceback
            return {"image_url": None, "error": str(e)}
    
    @agent.on_rest_post("/linkedin/post", LinkedInPostRESTRequest, LinkedInPostRESTResponse)
    async def handle_linkedin_post_frontend(ctx: Context, req: LinkedInPostRESTRequest) -> Dict[str, Any]:
        """Post to LinkedIn - Frontend version - Free mode for hackathon"""
        try:
            if not req.user_id:
                req.user_id = await _get_user_id_from_token(ctx)
            if not req.user_id:
                return {"message": "", "error": "Authentication required"}
            
            image_url = req.imageUrl if hasattr(req, 'imageUrl') else None
            service_name = "linkedin_post_with_image" if (req.image_base64 or image_url) else "linkedin_post"
            
            if req.image_base64 or image_url:
                if req.image_base64 and (req.image_base64.startswith("http://") or req.image_base64.startswith("https://")):
                    image_url = req.image_base64
                    image_base64 = None
                else:
                    image_base64 = req.image_base64
                
                result = await linkedin_service.post_with_image(req.user_id, req.text, image_base64=image_base64, image_url=image_url)
            else:
                result = await linkedin_service.post_text(req.user_id, req.text)
            
            linkedin_post_url = None
            linkedin_post_id = result.get("post_id")
            
            if linkedin_post_id and not result.get("error") and supabase_admin:
                if linkedin_post_id.startswith("urn:li:"):
                    linkedin_post_url = f"https://www.linkedin.com/feed/update/{linkedin_post_id}/"
                elif ":" in linkedin_post_id:
                    linkedin_post_url = f"https://www.linkedin.com/feed/update/{linkedin_post_id}/"
                else:
                    linkedin_post_url = f"https://www.linkedin.com/feed/update/{linkedin_post_id}/"
                
                try:
                    post_data = {
                        "user_id": req.user_id,
                        "topic": req.text[:100],
                        "content": req.text,
                        "hashtags": [],
                        "image_url": image_url,
                        "linkedin_post_url": linkedin_post_url,
                        "linkedin_post_id": linkedin_post_id,
                    }
                    
                    existing = supabase_admin.table("generated_posts").select("*").eq("user_id", req.user_id).is_("linkedin_post_id", "null").order("created_at", desc=True).limit(1).execute()
                    
                    if existing.data and len(existing.data) > 0:
                        supabase_admin.table("generated_posts").update({
                            "linkedin_post_url": linkedin_post_url,
                            "linkedin_post_id": linkedin_post_id,
                        }).eq("id", existing.data[0]["id"]).execute()
                    else:
                        supabase_admin.table("generated_posts").insert(post_data).execute()
                except Exception as save_error:
                    pass
            
            return {
                "message": result.get("message", ""),
                "post_id": result.get("post_id"),
                "linkedin_post_url": linkedin_post_url,
                "error": result.get("error"),
            }
        except Exception as e:
            return {"message": "", "error": str(e)}
    
    @agent.on_rest_post("/api/linkedin/ai-post", LinkedInAIPostRESTRequest, LinkedInAIPostRESTResponse)
    async def handle_linkedin_ai_post_rest(ctx: Context, req: LinkedInAIPostRESTRequest) -> LinkedInAIPostRESTResponse:
        """Generate and get AI post for LinkedIn via REST"""
        try:
            result = await ai_service.generate_linkedin_post_with_image(
                req.topic,
                req.include_image,
                req.language,
                ctx
            )
            
            if "error" in result:
                return LinkedInAIPostRESTResponse(text="", error=result["error"])
            
            full_text = result["text"]
            if result.get("hashtags"):
                full_text += "\n\n" + " ".join(result["hashtags"])
            
            return LinkedInAIPostRESTResponse(
                text=full_text,
                hashtags=result.get("hashtags", []),
                image_base64=result.get("image_url"),  # Use image_url from agent, not base64
            )
        except Exception as e:
            return LinkedInAIPostRESTResponse(text="", error=str(e))
    
    @agent.on_rest_post("/linkedin/generate-ai-post", LinkedInAIPostRESTRequest, LinkedInAIPostRESTResponse)
    async def handle_linkedin_generate_ai_post_frontend(ctx: Context, req: LinkedInAIPostRESTRequest) -> Dict[str, Any]:
        """Generate AI post for LinkedIn - Frontend version"""
        try:
            if not req.user_id:
                req.user_id = await _get_user_id_from_token(ctx)
            if not req.user_id:
                return {"error": "Authentication required"}
            
            include_image = req.include_image or req.includeImage or False
            
            result = await ai_service.generate_linkedin_post_with_image(
                req.topic,
                include_image,
                req.language,
                ctx
            )
            
            
            if "error" in result:
                return {"text": "", "error": result["error"]}
            
            full_text = result["text"]
            if result.get("hashtags"):
                full_text += "\n\n" + " ".join(result["hashtags"])
            
            image_url = result.get("image_url")
            
            # Always save to generated_posts first (draft for review/scheduling)
            post_id = None
            if supabase_admin:
                try:
                    post_data = {
                        "user_id": req.user_id,
                        "topic": req.topic,
                        "content": full_text,
                        "hashtags": result.get("hashtags", []),
                        "language": req.language,
                    }
                    
                    if image_url:
                        post_data["image_url"] = image_url
                    
                    save_result = supabase_admin.table("generated_posts").insert(post_data).execute()
                    if save_result.data and len(save_result.data) > 0:
                        post_id = str(save_result.data[0]["id"])
                except Exception as save_error:
                    import traceback
                    print(f"❌ Database save error in frontend handler: {save_error}")
                    print(f"❌ Traceback: {traceback.format_exc()}")
                    return {"error": f"Failed to save post: {str(save_error)}"}
            
            # Handle scheduling - always create schedule if schedule/scheduled_at provided
            schedule_id = None
            review_link = None
            
            if req.schedule or req.scheduled_at:
                # User wants to schedule the post
                # Use scheduler_service if available, otherwise create a new instance
                current_scheduler_service = scheduler_service
                if not current_scheduler_service:
                    from scheduler_service import SchedulerService
                    current_scheduler_service = SchedulerService(supabase_admin, supabase_admin, ai_service)
                
                schedule_result = await current_scheduler_service.create_scheduled_post(
                    req.user_id,
                    req.topic,
                    req.schedule or "",  # Cron expression
                    include_image,
                    full_text,  # Use generated content as custom_text
                    image_url,
                    req.scheduled_at,  # ISO datetime for one-time schedule
                    req.require_approval,
                    req.team_emails  # Team emails for approval
                )
                
                if schedule_result.get("schedule_id"):
                    schedule_id = str(schedule_result["schedule_id"])
                    review_link = schedule_result.get("review_link")
                    review_link = schedule_result.get("review_link")
                elif schedule_result.get("error"):
                    # Don't return error, just log it - post is still saved for review
                    pass
            
            final_image_url = result.get("image_url") or image_url
            
            # Always include schedule options in response (even if None)
            response_data = {
                "text": full_text,
                "hashtags": result.get("hashtags", []),
                "imageUrl": final_image_url,
                "image": final_image_url,
                "image_url": final_image_url,
                "postId": post_id,
                "schedule_id": schedule_id,  # Will be None if not scheduled, but field always present
                "review_link": review_link,  # Will be None if not scheduled/approved, but field always present
                "error": None
            }
            
            return response_data
        except Exception as e:
            import traceback
            print(f"❌ AI post generation error in frontend handler: {e}")
            print(f"❌ Traceback: {traceback.format_exc()}")
            return {"error": str(e)}

