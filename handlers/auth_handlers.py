"""Authentication REST handlers"""
from typing import Dict, Any
from uagents import Context
from rest_models import LoginRequest, RegisterRequest, AuthResponse, UserProfileRESTResponse

def register_auth_handlers(agent, supabase_client, supabase_admin=None):
    """Register authentication REST handlers"""
    
    async def _handle_login_internal(ctx: Context, req: LoginRequest) -> Dict[str, Any]:
        """Internal login handler using Supabase Auth"""
        try:
            if not supabase_client:
                return {"success": False, "error": "Database not configured"}
            
            response = supabase_client.auth.sign_in_with_password({
                "email": req.email,
                "password": req.password
            })
            
            if response.user is None:
                return {"success": False, "error": "Invalid credentials"}
            
            user_data = {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name", ""),
            }
            
            token = response.session.access_token if response.session else None
            if not token:
                return {"success": False, "error": "Failed to generate token"}
            
            return {"success": True, "token": token, "accessToken": token, "user": user_data}
        except Exception as e:
            error_msg = str(e)
            if "Invalid login credentials" in error_msg or "Email not confirmed" in error_msg:
                return {"success": False, "error": "Invalid credentials"}
            return {"success": False, "error": error_msg}
    
    @agent.on_rest_post("/api/auth/login", LoginRequest, AuthResponse)
    async def handle_login(ctx: Context, req: LoginRequest) -> AuthResponse:
        """Handle user login - API version"""
        result = await _handle_login_internal(ctx, req)
        return AuthResponse(
            success=result.get("success", False),
            token=result.get("token"),
            user=result.get("user"),
            error=result.get("error")
        )
    
    @agent.on_rest_post("/auth/login", LoginRequest, AuthResponse)
    async def handle_login_frontend(ctx: Context, req: LoginRequest) -> Dict[str, Any]:
        """Handle user login - Frontend version"""
        return await _handle_login_internal(ctx, req)
    
    async def _handle_register_internal(ctx: Context, req: RegisterRequest) -> Dict[str, Any]:
        """Internal register handler using Supabase Auth"""
        try:
            if not supabase_client:
                return {"success": False, "error": "Database not configured"}
            
            # Try using admin client if available (bypasses some restrictions)
            client_to_use = supabase_admin if supabase_admin else supabase_client
            
            try:
                # Try signup - Supabase will handle user creation in auth.users
                # If there's a database trigger/function issue, it will fail here
                signup_options = {
                    "data": {"name": req.name}
                }
                
                # Use regular client for signup (admin client doesn't have sign_up method)
                response = supabase_client.auth.sign_up({
                    "email": req.email,
                    "password": req.password,
                    "options": signup_options
                })
            except Exception as signup_error:
                error_msg = str(signup_error)
                
                # Check for specific Supabase errors
                if "500" in error_msg or "Internal Server Error" in error_msg or "Database error" in error_msg:
                    return {
                        "success": False, 
                        "error": "Database error during registration. This might be due to a database trigger or function failing. Please check your Supabase dashboard or contact support."
                    }
                return {"success": False, "error": f"Registration failed: {error_msg}"}
            
            if hasattr(response, 'error') and response.error:
                error_msg = response.error.message if hasattr(response.error, 'message') else str(response.error)
                # Handle 500 errors from Supabase
                if "500" in error_msg or "Internal Server Error" in error_msg:
                    return {"success": False, "error": "Server error during registration. Please try again later."}
                return {"success": False, "error": error_msg}
            
            if response.user is None:
                error_msg = "User registration failed"
                if hasattr(response, 'message'):
                    error_msg = response.message
                return {"success": False, "error": error_msg}
            
            user_data = {
                "id": response.user.id,
                "email": response.user.email,
                "name": response.user.user_metadata.get("name", req.name),
            }
            
            token = None
            if response.session:
                token = response.session.access_token
            
            if not token:
                return {
                    "success": True,
                    "token": None,
                    "accessToken": None,
                    "user": user_data,
                    "message": "Account created! Please check your email to confirm your account before logging in."
                }
            
            return {"success": True, "token": token, "accessToken": token, "user": user_data}
        except Exception as e:
            error_msg = str(e)
            
            # Handle 500 Internal Server Error from Supabase
            if "500" in error_msg or "Internal Server Error" in error_msg or "Database error" in error_msg:
                return {"success": False, "error": "Server error during registration. Please check Supabase configuration or try again later."}
            
            if "User already registered" in error_msg or "already exists" in error_msg.lower():
                return {"success": False, "error": "An account with this email already exists"}
            
            if "Too Many Requests" in error_msg or "429" in error_msg:
                import re
                wait_match = re.search(r'after (\d+) seconds?', error_msg)
                if wait_match:
                    wait_time = wait_match.group(1)
                    return {"success": False, "error": f"Too many signup attempts. Please wait {wait_time} seconds and try again."}
                return {"success": False, "error": "Too many signup attempts. Please wait a moment and try again."}
            
            if "Invalid email" in error_msg or ("email" in error_msg.lower() and "invalid" in error_msg.lower()):
                return {"success": False, "error": "Please enter a valid email address"}
            
            if "password" in error_msg.lower() and ("weak" in error_msg.lower() or "short" in error_msg.lower()):
                return {"success": False, "error": "Password is too weak. Please use a stronger password."}
            
            return {"success": False, "error": error_msg}
    
    @agent.on_rest_post("/api/auth/register", RegisterRequest, AuthResponse)
    async def handle_register(ctx: Context, req: RegisterRequest) -> AuthResponse:
        """Handle user registration - API version"""
        result = await _handle_register_internal(ctx, req)
        return AuthResponse(
            success=result.get("success", False),
            token=result.get("token"),
            user=result.get("user"),
            error=result.get("error")
        )
    
    @agent.on_rest_post("/auth/signup", RegisterRequest, AuthResponse)
    async def handle_signup_frontend(ctx: Context, req: RegisterRequest) -> Dict[str, Any]:
        """Handle user signup - Frontend version"""
        return await _handle_register_internal(ctx, req)
    
    @agent.on_rest_get("/auth/me", UserProfileRESTResponse)
    async def handle_get_current_user(ctx: Context) -> UserProfileRESTResponse:
        """Get current user from JWT token"""
        try:
            from utils.auth import get_user_id_from_token
            
            user_id = await get_user_id_from_token()
            if not user_id:
                return {"success": False, "error": "Unauthorized"}
            
            if not supabase_client:
                return {"success": False, "error": "Database not configured"}
            
            # Get user from Supabase using admin client to get user by ID
            admin_client = supabase_admin if supabase_admin else supabase_client
            try:
                # Use admin client to get user by ID
                user_response = admin_client.auth.admin.get_user_by_id(user_id)
                if not user_response or not hasattr(user_response, 'user') or not user_response.user:
                    return {"success": False, "error": "User not found"}
                
                user = user_response.user
                user_data = {
                    "id": user.id,
                    "email": user.email,
                    "name": user.user_metadata.get("name", "") if user.user_metadata else "",
                    "picture": user.user_metadata.get("picture") if user.user_metadata else None,
                }
                
                return {"success": True, "user": user_data}
            except Exception as supabase_error:
                # Fallback: decode token to get basic info
                from utils.auth import _request_headers
                headers = _request_headers.get({})
                auth_header = headers.get('authorization') or headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    token = auth_header.replace('Bearer ', '').strip()
                    try:
                        import jwt
                        payload = jwt.decode(token, options={"verify_signature": False})
                        user_data = {
                            "id": payload.get('sub') or payload.get('user_id'),
                            "email": payload.get('email', ''),
                            "name": payload.get('name', '') or payload.get('user_metadata', {}).get('name', ''),
                            "picture": payload.get('picture') or payload.get('user_metadata', {}).get('picture'),
                        }
                        return {"success": True, "user": user_data}
                    except Exception:
                        pass
                return {"success": False, "error": "Failed to get user information"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @agent.on_rest_get("/api/auth/me", UserProfileRESTResponse)
    async def handle_get_current_user_api(ctx: Context) -> UserProfileRESTResponse:
        """Get current user - API version"""
        return await handle_get_current_user(ctx)