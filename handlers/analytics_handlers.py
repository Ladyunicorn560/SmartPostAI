"""Analytics REST handlers"""
from typing import Dict, Any, Optional
from uagents import Context
from datetime import datetime, timedelta, timezone
import time
from rest_models import AnalyticsRESTResponse
from utils.auth import _get_user_id_from_token

def register_analytics_handlers(agent, supabase_admin):
    """Register analytics-related REST handlers"""
    
    @agent.on_rest_get("/analytics", AnalyticsRESTResponse)
    async def handle_get_analytics(ctx: Context) -> Dict[str, Any]:
        """Get analytics data for user"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"error": "Authentication required"}
            
            # Get time range from query params
            query_params = getattr(ctx, '_request_query_params', {})
            if isinstance(query_params, dict):
                time_range = query_params.get("range", "30d")
            else:
                time_range = "30d"
            
            # Calculate date filter
            now = datetime.now(timezone.utc)
            if time_range == "7d":
                start_date = now - timedelta(days=7)
            elif time_range == "30d":
                start_date = now - timedelta(days=30)
            else:
                start_date = None
            
            # Get payments
            payment_query = supabase_admin.table("payments").select("*").eq("user_id", user_id)
            if start_date:
                payment_query = payment_query.gte("created_at", start_date.isoformat())
            payments_result = payment_query.order("created_at", desc=True).execute()
            
            payments = payments_result.data or []
            verified_payments = [p for p in payments if p.get("status") == "verified"]
            
            # Calculate totals
            total_spent = sum(float(p.get("amount", 0)) for p in verified_payments)
            total_earned = sum(float(p.get("amount", 0)) for p in payments if p.get("service") in ["tip", "commission"])
            
            # Get posts count
            posts_query = supabase_admin.table("generated_posts").select("id").eq("user_id", user_id)
            if start_date:
                posts_query = posts_query.gte("created_at", start_date.isoformat())
            posts_result = posts_query.execute()
            total_posts = len(posts_result.data or [])
            
            # Spending by service
            service_spending = {}
            service_counts = {}
            for payment in verified_payments:
                service = payment.get("service", "unknown")
                amount = float(payment.get("amount", 0))
                service_spending[service] = service_spending.get(service, 0) + amount
                service_counts[service] = service_counts.get(service, 0) + 1
            
            posts_by_service = [
                {
                    "service": service,
                    "count": service_counts[service],
                    "spent": service_spending[service]
                }
                for service in service_spending.keys()
            ]
            posts_by_service.sort(key=lambda x: x["spent"], reverse=True)
            
            # Engagement metrics (placeholder - would need LinkedIn API integration)
            engagement_rate = 5.2  # Placeholder
            avg_engagement = 150  # Placeholder
            
            # Recent payments (last 10)
            recent_payments = payments[:10]
            
            # Engagement trends (placeholder - would need LinkedIn API)
            engagement_trends = []
            
            return {
                "total_posts": total_posts,
                "total_spent": total_spent,
                "total_earned": total_earned,
                "engagement_rate": engagement_rate,
                "avg_engagement": avg_engagement,
                "posts_by_service": posts_by_service,
                "recent_payments": recent_payments,
                "engagement_trends": engagement_trends
            }
        except Exception as e:
            import traceback
            return {"error": str(e)}

