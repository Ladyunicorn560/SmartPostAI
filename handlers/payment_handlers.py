"""Payment REST handlers"""
import re
from typing import Dict, Any
from uagents import Context
from rest_models import (
    VerifyPaymentRESTRequest,
    VerifyPaymentRESTResponse,
    PaymentStatusRESTResponse,
    DashboardAccessRESTResponse,
    PaymentHistoryRESTResponse,
    PaymentAnalyticsRESTResponse,
    PaymentReceiptRESTRequest,
    PaymentReceiptRESTResponse,
)
from utils.auth import get_user_id_from_token, _request_headers
from utils.constants import MNEE_CONTRACT_ADDRESS

def register_payment_handlers(agent, payment_service, mnee_service):
    """Register payment-related REST handlers"""
    
    @agent.on_rest_post("/api/payment/verify", VerifyPaymentRESTRequest, VerifyPaymentRESTResponse)
    async def handle_verify_payment(ctx: Context, req: VerifyPaymentRESTRequest) -> VerifyPaymentRESTResponse:
        """Verify MNEE payment transaction"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                user_id = req.user_id
            
            if not user_id:
                return VerifyPaymentRESTResponse(success=False, error="Authentication required")
            
            tx_id = req.txHash
            if not tx_id:
                return VerifyPaymentRESTResponse(success=False, error="Invalid transaction ID")
            
            result = await payment_service.verify_and_record_payment(user_id, tx_id, req.amount, req.service)
            
            if result.get("success"):
                
                is_sandbox = mnee_service.environment == "sandbox"
                explorer_url = None
                actual_tx_id = tx_id
                
                ticket_id_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
                tx_id_pattern = re.compile(r'^[0-9a-f]{64}$', re.IGNORECASE)
                
                if ticket_id_pattern.match(tx_id):
                    tx_status = await mnee_service.get_tx_status(tx_id)
                    if tx_status.get("success") and tx_status.get("tx_id"):
                        actual_tx_id = tx_status.get("tx_id")
                
                if actual_tx_id and tx_id_pattern.match(actual_tx_id):
                    tx_verify = await mnee_service.get_transaction(actual_tx_id)
                    if tx_verify.get("exists"):
                        if is_sandbox:
                            explorer_url = f"https://whatsonchain.com/tx/{actual_tx_id}"
                        else:
                            explorer_url = f"https://whatsonchain.com/tx/{actual_tx_id}"
                
                return VerifyPaymentRESTResponse(
                    success=True,
                    message=f"Payment verified successfully. Contract: {MNEE_CONTRACT_ADDRESS}",
                    tx_hash=actual_tx_id,
                    explorer_url=explorer_url
                )
            else:
                error_msg = result.get("error", "Payment verification failed")
                return VerifyPaymentRESTResponse(success=False, error=error_msg)
        except Exception as e:
            return VerifyPaymentRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_get("/api/payment/status", PaymentStatusRESTResponse)
    async def handle_payment_status(ctx: Context) -> PaymentStatusRESTResponse:
        """Check user's payment status"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return PaymentStatusRESTResponse(has_paid=False, error="Authentication required")
            
            result = await payment_service.check_user_payment_status(user_id)
            
            return PaymentStatusRESTResponse(
                has_paid=result.get("has_paid", False),
                payment_date=result.get("payment_date"),
                tx_hash=result.get("tx_hash"),
                amount=result.get("amount"),
                error=result.get("error"),
            )
        except Exception as e:
            return PaymentStatusRESTResponse(has_paid=False, error=str(e))
    
    @agent.on_rest_get("/api/dashboard/access", DashboardAccessRESTResponse)
    async def handle_dashboard_access(ctx: Context) -> DashboardAccessRESTResponse:
        """Check if user has access to dashboard - Payment disabled for hackathon"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return DashboardAccessRESTResponse(
                    has_access=False,
                    has_paid=False,
                    error="Authentication required"
                )
            
            # Payment disabled - always grant access
            return DashboardAccessRESTResponse(
                has_access=True,
                has_paid=True,
                message="Access granted - payment disabled",
            )
        except Exception as e:
            return DashboardAccessRESTResponse(
                has_access=False,
                has_paid=False,
                error=str(e)
            )
    
    @agent.on_rest_get("/api/payment/history", PaymentHistoryRESTResponse)
    async def handle_payment_history(ctx: Context) -> PaymentHistoryRESTResponse:
        """Get user's payment history with pagination"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return PaymentHistoryRESTResponse(success=False, error="Authentication required")
            
            # Get query parameters for pagination
            from utils.auth import _request_query_params
            query_params = _request_query_params.get({})
            limit = int(query_params.get("limit", "50"))
            offset = int(query_params.get("offset", "0"))
            
            
            result = await payment_service.get_payment_history(user_id, limit=limit, offset=offset)
            
            
            if result.get("success"):
                payments_list = result.get("payments", [])
                return PaymentHistoryRESTResponse(
                    success=True,
                    payments=payments_list,
                    total_count=result.get("total_count", 0),
                    total_spent=result.get("total_spent", "0"),
                )
            else:
                error_msg = result.get("error", "Failed to get payment history")
                return PaymentHistoryRESTResponse(success=False, error=error_msg)
        except Exception as e:
            import traceback
            return PaymentHistoryRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_get("/api/payment/analytics", PaymentAnalyticsRESTResponse)
    async def handle_payment_analytics(ctx: Context) -> PaymentAnalyticsRESTResponse:
        """Get payment analytics for user (total spent, service breakdown, etc.)"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return PaymentAnalyticsRESTResponse(success=False, error="Authentication required")
            
            result = await payment_service.get_payment_analytics(user_id)
            
            if result.get("success"):
                return PaymentAnalyticsRESTResponse(
                    success=True,
                    total_spent=result.get("total_spent", "0"),
                    total_transactions=result.get("total_transactions", 0),
                    service_breakdown=result.get("service_breakdown", {}),
                    recent_payments=result.get("recent_payments", []),
                )
            else:
                return PaymentAnalyticsRESTResponse(success=False, error=result.get("error", "Failed to get payment analytics"))
        except Exception as e:
            return PaymentAnalyticsRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_post("/api/payment/receipt", PaymentReceiptRESTRequest, PaymentReceiptRESTResponse)
    async def handle_payment_receipt(ctx: Context, req: PaymentReceiptRESTRequest) -> PaymentReceiptRESTResponse:
        """Get detailed payment receipt with transaction information"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return PaymentReceiptRESTResponse(success=False, error="Authentication required")
            
            if not req.tx_hash:
                return PaymentReceiptRESTResponse(success=False, error="Transaction hash required")
            
            result = await payment_service.get_payment_receipt(user_id, req.tx_hash)
            
            if result.get("success"):
                return PaymentReceiptRESTResponse(
                    success=True,
                    receipt=result.get("receipt"),
                )
            else:
                return PaymentReceiptRESTResponse(success=False, error=result.get("error", "Failed to get payment receipt"))
        except Exception as e:
            return PaymentReceiptRESTResponse(success=False, error=str(e))

