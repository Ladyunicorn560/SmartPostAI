"""Wallet REST handlers - Save/retrieve wallet data from Supabase"""
from typing import Dict, Any, Optional
from uagents import Context
from rest_models import (
    SaveWalletRESTRequest,
    SaveWalletRESTResponse,
    GetWalletRESTResponse,
    DeleteWalletRESTResponse,
    EmptyRequest,
)
from utils.auth import get_user_id_from_token
from cryptography.fernet import Fernet
import os
import base64

# Encryption key - should be in environment variable
ENCRYPTION_KEY = os.getenv("WALLET_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generate a key if not set (for development only)
    # In production, set WALLET_ENCRYPTION_KEY in environment
    ENCRYPTION_KEY = Fernet.generate_key().decode()

fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

def encrypt_wif(wif: str) -> str:
    """Encrypt WIF key"""
    try:
        encrypted = fernet.encrypt(wif.encode())
        return base64.b64encode(encrypted).decode()
    except Exception as e:
        raise Exception(f"Encryption failed: {str(e)}")

def decrypt_wif(encrypted_wif: str) -> str:
    """Decrypt WIF key"""
    try:
        encrypted_bytes = base64.b64decode(encrypted_wif.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        raise Exception(f"Decryption failed: {str(e)}")

def register_wallet_handlers(agent, supabase_client, supabase_admin=None):
    """Register wallet REST handlers"""
    
    @agent.on_rest_post("/api/wallet/save", SaveWalletRESTRequest, SaveWalletRESTResponse)
    async def handle_save_wallet(ctx: Context, req: SaveWalletRESTRequest) -> SaveWalletRESTResponse:
        """Save wallet address and encrypted WIF to Supabase"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return SaveWalletRESTResponse(success=False, error="Unauthorized")
            
            if not supabase_client:
                return SaveWalletRESTResponse(success=False, error="Database not configured")
            
            address = req.address
            wif = req.wif  # Optional
            
            if not address:
                return SaveWalletRESTResponse(success=False, error="Wallet address is required")
            
            # Validate address format
            import re
            if not re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
                return SaveWalletRESTResponse(success=False, error="Invalid wallet address format")
            
            # Encrypt WIF if provided
            encrypted_wif = None
            if wif:
                try:
                    encrypted_wif = encrypt_wif(wif)
                except Exception as e:
                    return SaveWalletRESTResponse(success=False, error=f"Failed to encrypt WIF: {str(e)}")
            
            # Use admin client to insert/update wallet data
            admin_client = supabase_admin if supabase_admin else supabase_client
            
            # Check if wallet already exists for this user
            existing = admin_client.table("user_wallets").select("*").eq("user_id", user_id).execute()
            
            wallet_data = {
                "user_id": user_id,
                "address": address,
                "encrypted_wif": encrypted_wif,
                "has_payment_capability": encrypted_wif is not None,
            }
            
            if existing.data and len(existing.data) > 0:
                # Update existing wallet
                result = admin_client.table("user_wallets").update(wallet_data).eq("user_id", user_id).execute()
            else:
                # Insert new wallet
                result = admin_client.table("user_wallets").insert(wallet_data).execute()
            
            return SaveWalletRESTResponse(
                success=True,
                message="Wallet saved successfully",
                address=address,
                has_payment_capability=encrypted_wif is not None
            )
        except Exception as e:
            return SaveWalletRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_get("/api/wallet/get", GetWalletRESTResponse)
    async def handle_get_wallet(ctx: Context) -> GetWalletRESTResponse:
        """Get wallet data from Supabase (returns address and decrypted WIF)"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return {"success": False, "error": "Unauthorized"}
            
            if not supabase_client:
                return {"success": False, "error": "Database not configured"}
            
            # Use admin client to get wallet data
            admin_client = supabase_admin if supabase_admin else supabase_client
            
            result = admin_client.table("user_wallets").select("*").eq("user_id", user_id).execute()
            
            if not result.data or len(result.data) == 0:
                return GetWalletRESTResponse(success=False, error="No wallet found")
            
            wallet = result.data[0]
            address = wallet.get("address")
            encrypted_wif = wallet.get("encrypted_wif")
            
            # Decrypt WIF if present
            wif = None
            if encrypted_wif:
                try:
                    wif = decrypt_wif(encrypted_wif)
                except Exception as e:
                    return GetWalletRESTResponse(success=False, error=f"Failed to decrypt WIF: {str(e)}")
            
            return GetWalletRESTResponse(
                success=True,
                address=address,
                wif=wif,  # Decrypted WIF
                has_payment_capability=wif is not None
            )
        except Exception as e:
            return GetWalletRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_post("/api/wallet/delete", EmptyRequest, DeleteWalletRESTResponse)
    async def handle_delete_wallet(ctx: Context, req: EmptyRequest) -> DeleteWalletRESTResponse:
        """Delete wallet data from Supabase"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return DeleteWalletRESTResponse(success=False, error="Unauthorized")
            
            if not supabase_client:
                return DeleteWalletRESTResponse(success=False, error="Database not configured")
            
            # Use admin client to delete wallet data
            admin_client = supabase_admin if supabase_admin else supabase_client
            
            result = admin_client.table("user_wallets").delete().eq("user_id", user_id).execute()
            
            return DeleteWalletRESTResponse(success=True, message="Wallet deleted successfully")
        except Exception as e:
            return DeleteWalletRESTResponse(success=False, error=str(e))
    
    @agent.on_rest_get("/api/wallet/recipient", GetWalletRESTResponse)
    async def handle_get_recipient_address(ctx: Context) -> GetWalletRESTResponse:
        """Get recipient address from user's connected wallet"""
        try:
            user_id = await get_user_id_from_token()
            if not user_id:
                return GetWalletRESTResponse(success=False, error="Unauthorized")
            
            if not supabase_client:
                return GetWalletRESTResponse(success=False, error="Database not configured")
            
            # Use admin client to get wallet data
            admin_client = supabase_admin if supabase_admin else supabase_client
            
            result = admin_client.table("user_wallets").select("address").eq("user_id", user_id).execute()
            
            if not result.data or len(result.data) == 0:
                return GetWalletRESTResponse(success=False, error="No wallet connected. Please connect your wallet first.")
            
            wallet = result.data[0]
            address = wallet.get("address")
            
            if not address:
                return GetWalletRESTResponse(success=False, error="Wallet address not found")
            
            return GetWalletRESTResponse(
                success=True,
                address=address,
                has_payment_capability=True
            )
        except Exception as e:
            return GetWalletRESTResponse(success=False, error=str(e))

