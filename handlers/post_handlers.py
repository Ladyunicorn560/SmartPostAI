"""Post-related REST handlers (URL to post, generated posts, ideas)"""
from typing import Dict, Any
from uagents import Context
from rest_models import (
    URLToPostRESTRequest,
    URLToPostRESTResponse,
    GetGeneratedPostsRESTResponse,
    GenerateIdeasRESTRequest,
    GenerateIdeasRESTResponse,
    PostGeneratedPostRESTRequest,
    PostGeneratedPostRESTResponse,
)
from utils.auth import _get_user_id_from_token

def register_post_handlers(agent, ai_service, linkedin_service, payment_service, supabase_admin):
    """Register post-related REST handlers"""
    
    @agent.on_rest_post("/linkedin/url-to-post", URLToPostRESTRequest, URLToPostRESTResponse)
    async def handle_url_to_post_frontend(ctx: Context, req: URLToPostRESTRequest) -> Dict[str, Any]:
        """Convert URL to LinkedIn post - requires user approval before posting"""
        try:
            if not req.user_id:
                req.user_id = await _get_user_id_from_token(ctx)
            if not req.user_id:
                return {"error": "Authentication required"}
            
            include_image = req.include_image or req.includeImage or False
            
            result = await ai_service.extract_and_convert_url_to_post(
                req.url,
                include_image,
                req.language,
                ctx
            )
            
            if "error" in result:
                return {"text": "", "hashtags": [], "source_url": req.url, "error": result["error"]}
            
            post_id = None
            image_url = result.get("image_url")
            linkedin_post_url = None
            linkedin_post_id = None
            
            if include_image and not image_url:
                pass
            
            if supabase_admin:
                try:
                    post_data = {
                        "user_id": req.user_id,
                        "topic": result.get("source_title") or req.url,
                        "content": result.get("text", ""),
                        "hashtags": result.get("hashtags", []),
                        "image_url": image_url,
                        "language": req.language,
                        "source_url": result.get("source_url", req.url),
                        "linkedin_post_url": linkedin_post_url,
                        "linkedin_post_id": linkedin_post_id,
                    }
                    
                    save_result = supabase_admin.table("generated_posts").insert(post_data).execute()
                    if save_result.data and len(save_result.data) > 0:
                        post_id = save_result.data[0]["id"]
                except Exception as save_error:
                    pass
            
            return {
                "text": result.get("text", ""),
                "hashtags": result.get("hashtags", []),
                "imageUrl": image_url,  # URL from agent
                "image_url": image_url,  # URL from agent
                "image_error": result.get("image_error"),  # Include image error if any
                "source_url": result.get("source_url", req.url),
                "source_title": result.get("source_title"),
                "postId": post_id,
                "linkedin_post_url": linkedin_post_url,
                "linkedin_post_id": linkedin_post_id,
                "error": None,
            }
        except Exception as e:
            return {"text": "", "hashtags": [], "source_url": req.url, "error": str(e)}
    
    @agent.on_rest_get("/linkedin/posts", GetGeneratedPostsRESTResponse)
    async def handle_get_generated_posts_frontend(ctx: Context) -> Dict[str, Any]:
        """Get all generated posts and scheduled posts for user - Frontend version"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"posts": [], "error": "Authentication required"}
            
            if not supabase_admin:
                return {"posts": [], "error": "Database not configured"}
            
            posts = []
            
            # Get generated posts
            generated_result = supabase_admin.table("generated_posts").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            if generated_result.data:
                for post in generated_result.data:
                    posts.append({
                        "id": post.get("id"),
                        "topic": post.get("topic", ""),
                        "content": post.get("content", ""),
                        "hashtags": post.get("hashtags", []),
                        "image_url": post.get("image_url"),
                        "source_url": post.get("source_url"),
                        "linkedin_post_url": post.get("linkedin_post_url"),
                        "linkedin_post_id": post.get("linkedin_post_id"),
                        "language": post.get("language", "en"),
                        "created_at": post.get("created_at"),
                    })
            
            # Get scheduled posts that have been posted
            scheduled_result = supabase_admin.table("scheduled_posts").select("*").eq("user_id", user_id).in_("status", ["posted", "pending"]).order("posted_at", desc=True).execute()
            if scheduled_result.data:
                for schedule in scheduled_result.data:
                    # Only include if it has been posted (has post_id or post_url)
                    if schedule.get("post_id") or schedule.get("post_url"):
                        posts.append({
                            "id": schedule.get("id"),
                            "topic": schedule.get("content", ""),  # Topic/content
                            "content": schedule.get("content", ""),  # Same as topic for scheduled posts
                            "hashtags": [],
                            "image_url": schedule.get("image_url") if schedule.get("image_url") and schedule.get("image_url") != "__GENERATE_ON_EXECUTION__" else None,
                            "source_url": None,
                            "linkedin_post_url": schedule.get("post_url"),
                            "linkedin_post_id": schedule.get("post_id"),
                            "language": "en",
                            "created_at": schedule.get("posted_at") or schedule.get("created_at"),
                        })
            
            # Sort all posts by created_at descending
            posts.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return {
                "posts": posts,
                "error": None,
            }
        except Exception as e:
            return {"posts": [], "error": str(e)}
    
    @agent.on_rest_post("/linkedin/generate-ideas", GenerateIdeasRESTRequest, GenerateIdeasRESTResponse)
    async def handle_generate_ideas_frontend(ctx: Context, req: GenerateIdeasRESTRequest) -> GenerateIdeasRESTResponse:
        """Generate LinkedIn post ideas - No payment required"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return GenerateIdeasRESTResponse(ideas=[], error="Authentication required")
            
            result = await ai_service.generate_post_ideas(
                req.industry,
                req.topic,
                req.prompt,
                req.count,
                req.language
            )
            
            if "error" in result:
                return GenerateIdeasRESTResponse(ideas=[], error=result["error"])
            
            return GenerateIdeasRESTResponse(
                ideas=result.get("ideas", []),
                error=None,
            )
        except Exception as e:
            return GenerateIdeasRESTResponse(ideas=[], error=str(e))
    
    @agent.on_rest_post("/linkedin/post-generated", PostGeneratedPostRESTRequest, PostGeneratedPostRESTResponse)
    async def handle_post_generated_content(ctx: Context, req: PostGeneratedPostRESTRequest) -> Dict[str, Any]:
        """Post generated content to LinkedIn"""
        try:
            if not req.user_id:
                req.user_id = await _get_user_id_from_token(ctx)
            if not req.user_id:
                return {"success": False, "error": "Authentication required"}
            
            if not linkedin_service:
                return {"success": False, "error": "LinkedIn service not available"}
            
            # Get the generated post from database
            if not supabase_admin:
                return {"success": False, "error": "Database not available"}
            
            try:
                post_result = supabase_admin.table("generated_posts").select("*").eq("id", req.post_id).eq("user_id", req.user_id).execute()
                if not post_result.data or len(post_result.data) == 0:
                    return {"success": False, "error": "Generated post not found"}
                
                generated_post = post_result.data[0]
                content = generated_post.get("content", "")
                image_url = generated_post.get("image_url")
                
                if not content:
                    return {"success": False, "error": "No content to post"}
                
                # Post to LinkedIn
                try:
                    # Create a simple request object for the LinkedIn service
                    class LinkedInRequest:
                        def __init__(self, text, user_id, image_url=None):
                            self.text = text
                            self.user_id = user_id
                            self.imageUrl = image_url
                    
                    linkedin_req = LinkedInRequest(content, req.user_id, image_url)
                    result = await linkedin_service.post_text(req.user_id, content, image_url)
                    
                    if "error" in result:
                        return {"success": False, "error": result["error"]}
                    
                    # Update the generated post with LinkedIn post info
                    linkedin_post_id = result.get("post_id")
                    linkedin_post_url = result.get("post_url") or result.get("url")
                    
                    if linkedin_post_id:
                        update_data = {
                            "linkedin_post_id": linkedin_post_id,
                            "linkedin_post_url": linkedin_post_url,
                            "updated_at": "now()"
                        }
                        
                        supabase_admin.table("generated_posts").update(update_data).eq("id", req.post_id).execute()
                    
                    return {
                        "success": True,
                        "post_id": linkedin_post_id,
                        "post_url": linkedin_post_url,
                        "message": "Successfully posted to LinkedIn"
                    }
                    
                except Exception as linkedin_error:
                    return {"success": False, "error": f"Failed to post to LinkedIn: {str(linkedin_error)}"}
                
            except Exception as db_error:
                return {"success": False, "error": f"Database error: {str(db_error)}"}
                
        except Exception as e:
            return {"success": False, "error": f"Unexpected error: {str(e)}"}

