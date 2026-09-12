import os
import aiohttp
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone
import base64
from dotenv import load_dotenv
load_dotenv()

LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "")
LINKEDIN_SCOPE = os.getenv("LINKEDIN_SCOPE", "openid profile email w_member_social")

class LinkedInService:
    def __init__(self, supabase_client=None, supabase_admin=None):
        self.supabase_client = supabase_client  # For reads (with user context if needed)
        self.supabase_admin = supabase_admin or supabase_client  # For writes (bypasses RLS)
        self.client_id = LINKEDIN_CLIENT_ID
        self.client_secret = LINKEDIN_CLIENT_SECRET
        self.redirect_uri = LINKEDIN_REDIRECT_URI
        self.scope = LINKEDIN_SCOPE

    def generate_auth_url(self, user_id: str) -> Dict:
        """Generate LinkedIn OAuth URL"""
        state = f"linkedin-{user_id}-{int(datetime.now().timestamp())}"
        auth_url = (
            f"https://www.linkedin.com/oauth/v2/authorization?"
            f"response_type=code&"
            f"client_id={self.client_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"state={state}&"
            f"scope={self.scope}"
        )
        return {"auth_url": auth_url}

    async def handle_callback(self, code: str, state: str) -> Dict:
        """Exchange authorization code for access token"""
        try:
            # Extract userId from state
            # State format: linkedin-{uuid}-{timestamp}
            # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (has dashes)
            state_parts = state.split('-')
            if len(state_parts) < 3:
                return {"error": "Invalid state parameter format"}
            
            # Remove "linkedin" prefix and timestamp suffix
            # UUID is everything between "linkedin" and the last part (timestamp)
            # Example: linkedin-90a41a77-d8d0-45ff-ad2f-341112b5920a-1764948914
            # Parts: ["linkedin", "90a41a77", "d8d0", "45ff", "ad2f", "341112b5920a", "1764948914"]
            # UUID: parts[1:-1] = ["90a41a77", "d8d0", "45ff", "ad2f", "341112b5920a"]
            uuid_parts = state_parts[1:-1]  # Skip "linkedin" and timestamp
            user_id = '-'.join(uuid_parts)  # Rejoin UUID parts
            
            if not user_id or len(user_id) < 30:  # UUID should be at least 30 chars
                return {"error": "Invalid state parameter - user_id not found"}

            # Exchange code for token
            async with aiohttp.ClientSession() as session:
                token_data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                }
                
                async with session.post(
                    "https://www.linkedin.com/oauth/v2/accessToken",
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return {"error": f"Token exchange failed: {error_text}"}
                    
                    token_response = await resp.json()
                    access_token = token_response.get("access_token")
                    expires_in = token_response.get("expires_in", 5184000)  # Default 60 days
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

                    # Fetch profile info
                    async with session.get(
                        "https://api.linkedin.com/v2/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as profile_resp:
                        if profile_resp.status == 200:
                            profile = await profile_resp.json()
                        else:
                            profile = {}

                    # Save to Supabase using admin client to bypass RLS
                    if self.supabase_admin:
                        try:
                            # Upsert LinkedIn connection
                            connection_data = {
                                "user_id": user_id,
                                "access_token": access_token,
                                "expires_at": expires_at.isoformat(),
                                "profile_id": profile.get("sub", ""),
                                "profile_name": profile.get("name", ""),
                                "profile_email": profile.get("email", ""),
                                "profile_picture": profile.get("picture", ""),
                            }
                            
                            # Check if connection exists (use admin for read too to ensure we can see the record)
                            existing = self.supabase_admin.table("linkedin_connections").select("*").eq("user_id", user_id).execute()
                            
                            if existing.data:
                                # Update existing
                                self.supabase_admin.table("linkedin_connections").update(connection_data).eq("user_id", user_id).execute()
                            else:
                                # Insert new
                                self.supabase_admin.table("linkedin_connections").insert(connection_data).execute()
                        except Exception as e:
                            return {"error": f"Failed to save LinkedIn connection: {str(e)}"}

                    return {
                        "message": "LinkedIn connected successfully",
                        "profile": profile,
                    }
        except Exception as e:
            return {"error": f"LinkedIn auth failed: {str(e)}"}

    async def get_connection_status(self, user_id: str) -> Dict:
        """Get LinkedIn connection status"""
        # Use admin client to bypass RLS for reads
        client = self.supabase_admin or self.supabase_client
        if not client:
            return {"error": "Supabase client not configured"}
        
        try:
            result = client.table("linkedin_connections").select("*").eq("user_id", user_id).execute()
            
            if not result.data:
                return {"is_connected": False, "profile": None}
            
            connection = result.data[0]
            
            expires_at_str = connection.get("expires_at")
            
            is_connected = False
            if expires_at_str:
                # Normalize datetime string to handle microseconds properly
                expires_at_str = expires_at_str.replace('Z', '+00:00')
                # Fix microseconds: ensure exactly 6 digits
                if '.' in expires_at_str and '+' in expires_at_str:
                    parts = expires_at_str.split('.')
                    if len(parts) == 2:
                        microseconds_part = parts[1].split('+')[0].split('-')[0]
                        if len(microseconds_part) < 6:
                            microseconds_part = microseconds_part.ljust(6, '0')
                        elif len(microseconds_part) > 6:
                            microseconds_part = microseconds_part[:6]
                        timezone_part = expires_at_str.split('+')[-1] if '+' in expires_at_str else expires_at_str.split('-')[-1]
                        expires_at_str = f"{parts[0]}.{microseconds_part}+{timezone_part}"
                
                expires_at = datetime.fromisoformat(expires_at_str)
                now_utc = datetime.now(timezone.utc)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                is_connected = expires_at > now_utc
            
            # Build profile object - check if profile data exists
            profile_data = None
            profile_id = connection.get("profile_id")
            profile_name = connection.get("profile_name")
            profile_email = connection.get("profile_email")
            profile_picture = connection.get("profile_picture")
            
            # Return profile if we have at least profile_id or name
            if profile_id or profile_name:
                profile_data = {
                    "name": profile_name,
                    "email": profile_email,
                    "picture": profile_picture,
                    "sub": profile_id,
                }
            
            return {
                "is_connected": is_connected,
                "profile": profile_data,
                "expires_at": expires_at_str,
            }
        except Exception as e:
            return {"error": f"Failed to get connection status: {str(e)}"}

    async def get_access_token(self, user_id: str) -> Dict:
        """Get user's LinkedIn access token"""
        # Use admin client to bypass RLS for reads
        client = self.supabase_admin or self.supabase_client
        if not client:
            return {"error": "Supabase client not configured"}
        
        try:
            result = client.table("linkedin_connections").select("*").eq("user_id", user_id).execute()
            
            if not result.data:
                return {"error": "LinkedIn not connected. Please connect your LinkedIn account first."}
            
            connection = result.data[0]
            access_token = connection.get("access_token")
            expires_at_str = connection.get("expires_at")
            
            if not access_token:
                return {"error": "LinkedIn not connected. Please connect your LinkedIn account first."}
            
            if expires_at_str:
                expires_at_str = expires_at_str.replace('Z', '+00:00')
                if '.' in expires_at_str and '+' in expires_at_str:
                    parts = expires_at_str.split('.')
                    if len(parts) == 2:
                        microseconds_part = parts[1].split('+')[0].split('-')[0]
                        if len(microseconds_part) < 6:
                            microseconds_part = microseconds_part.ljust(6, '0')
                        elif len(microseconds_part) > 6:
                            microseconds_part = microseconds_part[:6]
                        timezone_part = expires_at_str.split('+')[-1] if '+' in expires_at_str else expires_at_str.split('-')[-1]
                        expires_at_str = f"{parts[0]}.{microseconds_part}+{timezone_part}"
                
                expires_at = datetime.fromisoformat(expires_at_str)
                now_utc = datetime.now(timezone.utc)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at <= now_utc:
                    return {"error": "LinkedIn token expired. Please reconnect your account."}
            
            profile = {
                "sub": connection.get("profile_id", ""),
                "name": connection.get("profile_name", ""),
                "email": connection.get("profile_email", ""),
                "picture": connection.get("profile_picture", ""),
            }
            
            return {
                "token": access_token,
                "profile": profile,
            }
        except Exception as e:
            return {"error": f"Failed to get access token: {str(e)}"}

    async def post_text(self, user_id: str, text: str) -> Dict:
        """Post simple text to LinkedIn"""
        # Convert markdown to LinkedIn-friendly plain text
        from utils.markdown_converter import markdown_to_linkedin
        text = markdown_to_linkedin(text)
        
        token_info = await self.get_access_token(user_id)
        if "error" in token_info:
            return token_info
        
        token = token_info["token"]
        profile = token_info["profile"]
        author_urn = f"urn:li:person:{profile.get('sub', '')}"
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "author": author_urn,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": text},
                            "shareMediaCategory": "NONE",
                        },
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
                    },
                }
                
                async with session.post(
                    "https://api.linkedin.com/v2/ugcPosts",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0",
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 201 or resp.status == 200:
                        response_data = await resp.json()
                        post_id = response_data.get("id")
                        # Generate LinkedIn post URL from post_id
                        # Format: https://www.linkedin.com/feed/update/{post_id}
                        post_url = None
                        if post_id:
                            # Extract URN from post_id if it's a full URN
                            # post_id format: urn:li:ugcPost:{numeric_id}
                            if ":" in str(post_id):
                                parts = str(post_id).split(":")
                                if len(parts) >= 4:
                                    numeric_id = parts[-1]
                                    post_url = f"https://www.linkedin.com/feed/update/{numeric_id}"
                            else:
                                post_url = f"https://www.linkedin.com/feed/update/{post_id}"
                        
                        return {
                            "message": "✅ Posted successfully to LinkedIn!",
                            "content": text,
                            "post_id": post_id,
                            "post_url": post_url,
                        }
                    else:
                        error_text = await resp.text()
                        return {"error": f"Failed to post to LinkedIn: {error_text}"}
        except Exception as e:
            return {"error": f"Failed to post to LinkedIn: {str(e)}"}

    async def upload_image_to_linkedin(self, token: str, image_buffer: bytes, user_sub: str) -> Optional[str]:
        """Upload image to LinkedIn and return asset URN"""
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Register upload
                register_payload = {
                    "registerUploadRequest": {
                        "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                        "owner": f"urn:li:person:{user_sub}",
                        "serviceRelationships": [
                            {
                                "relationshipType": "OWNER",
                                "identifier": "urn:li:userGeneratedContent",
                            },
                        ],
                    },
                }
                
                async with session.post(
                    "https://api.linkedin.com/v2/assets?action=registerUpload",
                    json=register_payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0",
                    },
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as register_resp:
                    if register_resp.status != 200:
                        return None
                    
                    register_data = await register_resp.json()
                    upload_url = register_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                    asset = register_data["value"]["asset"]
                    
                    # Step 2: Upload image
                    async with session.put(
                        upload_url,
                        data=image_buffer,
                        headers={"Content-Type": "image/jpeg"},
                        timeout=aiohttp.ClientTimeout(total=120)
                    ) as upload_resp:
                        if upload_resp.status == 200 or upload_resp.status == 201:
                            return asset
                        return None
        except Exception as e:
            return None

    async def post_with_image(self, user_id: str, text: str, image_base64: Optional[str] = None, image_url: Optional[str] = None) -> Dict:
        """Post to LinkedIn with image. Accepts either image_url (preferred) or image_base64"""
        # Convert markdown to LinkedIn-friendly plain text
        from utils.markdown_converter import markdown_to_linkedin
        text = markdown_to_linkedin(text)
        
        token_info = await self.get_access_token(user_id)
        if "error" in token_info:
            return token_info
        
        token = token_info["token"]
        profile = token_info["profile"]
        author_urn = f"urn:li:person:{profile.get('sub', '')}"
        user_sub = profile.get('sub', '')
        
        try:
            image_buffer = None
            
            # Prefer image_url over image_base64
            if image_url:
                # Download image from URL
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            image_buffer = await resp.read()
                        else:
                            return {"error": f"Failed to download image from URL: HTTP {resp.status}"}
            elif image_base64:
                # Check if it's actually a URL disguised as base64
                if image_base64.startswith("http://") or image_base64.startswith("https://"):
                    # It's actually a URL, download it
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_base64, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                            if resp.status == 200:
                                image_buffer = await resp.read()
                            else:
                                return {"error": f"Failed to download image from URL: HTTP {resp.status}"}
                else:
                    # Convert base64 to bytes
                    import re
                    base64_data = re.sub(r"data:image/\w+;base64,", "", image_base64)
                    image_buffer = base64.b64decode(base64_data)
            else:
                return {"error": "No image provided (neither image_url nor image_base64)"}
            
            if not image_buffer:
                return {"error": "Failed to get image data"}
            
            asset = await self.upload_image_to_linkedin(token, image_buffer, user_sub)
            if not asset:
                return {"error": "Failed to upload image to LinkedIn"}
            
            # Post with image
            async with aiohttp.ClientSession() as session:
                payload = {
                    "author": author_urn,
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": text},
                            "shareMediaCategory": "IMAGE",
                            "media": [
                                {
                                    "status": "READY",
                                    "media": asset,
                                    "title": {"text": "AI Generated Image"},
                                },
                            ],
                        },
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
                    },
                }
                
                async with session.post(
                    "https://api.linkedin.com/v2/ugcPosts",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0",
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 201 or resp.status == 200:
                        response_data = await resp.json()
                        post_id = response_data.get("id")
                        # Generate LinkedIn post URL from post_id
                        post_url = None
                        if post_id:
                            if ":" in str(post_id):
                                parts = str(post_id).split(":")
                                if len(parts) >= 4:
                                    numeric_id = parts[-1]
                                    post_url = f"https://www.linkedin.com/feed/update/{numeric_id}"
                            else:
                                post_url = f"https://www.linkedin.com/feed/update/{post_id}"
                        
                        return {
                            "message": "✅ Posted successfully to LinkedIn with image!",
                            "content": text,
                            "post_id": post_id,
                            "post_url": post_url,
                        }
                    else:
                        error_text = await resp.text()
                        return {"error": f"Failed to post to LinkedIn: {error_text}"}
        except Exception as e:
            return {"error": f"Failed to post to LinkedIn: {str(e)}"}
