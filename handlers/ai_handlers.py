"""AI REST handlers - Content generation without payment"""
from typing import Dict, Any
from uagents import Context
from rest_models import (
    GeneratePostRESTRequest,
    GeneratePostRESTResponse,
    GenerateImageRESTRequest,
    GenerateImageRESTResponse,
)

def register_ai_handlers(agent, ai_service, payment_service=None, supabase_admin=None, scheduler_service=None):
    """Register AI-related REST handlers - No payment required for content generation"""
    
    @agent.on_rest_post("/api/ai/generate-post", GeneratePostRESTRequest, GeneratePostRESTResponse)
    async def handle_generate_post_rest(ctx: Context, req: GeneratePostRESTRequest) -> GeneratePostRESTResponse:
        """Generate LinkedIn post via REST - No payment required for content generation
        
        Payment is only required when posting to LinkedIn, not for generating content.
        """
        try:
            # Generate post (AI agent creates content) - no payment check needed
            result = await ai_service.generate_linkedin_post(
                req.topic,
                req.include_hashtags,
                req.language
            )
            if "error" in result:
                return GeneratePostRESTResponse(text="", error=result["error"])
            
            return GeneratePostRESTResponse(
                text=result["text"],
                hashtags=result.get("hashtags", []),
            )
        except Exception as e:
            return GeneratePostRESTResponse(text="", error=str(e))
    
    @agent.on_rest_post("/api/ai/generate-post-with-image", GeneratePostRESTRequest, GeneratePostRESTResponse)
    async def handle_generate_post_with_image_rest(ctx: Context, req: GeneratePostRESTRequest) -> GeneratePostRESTResponse:
        """Generate LinkedIn post with image via REST - No payment required for content generation
        
        Payment is only required when posting to LinkedIn, not for generating content.
        """
        try:
            result = await ai_service.generate_linkedin_post_with_image(
                req.topic,
                req.include_image,
                req.language,
                ctx
            )
            if "error" in result and not result.get("text"):
                return GeneratePostRESTResponse(text="", error=result["error"])
            
            
            schedule_id = None
            review_link = None
            
            # Check if user wants to schedule
            if scheduler_service and (req.schedule or req.scheduled_at):
                full_text = result["text"]
                if result.get("hashtags"):
                    full_text += "\n\n" + " ".join(result["hashtags"])
                
                # Get user_id from context if available
                user_id = None
                try:
                    from utils.auth import _get_user_id_from_token
                    user_id = await _get_user_id_from_token(ctx)
                except:
                    pass
                
                if user_id:
                    schedule_result = await scheduler_service.create_scheduled_post(
                        user_id,
                        req.topic,
                        req.schedule or "",
                        req.include_image,
                        full_text,
                        result.get("image_url"),
                        req.scheduled_at,
                        req.require_approval
                    )
                    
                    if schedule_result.get("schedule_id"):
                        schedule_id = schedule_result["schedule_id"]
                        review_link = schedule_result.get("review_link")
            
            # Always return schedule fields (even if None) so frontend knows schedule options are available
            return GeneratePostRESTResponse(
                text=result["text"],
                hashtags=result.get("hashtags", []),
                image_prompt=result.get("image_prompt"),
                image_url=result.get("image_url"),
                schedule_id=schedule_id,  # Always included, None if not scheduled
                review_link=review_link,  # Always included, None if not scheduled/approved
            )
        except Exception as e:
            return GeneratePostRESTResponse(text="", error=str(e))
    
    @agent.on_rest_post("/api/ai/generate-image", GenerateImageRESTRequest, GenerateImageRESTResponse)
    async def handle_generate_image_rest(ctx: Context, req: GenerateImageRESTRequest) -> GenerateImageRESTResponse:
        """Generate image via REST - returns URL from Gemini API"""
        try:
            image_prompt = await ai_service.generate_image_prompt(req.topic)
            image_url = await ai_service.generate_image(image_prompt, ctx=ctx)
            
            if image_url:
                return GenerateImageRESTResponse(
                    image_prompt=image_prompt,
                    image_url=image_url,
                )
            else:
                return GenerateImageRESTResponse(
                    image_prompt=image_prompt,
                    error="Image generation failed"
                )
        except Exception as e:
            return GenerateImageRESTResponse(image_prompt="", error=str(e))

