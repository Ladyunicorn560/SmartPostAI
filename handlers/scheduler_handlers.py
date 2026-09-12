"""Scheduler REST handlers"""
from typing import Dict, Any
from uagents import Context
from rest_models import (
    CreateScheduleRESTRequest,
    CreateScheduleRESTResponse,
    GetSchedulesRESTResponse,
    ScheduleActionRESTRequest,
    ScheduleActionRESTResponse,
    UpdateScheduleRESTRequest,
    ReviewPostRESTRequest,
    ReviewPostRESTResponse,
    GetScheduleForReviewRESTRequest,
    GetScheduleForReviewRESTResponse,
    VerifyReviewEmailRESTRequest,
    VerifyReviewEmailRESTResponse,
    GetScheduledDatesRESTResponse,
    GetOccurrencesForDateRESTResponse,
    GetApprovalStatusRESTResponse,
)
from utils.auth import _get_user_id_from_token

def register_scheduler_handlers(agent, scheduler_service, payment_service):
    """Register scheduler-related REST handlers"""
    
    @agent.on_rest_post("/linkedin/schedule", CreateScheduleRESTRequest, CreateScheduleRESTResponse)
    async def handle_create_schedule_frontend(ctx: Context, req: CreateScheduleRESTRequest) -> Dict[str, Any]:
        """Create scheduled LinkedIn post - Frontend version"""
        try:
            if not req.user_id:
                req.user_id = await _get_user_id_from_token(ctx)
            if not req.user_id:
                return {"message": "", "error": "Authentication required"}
            
            if not req.topic or not req.topic.strip():
                return {"message": "", "error": "Topic is required"}
            
            # Check if schedule or scheduled_at is provided
            if not req.schedule and not req.scheduled_at:
                return {"message": "", "error": "Either schedule (cron expression) or scheduled_at (ISO datetime) is required"}
            
            include_image = req.include_image or req.includeImage or False
            
            # Get image URL from request or from generated_posts table
            image_url = None
            # Check if imageUrl is provided in request (from frontend)
            if req.imageUrl:
                image_url = req.imageUrl
            elif req.custom_text and include_image:
                # Try to get image URL from generated_posts table
                try:
                    user_id = req.user_id or await _get_user_id_from_token(ctx)
                    if user_id:
                        # Find latest generated post with same topic/content
                        import os
                        from supabase import create_client
                        supabase_url = os.getenv("SUPABASE_URL", "")
                        supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "")
                        if supabase_url and supabase_key:
                            supabase_admin = create_client(supabase_url, supabase_key)
                            gen_result = supabase_admin.table("generated_posts").select("image_url").eq("user_id", user_id).eq("topic", req.topic).order("created_at", desc=True).limit(1).execute()
                            if gen_result.data and gen_result.data[0].get("image_url"):
                                image_url = gen_result.data[0]["image_url"]
                except Exception as e:
                    pass
            
            # Check if require_approval is in request (from rest_models)
            require_approval = getattr(req, 'require_approval', False)
            
            # Get team_emails from request
            team_emails = getattr(req, 'team_emails', None)
            
            result = await scheduler_service.create_scheduled_post(
                req.user_id,
                req.topic,
                req.schedule or "",  # Empty string if using scheduled_at
                include_image,
                req.custom_text,
                image_url,
                req.scheduled_at,  # ISO datetime for one-time schedule
                require_approval,
                team_emails  # Team emails for approval
            )
            
            
            if result.get("error"):
                pass
            else:
                pass
            
            return {
                "message": result.get("message", ""),
                "schedule_id": result.get("schedule_id"),
                "next_post_at": result.get("next_post_at"),
                "review_link": result.get("review_link"),
                "error": result.get("error"),
            }
        except Exception as e:
            import traceback
            return {"message": "", "error": str(e)}
    
    @agent.on_rest_post("/api/scheduler/create", CreateScheduleRESTRequest, CreateScheduleRESTResponse)
    async def handle_create_schedule_rest(ctx: Context, req: CreateScheduleRESTRequest) -> CreateScheduleRESTResponse:
        """Create scheduled post via REST"""
        try:
            result = await scheduler_service.create_scheduled_post(
                req.user_id,
                req.topic,
                req.schedule,
                req.include_image,
                req.custom_text
            )
            return CreateScheduleRESTResponse(
                message=result.get("message", ""),
                schedule_id=result.get("schedule_id"),
                next_post_at=result.get("next_post_at"),
                error=result.get("error"),
            )
        except Exception as e:
            return CreateScheduleRESTResponse(message="", error=str(e))
    
    @agent.on_rest_get("/linkedin/schedules", GetSchedulesRESTResponse)
    async def handle_get_schedules_frontend(ctx: Context) -> Dict[str, Any]:
        """Get all schedules for user - Frontend version"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"schedules": [], "error": "Authentication required"}
            
            result = await scheduler_service.get_scheduled_posts(user_id)
            
            if result.get("error"):
                return {"schedules": [], "error": result.get("error")}
            
            schedules_raw = result.get("schedules", [])
            schedules_transformed = []
            
            for schedule in schedules_raw:
                post_count = 0
                if schedule.get("posted_at"):
                    post_count = 1 if schedule.get("status") == "posted" else 0
                
                schedules_transformed.append({
                    "_id": schedule.get("id"),
                    "topic": schedule.get("content", ""),
                    "schedule": schedule.get("cron_expression", ""),
                    "nextPostAt": schedule.get("scheduled_at", ""),
                    "postCount": post_count,
                    "isActive": schedule.get("status") in ["pending", "scheduled"],
                    "includeImage": schedule.get("image_url") is not None,
                    "postUrl": schedule.get("post_url"),  # LinkedIn post URL
                    "postId": schedule.get("post_id"),  # LinkedIn post ID
                })
            
            return {"schedules": schedules_transformed, "error": None}
        except Exception as e:
            return {"schedules": [], "error": str(e)}
    
    @agent.on_rest_get("/api/scheduler", GetSchedulesRESTResponse)
    async def handle_get_schedules_rest(ctx: Context, user_id: str = None) -> Dict[str, Any]:
        """Get all schedules for user via REST"""
        try:
            if not user_id:
                user_id = ctx.rest_params.get("user_id") if hasattr(ctx, 'rest_params') else None
            if not user_id:
                return {"error": "user_id is required"}
            
            result = await scheduler_service.get_scheduled_posts(user_id)
            return {
                "schedules": result.get("schedules", []),
                "error": result.get("error"),
            }
        except Exception as e:
            return {"error": str(e)}
    
    @agent.on_rest_post("/linkedin/schedules/action", ScheduleActionRESTRequest, ScheduleActionRESTResponse)
    async def handle_schedule_action_frontend(ctx: Context, req: ScheduleActionRESTRequest) -> Dict[str, Any]:
        """Activate/deactivate/delete schedule - Frontend version"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"message": "", "error": "Authentication required"}
            
            if req.action == "activate":
                result = await scheduler_service.activate_schedule(user_id, req.schedule_id)
            elif req.action == "deactivate":
                result = await scheduler_service.deactivate_schedule(user_id, req.schedule_id)
            elif req.action == "delete":
                result = await scheduler_service.delete_schedule(user_id, req.schedule_id)
            else:
                result = {"error": "Invalid action"}
            
            return {
                "message": result.get("message", ""),
                "error": result.get("error"),
            }
        except Exception as e:
            return {"message": "", "error": str(e)}
    
    @agent.on_rest_post("/api/scheduler/action", ScheduleActionRESTRequest, ScheduleActionRESTResponse)
    async def handle_schedule_action_rest(ctx: Context, req: ScheduleActionRESTRequest) -> ScheduleActionRESTResponse:
        """Activate/deactivate/delete schedule via REST"""
        try:
            if req.action == "activate":
                result = await scheduler_service.activate_schedule(req.user_id, req.schedule_id)
            elif req.action == "deactivate":
                result = await scheduler_service.deactivate_schedule(req.user_id, req.schedule_id)
            elif req.action == "delete":
                result = await scheduler_service.delete_schedule(req.user_id, req.schedule_id)
            else:
                result = {"error": "Invalid action"}
            
            return ScheduleActionRESTResponse(
                message=result.get("message", ""),
                error=result.get("error"),
            )
        except Exception as e:
            return ScheduleActionRESTResponse(message="", error=str(e))
    
    @agent.on_rest_post("/review/verify-email", VerifyReviewEmailRESTRequest, VerifyReviewEmailRESTResponse)
    async def handle_verify_review_email(ctx: Context, req: VerifyReviewEmailRESTRequest) -> Dict[str, Any]:
        """Verify team member email for review access - PUBLIC ACCESS"""
        try:
            # Get token from request body or query parameter
            from utils.auth import _request_query_params
            query_params = _request_query_params.get({})
            token = req.token or query_params.get("token") or query_params.get("id")
            
            if not token:
                return {"verified": False, "error": "Review token is required"}
            
            if not req.email:
                return {"verified": False, "error": "Email is required"}
            
            result = await scheduler_service.verify_review_email(token, req.email)
            return result
        except Exception as e:
            return {"verified": False, "error": str(e)}
    
    @agent.on_rest_get("/review", GetScheduleForReviewRESTResponse)
    async def handle_get_review_public(ctx: Context) -> Dict[str, Any]:
        """Get scheduled post for review - PUBLIC ACCESS (no auth required)"""
        try:
            # Get token and email from query parameters
            from utils.auth import _request_query_params
            query_params = _request_query_params.get({})
            token = query_params.get("token") or query_params.get("id")
            email = query_params.get("email")
            
            if not token:
                return {"error": "Review token is required (query parameter: token or id)"}
            
            result = await scheduler_service.get_schedule_for_review(token, email)
            
            return result
        except Exception as e:
            import traceback
            return {"error": str(e)}
    
    @agent.on_rest_post("/review", ReviewPostRESTRequest, ReviewPostRESTResponse)
    async def handle_review_post_public(ctx: Context, req: ReviewPostRESTRequest) -> ReviewPostRESTResponse:
        """Review and approve/reject a scheduled post - PUBLIC ACCESS (no auth required)"""
        try:
            # Get token from request body or query parameter
            from utils.auth import _request_query_params
            query_params = _request_query_params.get({})
            review_token = req.token or req.review_token or query_params.get("token") or query_params.get("id")
            
            if not review_token:
                return ReviewPostRESTResponse(
                    success=False,
                    message="",
                    error="Review token is required (in request body or query parameter)"
                )
            
            if req.action not in ["approve", "reject"]:
                return ReviewPostRESTResponse(
                    success=False,
                    message="",
                    error="Action must be 'approve' or 'reject'"
                )
            
            # Get reviewer email from query params if available
            reviewer_email = query_params.get("email")
            
            # Check for check_payment_only flag in request body
            check_payment_only = getattr(req, 'check_payment_only', None)
            
            result = await scheduler_service.review_schedule(
                review_token,
                req.action,
                req.comments,
                reviewer_email=reviewer_email,
                payment_completed=getattr(req, 'payment_completed', None),
                check_payment_only=check_payment_only,
                ctx=ctx
            )
            
            if result.get("error"):
                return ReviewPostRESTResponse(
                    success=False,
                    message="",
                    error=result.get("error")
                )
            else:
                return ReviewPostRESTResponse(
                    success=True,
                    message=result.get("message", "Review processed successfully"),
                    error=None,
                    schedule_id=result.get("schedule_id"),
                    payment_required=result.get("payment_required"),
                    payment_request=result.get("payment_request"),
                    scheduled_at=result.get("scheduled_at")
                )
        except Exception as e:
            import traceback
            return ReviewPostRESTResponse(
                success=False,
                message="",
                error=str(e)
            )
    
    @agent.on_rest_post("/linkedin/schedules/update", UpdateScheduleRESTRequest, CreateScheduleRESTResponse)
    async def handle_update_schedule_frontend(ctx: Context, req: UpdateScheduleRESTRequest) -> Dict[str, Any]:
        """Update/edit a scheduled post - Frontend version"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"message": "", "error": "Authentication required"}
            
            result = await scheduler_service.update_schedule(
                user_id,
                req.schedule_id,
                topic=req.topic,
                content=req.content,
                schedule=req.schedule,
                scheduled_at=req.scheduled_at,
                include_image=req.include_image,
                image_url=req.image_url
            )
            
            if result.get("error"):
                return {"message": "", "error": result.get("error")}
            
            return {
                "message": result.get("message", "Schedule updated successfully"),
                "schedule_id": req.schedule_id,
                "next_post_at": result.get("schedule", {}).get("scheduled_at") if result.get("schedule") else None,
                "error": None,
            }
        except Exception as e:
            return {"message": "", "error": str(e)}
    
    @agent.on_rest_post("/linkedin/review", ReviewPostRESTRequest, ReviewPostRESTResponse)
    async def handle_review_post(ctx: Context, req: ReviewPostRESTRequest) -> ReviewPostRESTResponse:
        """Review and approve/reject a scheduled post - PUBLIC ACCESS (no auth required)"""
        try:
            review_token = req.token or req.review_token
            if not review_token:
                return ReviewPostRESTResponse(
                    success=False,
                    message="",
                    error="Review token is required"
                )
            
            if req.action not in ["approve", "reject"]:
                return ReviewPostRESTResponse(
                    success=False,
                    message="",
                    error="Action must be 'approve' or 'reject'"
                )
            
            result = await scheduler_service.review_schedule(
                review_token,
                req.action,
                req.comments
            )
            
            if result.get("error"):
                return ReviewPostRESTResponse(
                    success=False,
                    message="",
                    error=result.get("error")
                )
            
            return ReviewPostRESTResponse(
                success=True,
                message=result.get("message", "Review processed successfully"),
                error=None
            )
        except Exception as e:
            return ReviewPostRESTResponse(
                success=False,
                message="",
                error=str(e)
            )
    
    @agent.on_rest_get("/linkedin/schedules/dates", GetScheduledDatesRESTResponse)
    async def handle_get_scheduled_dates(ctx: Context) -> Dict[str, Any]:
        """Get scheduled dates for a specific month"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"dates": [], "error": "Authentication required"}
            
            year = int(ctx.rest_params.get("year", 2024))
            month = int(ctx.rest_params.get("month", 1))
            
            result = await scheduler_service.get_scheduled_dates_for_month(user_id, year, month)
            return {
                "dates": result.get("dates", []),
                "error": result.get("error")
            }
        except Exception as e:
            return {"dates": [], "error": str(e)}
    
    @agent.on_rest_get("/linkedin/schedules/occurrences", GetOccurrencesForDateRESTResponse)
    async def handle_get_occurrences_for_date(ctx: Context) -> Dict[str, Any]:
        """Get all scheduled posts for a specific date"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"occurrences": [], "error": "Authentication required"}
            
            date_str = ctx.rest_params.get("date", "")
            if not date_str:
                return {"occurrences": [], "error": "Date parameter is required (YYYY-MM-DD)"}
            
            result = await scheduler_service.get_occurrences_for_date(user_id, date_str)
            return {
                "occurrences": result.get("occurrences", []),
                "error": result.get("error")
            }
        except Exception as e:
            return {"occurrences": [], "error": str(e)}
    
    @agent.on_rest_get("/linkedin/schedule/{schedule_id}/approval-status", GetApprovalStatusRESTResponse)
    async def handle_get_approval_status(ctx: Context) -> Dict[str, Any]:
        """Get approval status for a scheduled post"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"error": "Authentication required"}
            
            # Get schedule_id from path parameter
            schedule_id = ctx.rest_params.get("schedule_id")
            if not schedule_id:
                return {"error": "schedule_id is required"}
            
            result = await scheduler_service.get_approval_status(schedule_id)
            
            # Verify the schedule belongs to the user
            if not result.get("error"):
                import os
                from supabase import create_client
                supabase_url = os.getenv("SUPABASE_URL", "")
                supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "")
                if supabase_url and supabase_key:
                    supabase_admin = create_client(supabase_url, supabase_key)
                    verify_result = supabase_admin.table("scheduled_posts").select("user_id").eq("id", schedule_id).execute()
                    if verify_result.data and len(verify_result.data) > 0:
                        if verify_result.data[0].get("user_id") != user_id:
                            return {"error": "Unauthorized access to schedule"}
            
            return result
        except Exception as e:
            import traceback
            return {"error": str(e)}

