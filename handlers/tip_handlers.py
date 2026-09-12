"""Tip Jar REST handlers"""
from typing import Dict, Any
from uagents import Context
import time
from rest_models import TipPostRESTRequest, TipPostRESTResponse
from utils.auth import _get_user_id_from_token

def register_tip_handlers(agent, payment_service, mnee_service, supabase_admin):
    """Register tip jar handlers"""
    
    @agent.on_rest_post("/api/posts/tip", TipPostRESTRequest, TipPostRESTResponse)
    async def handle_tip_post(ctx: Context, req: TipPostRESTRequest) -> Dict[str, Any]:
        """Tip a post creator with MNEE"""
        try:
            tipper_id = await _get_user_id_from_token(ctx)
            if not tipper_id:
                return {"success": False, "error": "Authentication required"}
            
            # Get post creator
            post_result = supabase_admin.table("generated_posts").select("user_id").eq("id", req.post_id).execute()
            if not post_result.data:
                return {"success": False, "error": "Post not found"}
            
            creator_id = post_result.data[0].get("user_id")
            if not creator_id:
                return {"success": False, "error": "Post creator not found"}
            
            # Compare user IDs (ensure both are strings for comparison)
            tipper_id_str = str(tipper_id).strip()
            creator_id_str = str(creator_id).strip()
            
            if tipper_id_str == creator_id_str:
                return {"success": False, "error": "Cannot tip your own post"}
            
            # Get tipper wallet
            tipper_wallet = supabase_admin.table("user_wallets").select("*").eq("user_id", tipper_id).limit(1).execute()
            if not tipper_wallet.data:
                return {"success": False, "error": "Wallet not found. Please connect your wallet first."}
            
            # Get creator wallet address
            creator_wallet = supabase_admin.table("user_wallets").select("address").eq("user_id", creator_id).limit(1).execute()
            if not creator_wallet.data:
                return {"success": False, "error": "Creator wallet not found"}
            
            creator_address = creator_wallet.data[0].get("address")
            
            # Record tip payment
            tip_payment = await payment_service.record_payment(
                user_id=tipper_id,
                tx_hash=f"tip_{req.post_id}_{int(time.time())}",  # Temporary hash
                service="tip",
                amount=str(req.amount),
                status="pending"
            )
            
            # Return payment request for frontend to process
            return {
                "success": True,
                "message": f"Tip of {req.amount} MNEE initiated",
                "payment_request": {
                    "recipient_address": creator_address,
                    "amount": req.amount,
                    "post_id": req.post_id,
                    "creator_id": creator_id
                }
            }
        except Exception as e:
            import traceback
            return {"success": False, "error": str(e)}

