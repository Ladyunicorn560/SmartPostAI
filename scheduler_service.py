import os
import uuid
from typing import Dict, Optional
from datetime import datetime, timezone
import croniter
import aiohttp

class SchedulerService:
    def __init__(self, supabase_client=None, supabase_admin=None, ai_service=None, payment_service=None):
        self.supabase_client = supabase_client
        self.supabase_admin = supabase_admin
        self.ai_service = ai_service
        self.payment_service = payment_service

    def get_next_utc(self, cron: str) -> Optional[datetime]:
        """Safely parse cron and return next UTC Date"""
        try:
            now = datetime.now(timezone.utc)
            iter = croniter.croniter(cron, now)
            next_run = iter.get_next(datetime)
            # Ensure timezone-aware UTC datetime
            if next_run.tzinfo is None:
                next_run = next_run.replace(tzinfo=timezone.utc)
            return next_run
        except Exception as e:
            return None
    
    def get_next_occurrences(self, cron: str, count: int = 30) -> list:
        """Get next N occurrences from cron expression"""
        try:
            now = datetime.now(timezone.utc)
            iter = croniter.croniter(cron, now)
            occurrences = []
            for _ in range(count):
                next_run = iter.get_next(datetime)
                if next_run.tzinfo is None:
                    next_run = next_run.replace(tzinfo=timezone.utc)
                occurrences.append(next_run.isoformat())
            return occurrences
        except Exception as e:
            return []
    
    async def get_scheduled_dates_for_month(self, user_id: str, year: int, month: int) -> Dict:
        """Get scheduled dates for a specific month"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured", "dates": []}
        
        try:
            # Get all active schedules for user
            result = self.supabase_admin.table("scheduled_posts").select("*").eq("user_id", user_id).in_("status", ["pending", "scheduled"]).execute()
            
            schedules = result.data or []
            dates = set()
            
            for schedule in schedules:
                cron_expr = schedule.get("cron_expression")
                if not cron_expr:
                    continue
                
                # Get next 60 occurrences
                occurrences = self.get_next_occurrences(cron_expr, 60)
                
                for occ_iso in occurrences:
                    try:
                        occ_date = datetime.fromisoformat(occ_iso.replace('Z', '+00:00'))
                        if occ_date.year == year and occ_date.month == month:
                            date_str = f"{year}-{str(month).zfill(2)}-{str(occ_date.day).zfill(2)}"
                            dates.add(date_str)
                    except:
                        continue
            
            return {"dates": sorted(list(dates)), "error": None}
        except Exception as e:
            return {"error": str(e), "dates": []}
    
    async def get_occurrences_for_date(self, user_id: str, date_str: str) -> Dict:
        """Get all scheduled posts for a specific date"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured", "occurrences": []}
        
        try:
            # Parse date string (YYYY-MM-DD)
            target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            target_year = target_date.year
            target_month = target_date.month
            target_day = target_date.day
            
            # Get all active schedules for user
            result = self.supabase_admin.table("scheduled_posts").select("*").eq("user_id", user_id).in_("status", ["pending", "scheduled"]).execute()
            
            schedules = result.data or []
            occurrences = []
            
            for schedule in schedules:
                cron_expr = schedule.get("cron_expression")
                if not cron_expr:
                    continue
                
                # Get next 60 occurrences
                occ_list = self.get_next_occurrences(cron_expr, 60)
                
                for occ_iso in occ_list:
                    try:
                        occ_date = datetime.fromisoformat(occ_iso.replace('Z', '+00:00'))
                        if occ_date.year == target_year and occ_date.month == target_month and occ_date.day == target_day:
                            occurrences.append({
                                "schedule": schedule,
                                "date": occ_iso
                            })
                    except:
                        continue
            
            # Sort by date
            occurrences.sort(key=lambda x: x["date"])
            
            return {"occurrences": occurrences, "error": None}
        except Exception as e:
            return {"error": str(e), "occurrences": []}

    async def create_scheduled_post(
        self,
        user_id: str,
        topic: str,
        schedule: str,
        include_image: bool = False,
        custom_text: Optional[str] = None,
        image_url: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        require_approval: bool = False,
        team_emails: Optional[list] = None
    ) -> Dict:
        """Create a new scheduled post"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured"}
        
        # Determine scheduled time
        if scheduled_at:
            # One-time schedule from ISO datetime string
            try:
                next_post_at = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                if next_post_at.tzinfo is None:
                    next_post_at = next_post_at.replace(tzinfo=timezone.utc)
            except Exception as e:
                return {"error": f"Invalid scheduled_at format: {str(e)}"}
        elif schedule:
            # Cron expression
            next_post_at = self.get_next_utc(schedule)
            if not next_post_at:
                return {"error": "Invalid cron expression format"}
        else:
            return {"error": "Either schedule (cron) or scheduled_at (ISO datetime) is required"}
        
        try:
            # Check for duplicate: same user_id, topic/content, and cron_expression (only for recurring schedules)
            content = custom_text or topic
            existing = None
            if schedule:
                # For recurring schedules, check duplicates
                existing = self.supabase_admin.table("scheduled_posts").select("*").eq("user_id", user_id).eq("content", content).eq("cron_expression", schedule).eq("status", "pending").execute()
            
            if existing and existing.data and len(existing.data) > 0:
                return {
                    "message": "Schedule already exists",
                    "schedule_id": existing.data[0]["id"],
                    "next_post_at": existing.data[0].get("scheduled_at"),
                    "error": None,
                }
            # For one-time schedules (scheduled_at), don't check duplicates - allow multiple
            
            scheduled_post = {
                "user_id": user_id,
                "platform": "linkedin",
                "content": content,
                "scheduled_at": next_post_at.isoformat(),
                "status": "pending",
            }
            
            # Add cron_expression only if schedule is provided (not for one-time schedules)
            if schedule:
                scheduled_post["cron_expression"] = schedule
            
            # Add review token if approval required
            review_token = None
            if require_approval:
                review_token = str(uuid.uuid4())
                scheduled_post["review_token"] = review_token
                scheduled_post["status"] = "pending_approval"
                # Store team emails if provided
                if team_emails:
                    scheduled_post["team_emails"] = team_emails
            
            # Handle image URL: use provided image_url, or marker for generation on execution
            if image_url:
                # Use the provided image URL (generated upfront)
                scheduled_post["image_url"] = image_url
            elif include_image:
                # Set marker to generate image on execution
                scheduled_post["image_url"] = "__GENERATE_ON_EXECUTION__"
            # If False, leave image_url as None
            
            
            # Try to insert, but handle missing columns gracefully
            try:
                result = self.supabase_admin.table("scheduled_posts").insert(scheduled_post).execute()
            except Exception as insert_error:
                # Handle missing columns (review_token, team_emails)
                error_str = str(insert_error)
                scheduled_post_clean = scheduled_post.copy()
                columns_removed = []
                
                # Remove review_token if column doesn't exist
                if "review_token" in error_str and "review_token" in scheduled_post_clean:
                    scheduled_post_clean.pop("review_token", None)
                    columns_removed.append("review_token")
                    review_token = None
                
                # Remove team_emails if column doesn't exist
                if ("team_emails" in error_str or "team_emails" in str(insert_error)) and "team_emails" in scheduled_post_clean:
                    scheduled_post_clean.pop("team_emails", None)
                    columns_removed.append("team_emails")
                
                # If status was pending_approval and review_token removed, change to pending
                if "review_token" in columns_removed and scheduled_post_clean.get("status") == "pending_approval":
                    scheduled_post_clean["status"] = "pending"
                
                if columns_removed:
                    result = self.supabase_admin.table("scheduled_posts").insert(scheduled_post_clean).execute()
                else:
                    raise
            
            if result.data and len(result.data) > 0:
                schedule_id = result.data[0]["id"]
                
                response = {
                    "message": "Scheduled post created successfully",
                    "schedule_id": schedule_id,
                    "next_post_at": next_post_at.isoformat(),
                }
                
                # Add review link if approval required and review_token exists
                if require_approval and review_token:
                    # Generate review link (frontend URL + token)
                    base_url = os.getenv("FRONTEND_URL", "")
                    if not base_url:
                        raise ValueError("FRONTEND_URL environment variable is required")
                    review_link = f"{base_url}/review/{review_token}"
                    response["review_link"] = review_link
                    response["review_token"] = review_token
                    response["team_emails"] = team_emails or []
                elif require_approval:
                    # Still generate review link using schedule_id as fallback
                    base_url = os.getenv("FRONTEND_URL", "")
                    if not base_url:
                        raise ValueError("FRONTEND_URL environment variable is required")
                    review_link = f"{base_url}/review/{schedule_id}"
                    response["review_link"] = review_link
                    response["team_emails"] = team_emails or []
                    
                    # Send Slack notification if connected
                    try:
                        from slack_service import SlackService
                        slack_service = SlackService(self.supabase_client, self.supabase_admin)
                        await slack_service.send_notification(
                            user_id=user_id,
                            text=f"📅 New scheduled post created!\nReview Link: {review_link}",
                            team_id=None
                        )
                    except Exception:
                        pass  # Slack notification is optional
                
                return response
            return {"error": "Failed to create scheduled post: No data returned from insert"}
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return {"error": f"Failed to create scheduled post: {str(e)}\n{error_details}"}

    async def get_scheduled_posts(self, user_id: str) -> Dict:
        """Get all scheduled posts for a user"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured"}
        
        try:
            result = self.supabase_admin.table("scheduled_posts").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            
            return {"schedules": result.data or []}
        except Exception as e:
            return {"error": f"Failed to get scheduled posts: {str(e)}"}

    async def activate_schedule(self, user_id: str, schedule_id: str) -> Dict:
        """Activate a schedule"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured"}
        
        try:
            # Get schedule to validate cron (use admin for select to bypass RLS)
            schedule_result = self.supabase_admin.table("scheduled_posts").select("*").eq("id", schedule_id).eq("user_id", user_id).execute()
            
            if not schedule_result.data:
                return {"error": "Schedule not found"}
            
            schedule = schedule_result.data[0]
            cron_expr = schedule.get("cron_expression")
            
            if not cron_expr:
                return {"error": "Invalid cron expression"}
            
            next_post_at = self.get_next_utc(cron_expr)
            if not next_post_at:
                return {"error": "Invalid cron expression"}
            
            result = self.supabase_admin.table("scheduled_posts").update({
                "status": "pending",
                "scheduled_at": next_post_at.isoformat(),
            }).eq("id", schedule_id).eq("user_id", user_id).execute()
            
            if not result.data:
                return {"error": "Schedule not found"}
            
            return {"message": "Schedule activated successfully"}
        except Exception as e:
            return {"error": f"Failed to activate schedule: {str(e)}"}

    async def deactivate_schedule(self, user_id: str, schedule_id: str) -> Dict:
        """Deactivate a schedule"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured"}
        
        try:
            result = self.supabase_admin.table("scheduled_posts").update({
                "status": "cancelled"
            }).eq("id", schedule_id).eq("user_id", user_id).execute()
            
            if not result.data:
                return {"error": "Schedule not found"}
            
            return {"message": "Schedule deactivated successfully"}
        except Exception as e:
            return {"error": f"Failed to deactivate schedule: {str(e)}"}

    async def delete_schedule(self, user_id: str, schedule_id: str) -> Dict:
        """Delete a schedule"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured"}
        
        try:
            result = self.supabase_admin.table("scheduled_posts").delete().eq("id", schedule_id).eq("user_id", user_id).execute()
            
            if not result.data:
                return {"error": "Schedule not found"}
            
            return {"message": "Schedule deleted successfully"}
        except Exception as e:
            return {"error": f"Failed to delete schedule: {str(e)}"}
    
    async def update_schedule(
        self,
        user_id: str,
        schedule_id: str,
        topic: Optional[str] = None,
        content: Optional[str] = None,
        schedule: Optional[str] = None,
        scheduled_at: Optional[str] = None,
        include_image: Optional[bool] = None,
        image_url: Optional[str] = None
    ) -> Dict:
        """Update/edit a scheduled post"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured"}
        
        try:
            # Get existing schedule
            existing = self.supabase_admin.table("scheduled_posts").select("*").eq("id", schedule_id).eq("user_id", user_id).execute()
            
            if not existing.data:
                return {"error": "Schedule not found"}
            
            update_data = {}
            
            # Update content/topic
            if topic or content:
                update_data["content"] = content or topic
            
            # Update schedule time
            if scheduled_at:
                try:
                    next_post_at = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                    if next_post_at.tzinfo is None:
                        next_post_at = next_post_at.replace(tzinfo=timezone.utc)
                    update_data["scheduled_at"] = next_post_at.isoformat()
                except Exception as e:
                    return {"error": f"Invalid scheduled_at format: {str(e)}"}
            elif schedule:
                next_post_at = self.get_next_utc(schedule)
                if not next_post_at:
                    return {"error": "Invalid cron expression format"}
                update_data["cron_expression"] = schedule
                update_data["scheduled_at"] = next_post_at.isoformat()
            
            # Update image
            if include_image is not None:
                if include_image and image_url:
                    update_data["image_url"] = image_url
                elif include_image:
                    update_data["image_url"] = "__GENERATE_ON_EXECUTION__"
                else:
                    update_data["image_url"] = None
            
            if not update_data:
                return {"error": "No fields to update"}
            
            result = self.supabase_admin.table("scheduled_posts").update(update_data).eq("id", schedule_id).eq("user_id", user_id).execute()
            
            if not result.data:
                return {"error": "Schedule not found"}
            
            return {"message": "Schedule updated successfully", "schedule": result.data[0]}
        except Exception as e:
            return {"error": f"Failed to update schedule: {str(e)}"}
    
    async def verify_review_email(self, review_token: str, email: str) -> Dict:
        """Verify team member email for review access"""
        if not self.supabase_admin:
            return {"verified": False, "error": "Supabase admin client not configured"}
        
        try:
            schedule = None
            
            # Find schedule by review_token or schedule_id
            try:
                result = self.supabase_admin.table("scheduled_posts").select("*").eq("review_token", review_token).execute()
                if result.data and len(result.data) > 0:
                    schedule = result.data[0]
            except:
                pass
            
            if not schedule:
                try:
                    result = self.supabase_admin.table("scheduled_posts").select("*").eq("id", review_token).execute()
                    if result.data and len(result.data) > 0:
                        schedule = result.data[0]
                except Exception as e:
                    pass
            
            if not schedule:
                return {"verified": False, "error": "Schedule not found"}
            
            # Get team_emails from schedule
            team_emails = schedule.get("team_emails")
            if not team_emails:
                # If no team_emails, allow access (backward compatibility)
                return {
                    "verified": True,
                    "schedule_id": schedule["id"]
                }
            
            # Check if email is in team_emails list
            if isinstance(team_emails, list):
                email_lower = email.lower().strip()
                team_emails_lower = [e.lower().strip() if isinstance(e, str) else str(e).lower().strip() for e in team_emails]
                
                if email_lower in team_emails_lower:
                    return {
                        "verified": True,
                        "schedule_id": schedule["id"]
                    }
                else:
                    return {
                        "verified": False,
                        "error": f"Email '{email}' is not authorized to review this post. Authorized emails: {', '.join(team_emails)}"
                    }
            else:
                # Handle case where team_emails is stored as string or other format
                team_emails_str = str(team_emails).lower()
                if email.lower().strip() in team_emails_str:
                    return {
                        "verified": True,
                        "schedule_id": schedule["id"]
                    }
                else:
                    return {
                        "verified": False,
                        "error": f"Email '{email}' is not authorized to review this post."
                    }
                    
        except Exception as e:
            import traceback
            return {"verified": False, "error": f"Failed to verify email: {str(e)}"}
    
    async def get_schedule_for_review(self, review_token: str, email: Optional[str] = None) -> Dict:
        """Get scheduled post for review (public access, no auth required)"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured"}
        
        try:
            result = None
            schedule = None
            
            # Strategy 1: Try to find by review_token column (if it exists)
            try:
                result = self.supabase_admin.table("scheduled_posts").select("*").eq("review_token", review_token).execute()
                if result.data and len(result.data) > 0:
                    schedule = result.data[0]
            except Exception as e:
                pass
            
            # Strategy 2: Try using schedule_id as token (fallback)
            if not schedule:
                try:
                    result = self.supabase_admin.table("scheduled_posts").select("*").eq("id", review_token).execute()
                    if result.data and len(result.data) > 0:
                        schedule = result.data[0]
                except Exception as e:
                    import traceback
                    pass
            
            if not schedule:
                return {"error": "Schedule not found. The review link may be invalid or the post may have already been processed."}
            
            
            # Check if email verification is required
            team_emails = schedule.get("team_emails")
            requires_email_verification = bool(team_emails and len(team_emails) > 0)
            
            # If email verification is required, verify email
            if requires_email_verification:
                if not email:
                    # Return schedule info but indicate email verification is required
                    return {
                        "schedule_id": schedule["id"],
                        "requires_email_verification": True,
                        "team_emails": team_emails if isinstance(team_emails, list) else [],
                        "error": "Email verification required"
                    }
                
                # Verify email
                email_lower = email.lower().strip()
                if isinstance(team_emails, list):
                    team_emails_lower = [e.lower().strip() if isinstance(e, str) else str(e).lower().strip() for e in team_emails]
                    if email_lower not in team_emails_lower:
                        return {
                            "error": f"Email '{email}' is not authorized to review this post. Authorized emails: {', '.join(team_emails)}",
                            "requires_email_verification": True,
                            "team_emails": team_emails
                        }
                else:
                    team_emails_str = str(team_emails).lower()
                    if email.lower().strip() not in team_emails_str:
                        return {
                            "error": f"Email '{email}' is not authorized to review this post.",
                            "requires_email_verification": True
                        }
            
            # Check if status allows review
            status = schedule.get("status")
            if status not in ["pending_approval", "pending"]:
                return {
                    "schedule_id": schedule["id"],
                    "topic": schedule.get("topic", ""),
                    "content": schedule.get("content", ""),
                    "image_url": schedule.get("image_url"),
                    "scheduled_at": schedule.get("scheduled_at"),
                    "status": schedule.get("status"),
                    "platform": schedule.get("platform", "linkedin"),
                    "error": f"Schedule status is '{status}'. Only 'pending' or 'pending_approval' posts can be reviewed.",
                }
            
            # Return schedule data
            return {
                "schedule_id": schedule["id"],
                "topic": schedule.get("topic", ""),
                "content": schedule.get("content", ""),
                "image_url": schedule.get("image_url"),
                "scheduled_at": schedule.get("scheduled_at"),
                "status": schedule.get("status"),
                "platform": schedule.get("platform", "linkedin"),
                "team_emails": team_emails if isinstance(team_emails, list) else [],
                "requires_email_verification": requires_email_verification,
                "review_comments": schedule.get("review_comments")  # Include review comments
            }
            
        except Exception as e:
            import traceback
            return {"error": f"Failed to get schedule: {str(e)}"}
    
    async def review_schedule(self, review_token: str, action: str, comments: Optional[str] = None, reviewer_email: Optional[str] = None, payment_completed: Optional[bool] = None, check_payment_only: Optional[bool] = None, ctx=None) -> Dict:
        """Review and approve/reject a scheduled post (public access, no auth required)"""
        if not self.supabase_admin:
            return {"error": "Supabase admin client not configured"}
        
        try:
            # Try to find by review_token first, then fallback to schedule_id
            result = None
            schedule_id = None
            
            # Try review_token column first (without status filter)
            try:
                result = self.supabase_admin.table("scheduled_posts").select("*").eq("review_token", review_token).execute()
                if result.data and len(result.data) > 0:
                    schedule = result.data[0]
                    # Only allow if status is pending_approval or pending
                    if schedule.get("status") not in ["pending_approval", "pending"]:
                        return {"error": f"Schedule found but status is '{schedule.get('status')}'. Only 'pending' or 'pending_approval' posts can be reviewed."}
            except Exception as e:
                result = None
            
            # If not found or column doesn't exist, try with schedule_id (fallback)
            if not result or not result.data or len(result.data) == 0:
                try:
                    result = self.supabase_admin.table("scheduled_posts").select("*").eq("id", review_token).execute()
                    if result.data and len(result.data) > 0:
                        schedule = result.data[0]
                        # Only allow if status is pending_approval or pending
                        if schedule.get("status") not in ["pending_approval", "pending"]:
                            return {"error": f"Schedule found but status is '{schedule.get('status')}'. Only 'pending' or 'pending_approval' posts can be reviewed."}
                except Exception as e:
                    pass
            
            if not result or not result.data or len(result.data) == 0:
                return {"error": "Review token not found or already processed"}
            
            schedule = result.data[0]
            schedule_id = schedule["id"]
            team_emails = schedule.get("team_emails", [])
            approved_emails = schedule.get("approved_emails", []) or []
            
            if not isinstance(approved_emails, list):
                approved_emails = []
            
            if action == "approve":
                # Payment check removed - payment is done before scheduling
                # No need to check payment here
                
                # Track approval by email if reviewer_email provided
                if reviewer_email and team_emails:
                    reviewer_email_lower = reviewer_email.lower().strip()
                    if reviewer_email_lower not in [e.lower().strip() for e in approved_emails]:
                        approved_emails.append(reviewer_email)
                
                # Check if all team members have approved
                all_approved = False
                if team_emails and isinstance(team_emails, list):
                    team_emails_lower = [e.lower().strip() if isinstance(e, str) else str(e).lower().strip() for e in team_emails]
                    approved_emails_lower = [e.lower().strip() if isinstance(e, str) else str(e).lower().strip() for e in approved_emails]
                    all_approved = len(team_emails_lower) > 0 and all(email in approved_emails_lower for email in team_emails_lower)
                
                # Update status and approvals
                update_data = {
                    "status": "pending" if not all_approved else "pending",
                    "approved_emails": approved_emails
                }
                if comments:
                    update_data["review_comments"] = comments
                    update_data["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                
                self.supabase_admin.table("scheduled_posts").update(update_data).eq("id", schedule_id).execute()
                
                # Payment is done before scheduling, no need to check here
                
                # If all team members approved, update status to pending (payment already done before scheduling)
                if all_approved and team_emails:
                    # Payment was already done before scheduling, so just update status
                    update_data["status"] = "pending"
                    self.supabase_admin.table("scheduled_posts").update(update_data).eq("id", schedule_id).execute()
                    
                    return {
                        "success": True,
                        "message": f"Post approved by all team members. Will be posted at scheduled time.",
                        "schedule_id": schedule_id,
                        "scheduled_at": schedule.get("scheduled_at")
                    }
                
                return {
                    "success": True,
                    "message": f"Post approved ({len(approved_emails)}/{len(team_emails) if team_emails else 1} approvals)" if team_emails else "Post approved and scheduled",
                    "schedule_id": schedule_id,
                    "approvals_count": len(approved_emails),
                    "total_required": len(team_emails) if team_emails else 1
                }
            elif action == "reject":
                # Change status to rejected
                update_data = {"status": "rejected"}
                if comments:
                    update_data["review_comments"] = comments
                    update_data["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                
                self.supabase_admin.table("scheduled_posts").update(update_data).eq("id", schedule_id).execute()
                return {
                    "success": True,
                    "message": "Post rejected",
                    "schedule_id": schedule_id
                }
            else:
                return {"error": "Invalid action. Use 'approve' or 'reject'"}
        except Exception as e:
            import traceback
            return {"error": f"Failed to review schedule: {str(e)}"}
    
    # Removed _process_auto_payment and _record_pending_payment - payment is done before scheduling
    
    async def _check_payment(self, user_id: str, service: str = "linkedin_post") -> Dict:
        """Check if user has valid payment for posting"""
        # Free mode: always allow
        return {"has_payment": True}
    
    async def _post_approved_schedule(self, schedule: Dict, ctx=None) -> None:
        """Post a schedule immediately after all approvals"""
        try:
            user_id = schedule["user_id"]
            content = schedule.get("content", "")
            saved_image_url = schedule.get("image_url")
            schedule_id = schedule.get("id")
            
            # Free mode: no payment check
            
            # Get LinkedIn connection
            linkedin_result = self.supabase_admin.table("linkedin_connections").select("*").eq("user_id", user_id).execute()
            
            if not linkedin_result.data or len(linkedin_result.data) == 0:
                raise Exception("LinkedIn connection not found")
            
            connection = linkedin_result.data[0]
            access_token = connection.get("access_token")
            
            if not access_token:
                raise Exception("LinkedIn access token not found")
            
            # LinkedIn posts are stored in markdown format
            # Convert to LinkedIn-compatible format only when posting
            from utils.markdown_converter import markdown_to_linkedin
            linkedin_content = markdown_to_linkedin(content)
            
            # Post to LinkedIn
            from linkedin_service import LinkedInService
            linkedin_service = LinkedInService(self.supabase_client, self.supabase_admin)
            
            include_image = False
            if saved_image_url and saved_image_url.startswith("http") and saved_image_url != "__GENERATE_ON_EXECUTION__":
                include_image = True
            
            if include_image:
                result = await linkedin_service.post_with_image(
                    user_id,
                    linkedin_content,
                    saved_image_url
                )
            else:
                result = await linkedin_service.post_text(user_id, linkedin_content)
            
            if result.get("error"):
                raise Exception(f"LinkedIn post failed: {result.get('error')}")
            
            post_id = result.get("post_id")
            post_url = result.get("post_url")
            
            
            # Update schedule status to posted with post URL
            update_data = {
                "status": "posted",
                "post_id": post_id,
                "post_url": post_url,  # Store post URL
                "posted_at": datetime.now(timezone.utc).isoformat()
            }
            
            self.supabase_admin.table("scheduled_posts").update(update_data).eq("id", schedule_id).execute()
            
        except Exception as e:
            import traceback
            raise

    async def handle_scheduled_posts(self, ctx=None) -> None:
        """Check and execute due scheduled posts (should be called periodically)"""
        if not self.supabase_admin or not self.ai_service:
            return
        
        try:
            now_utc = datetime.now(timezone.utc)
            # Get active schedules that are due (use admin to bypass RLS)
            result = self.supabase_admin.table("scheduled_posts").select("*").eq("status", "pending").lte("scheduled_at", now_utc.isoformat()).execute()
            
            active_schedules = result.data or []
            
            for schedule in active_schedules:
                try:
                    user_id = schedule["user_id"]
                    topic = schedule.get("content", "")  # Topic/content from user
                    saved_image_url = schedule.get("image_url")  # Saved image URL if any
                    schedule_id = schedule.get("id")
                    
                    
                    # Check if image was requested
                    include_image = False
                    needs_image_generation = False
                    
                    if saved_image_url == "__GENERATE_ON_EXECUTION__":
                        include_image = True
                        needs_image_generation = True
                        saved_image_url = None  # Clear the marker
                    elif saved_image_url and saved_image_url.startswith("http"):
                        include_image = True
                        needs_image_generation = False
                    
                    # Free mode: no payment check before posting
                    
                    linkedin_result = self.supabase_admin.table("linkedin_connections").select("*").eq("user_id", user_id).execute()
                    
                    if not linkedin_result.data:
                        continue
                    
                    connection = linkedin_result.data[0]
                    access_token = connection.get("access_token")
                    
                    if not access_token:
                        continue
                    
                    # Step 1: Use existing content if available, otherwise generate from topic
                    # If content is already stored (from AI generation), use it directly
                    # Otherwise, generate new content from topic
                    if topic and len(topic) > 200:  # If topic is actually full content
                        # Content is already stored in topic field
                        full_text = topic
                    else:
                        # Generate LinkedIn post content from topic
                        post_result = await self.ai_service.generate_linkedin_post(topic, include_hashtags=True, language="en")
                        
                        if "error" in post_result:
                            self.supabase_admin.table("scheduled_posts").update({
                                "status": "failed",
                                "error_message": f"Post content generation failed: {post_result.get('error')}"
                            }).eq("id", schedule_id).execute()
                            continue
                        
                        full_text = post_result.get("text", topic)
                        hashtags = post_result.get("hashtags", [])
                        if hashtags:
                            full_text += "\n\n" + " ".join(hashtags)
                    
                    # Convert markdown to LinkedIn-friendly format (always convert before posting)
                    from utils.markdown_converter import markdown_to_linkedin
                    full_text = markdown_to_linkedin(full_text)
                    
                    
                    # Step 2: Generate image from the generated post content (not topic)
                    image_url = None
                    if include_image and needs_image_generation:
                        # Generate image prompt from the post content (use first 500 chars)
                        image_prompt = await self.ai_service.generate_image_prompt(full_text[:500])
                        # Generate image with context for immediate response
                        image_url = await self.ai_service.generate_image(image_prompt, topic=full_text[:200], ctx=ctx)
                        
                        if image_url:
                            pass
                    elif include_image and saved_image_url:
                        # Use saved image URL
                        image_url = saved_image_url
                    
                    
                    # Post to LinkedIn - use admin client for LinkedInService
                    from linkedin_service import LinkedInService
                    linkedin_service = LinkedInService(self.supabase_client, self.supabase_admin)
                    
                    # Post with or without image
                    if include_image and image_url:
                        result = await linkedin_service.post_with_image(
                            user_id,
                            full_text,
                            image_url=image_url
                        )
                    else:
                        result = await linkedin_service.post_text(user_id, full_text)
                    
                    if "error" in result:
                        self.supabase_admin.table("scheduled_posts").update({
                            "status": "failed",
                            "error_message": result["error"]
                        }).eq("id", schedule_id).execute()
                    else:
                        post_id = result.get("post_id")
                        post_url = result.get("post_url") or result.get("url")
                        
                        cron_expr = schedule.get("cron_expression")
                        update_data = {
                            "posted_at": now_utc.isoformat(),
                            "post_id": post_id,
                        }
                        
                        # Store post_url in scheduled_posts table
                        if post_url:
                            update_data["post_url"] = post_url
                        
                        if cron_expr:
                            next_post_at = self.get_next_utc(cron_expr)
                            if next_post_at:
                                update_data["status"] = "pending"
                                update_data["scheduled_at"] = next_post_at.isoformat()
                            else:
                                update_data["status"] = "posted"
                        else:
                            update_data["status"] = "posted"
                        
                        self.supabase_admin.table("scheduled_posts").update(update_data).eq("id", schedule_id).execute()
                except Exception as e:
                    import traceback
                    try:
                        self.supabase_admin.table("scheduled_posts").update({
                            "status": "failed",
                            "error_message": str(e)
                        }).eq("id", schedule.get("id")).execute()
                    except:
                        pass
        except Exception:
            pass
