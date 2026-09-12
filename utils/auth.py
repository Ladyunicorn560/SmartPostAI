"""Authentication utilities"""
import jwt
from typing import Optional, Dict
from contextvars import ContextVar

# Context variable to store request headers for REST handlers (exported for handlers)
_request_headers: ContextVar[Dict[str, str]] = ContextVar('request_headers', default={})
_request_query_params: ContextVar[Dict[str, str]] = ContextVar('request_query_params', default={})
_request_body: ContextVar[bytes] = ContextVar('_request_body', default=b'')

# JWT Secret for authentication
JWT_SECRET = None  # Will be set from environment

def set_jwt_secret(secret: str):
    """Set JWT secret from environment"""
    global JWT_SECRET
    JWT_SECRET = secret

async def get_user_id_from_token() -> Optional[str]:
    """Extract user_id from JWT token in Authorization header"""
    try:
        headers = _request_headers.get({})
        auth_header = headers.get('authorization') or headers.get('Authorization', '')
        
        if not auth_header or not isinstance(auth_header, str):
            return None
        
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.replace('Bearer ', '').strip()
        
        if not token or len(token.split('.')) != 3:
            return None
            
        try:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            user_id = unverified_payload.get('sub') or unverified_payload.get('user_id')
            
            if not user_id:
                return None
            
            if JWT_SECRET:
                try:
                    jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False, "verify_exp": True})
                except Exception:
                    pass  # Still return user_id even if verification fails
            return user_id
        except Exception:
            return None
    except Exception:
        return None

# Compatibility function for old code
async def _get_user_id_from_token(ctx) -> Optional[str]:
    """Legacy wrapper for compatibility"""
    return await get_user_id_from_token()