"""MNEE service REST handlers"""
from typing import Dict, Any
from uagents import Context
from rest_models import (
    BalanceRESTResponse,
    ConfigRESTResponse,
    SubmitRawTxRESTRequest,
    SubmitRawTxRESTResponse,
    TxStatusRESTResponse,
    TransferRESTRequest,
    TransferRESTResponse,
    TxExplorerRESTRequest,
    TxExplorerRESTResponse,
    UtxosRESTRequest,
    UtxosRESTResponse,
)
from utils.auth import _request_query_params, _request_headers
from utils.constants import MNEE_CONTRACT_ADDRESS

def register_mnee_handlers(agent, mnee_service):
    """Register MNEE-related REST handlers"""
    
    @agent.on_rest_get("/api/mnee/config", ConfigRESTResponse)
    async def handle_mnee_config(ctx: Context) -> ConfigRESTResponse:
        """Get MNEE config via backend"""
        try:
            result = await mnee_service.get_config()
            if result.get("success"):
                config = result.get("config")
                return ConfigRESTResponse(success=True, config=config)
            else:
                error_msg = result.get("error", "Failed to get config")
                return ConfigRESTResponse(success=False, error=error_msg)
        except Exception as e:
            return ConfigRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_get("/api/mnee/balance/address", BalanceRESTResponse)
    async def handle_mnee_balance_address(ctx: Context) -> BalanceRESTResponse:
        """Get MNEE balance for any address"""
        try:
            query_params = _request_query_params.get({})
            address = query_params.get('address')
            
            if not address:
                return BalanceRESTResponse(
                    success=False,
                    balance=0.0,
                    address="",
                    error="Address is required"
                )
            
            balance_result = await mnee_service.check_balance(address)
            return BalanceRESTResponse(
                success=balance_result.get("success", False),
                balance=float(balance_result.get("balance", 0)),
                address=address,
                error=balance_result.get("error"),
            )
        except Exception as e:
            query_params = _request_query_params.get({})
            return BalanceRESTResponse(
                success=False,
                balance=0.0,
                address=query_params.get('address', ''),
                error=str(e)
            )
    
    @agent.on_rest_post("/api/mnee/submit-rawtx", SubmitRawTxRESTRequest, SubmitRawTxRESTResponse)
    async def handle_submit_rawtx(ctx: Context, req: SubmitRawTxRESTRequest) -> SubmitRawTxRESTResponse:
        """Submit raw MNEE transaction"""
        try:
            result = await mnee_service.submit_rawtx(req.rawtx)
            
            if result.get("success"):
                ticket_id = result.get("ticketId")
                return SubmitRawTxRESTResponse(success=True, ticketId=ticket_id)
            else:
                error_msg = result.get("error", "Failed to submit transaction")
                error_code = result.get("error_code")
                retry_after = result.get("retry_after")
                
                # Log specific error types
                if error_code == "UTXO_LOCKED":
                    pass
                else:
                    pass
                
                return SubmitRawTxRESTResponse(success=False, error=error_msg)
        except Exception as e:
            return SubmitRawTxRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_get("/api/mnee/tx-status", TxStatusRESTResponse)
    async def handle_tx_status(ctx: Context) -> TxStatusRESTResponse:
        """Get MNEE transaction status with explorer links"""
        try:
            query_params = _request_query_params.get({})
            ticket_id = query_params.get('ticketId') or query_params.get('ticket_id')
            
            if not ticket_id:
                return TxStatusRESTResponse(success=False, error="ticketId is required")
            
            result = await mnee_service.get_tx_status(ticket_id)
            if result.get("success"):
                tx_id = result.get("tx_id")
                
                # Add explorer links if tx_id is available
                explorer_url = None
                if tx_id:
                    is_sandbox = mnee_service.environment == "sandbox"
                    if is_sandbox:
                        explorer_url = f"https://whatsonchain.com/tx/{tx_id}"
                    else:
                        explorer_url = f"https://whatsonchain.com/tx/{tx_id}"
                
                response_data = {
                    "success": True,
                    "status": result.get("status"),
                    "tx_id": tx_id,
                    "tx_hex": result.get("tx_hex"),
                    "errors": result.get("errors"),
                    "action_requested": result.get("action_requested"),
                    "createdAt": result.get("createdAt"),
                    "updatedAt": result.get("updatedAt"),
                }
                
                # Add explorer_url to response if available
                if explorer_url:
                    response_data["explorer_url"] = explorer_url
                    response_data["environment"] = mnee_service.environment
                
                return TxStatusRESTResponse(**response_data)
            else:
                return TxStatusRESTResponse(
                    success=False,
                    error=result.get("error", "Failed to get transaction status"),
                )
        except Exception as e:
            return TxStatusRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_post("/api/mnee/transfer", TransferRESTRequest, TransferRESTResponse)
    async def handle_mnee_transfer(ctx: Context, req: TransferRESTRequest) -> TransferRESTResponse:
        """Complete MNEE transfer via backend"""
        try:
            config_result = await mnee_service.get_config()
            if not config_result.get("success"):
                return TransferRESTResponse(
                    success=False,
                    error=f"Failed to get MNEE config: {config_result.get('error')}",
                )
            return TransferRESTResponse(
                success=False,
                error="Rawtx creation requires Bitcoin transaction building. Please use frontend SDK with backend config proxy.",
            )
        except Exception as e:
            return TransferRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_post("/api/mnee/tx-explorer", TxExplorerRESTRequest, TxExplorerRESTResponse)
    async def handle_tx_explorer(ctx: Context, req: TxExplorerRESTRequest) -> TxExplorerRESTResponse:
        """Get transaction explorer links with MNEE plugin (WOC)
        
        Returns WhatsonChain explorer links with MNEE plugin tab for easy transaction viewing.
        Uses ?tab=m8eqcrbs to automatically launch MNEE plugin.
        """
        try:
            if not req.tx_id:
                return TxExplorerRESTResponse(success=False, error="Transaction ID is required")
            
            is_sandbox = mnee_service.environment == "sandbox"
            tx_id = req.tx_id
            
            # WOC explorer URLs with MNEE plugin tab (?tab=m8eqcrbs)
            # Production: https://whatsonchain.com/tx/{txid}?tab=m8eqcrbs
            # Sandbox: https://test.whatsonchain.com/tx/{txid}?tab=m8eqcrbs
            if is_sandbox:
                explorer_url = f"https://test.whatsonchain.com/tx/{tx_id}"
                explorer_url_with_plugin = f"https://test.whatsonchain.com/tx/{tx_id}"
            else:
                explorer_url = f"https://whatsonchain.com/tx/{tx_id}"
                explorer_url_with_plugin = f"https://whatsonchain.com/tx/{tx_id}"
            
            return TxExplorerRESTResponse(
                success=True,
                tx_id=tx_id,
                explorer_url=explorer_url,
                explorer_url_with_plugin=explorer_url_with_plugin,
                environment=mnee_service.environment,
            )
        except Exception as e:
            return TxExplorerRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_get("/api/mnee/tx-explorer", TxExplorerRESTResponse)
    async def handle_tx_explorer_get(ctx: Context) -> TxExplorerRESTResponse:
        """Get transaction explorer links via GET (query parameter)"""
        try:
            query_params = _request_query_params.get({})
            tx_id = query_params.get('tx_id') or query_params.get('txId') or query_params.get('txid')
            
            if not tx_id:
                return TxExplorerRESTResponse(success=False, error="Transaction ID is required (query param: tx_id)")
            
            is_sandbox = mnee_service.environment == "sandbox"
            
            # WOC explorer URLs with MNEE plugin tab
            if is_sandbox:
                explorer_url = f"https://whatsonchain.com/tx/{tx_id}"
                explorer_url_with_plugin = f"https://whatsonchain.com/tx/{tx_id}"
            else:
                explorer_url = f"https://whatsonchain.com/tx/{tx_id}"
                explorer_url_with_plugin = f"https://whatsonchain.com/tx/{tx_id}"
            
            return TxExplorerRESTResponse(
                success=True,
                tx_id=tx_id,
                explorer_url=explorer_url,
                explorer_url_with_plugin=explorer_url_with_plugin,
                environment=mnee_service.environment,
            )
        except Exception as e:
            return TxExplorerRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_post("/api/mnee/utxos", UtxosRESTRequest, UtxosRESTResponse)
    async def handle_get_utxos(ctx: Context, req: UtxosRESTRequest) -> UtxosRESTResponse:
        """Get UTXOs for a list of addresses
        
        Returns unspent transaction outputs for the given addresses.
        Useful for wallet management and transaction building.
        """
        try:
            if not req.addresses or len(req.addresses) == 0:
                return UtxosRESTResponse(success=False, error="At least one address is required")
            
            result = await mnee_service.get_utxos(req.addresses)
            
            if result.get("success"):
                utxos = result.get("utxos", [])
                total_utxos = len(utxos)
                
                # Calculate total amount from UTXOs
                total_amount = 0
                for utxo in utxos:
                    bsv21_data = utxo.get("data", {}).get("bsv21", {})
                    if bsv21_data:
                        amount = bsv21_data.get("amt", 0)
                        decimals = bsv21_data.get("dec", 5)
                        # Convert atomic units to MNEE
                        total_amount += amount / (10 ** decimals)
                
                return UtxosRESTResponse(
                    success=True,
                    utxos=utxos,
                    total_utxos=total_utxos,
                    total_amount=str(total_amount),
                )
            else:
                return UtxosRESTResponse(success=False, error=result.get("error", "Failed to get UTXOs"))
        except Exception as e:
            return UtxosRESTResponse(success=False, error=str(e))

