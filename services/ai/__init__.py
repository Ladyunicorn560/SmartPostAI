"""AI Service - Main service class"""
from .post_generator import PostGenerator
from .image_generator import ImageGenerator
from .url_extractor import URLExtractor
from .ideas_generator import AIPostChain
from typing import Dict, List, Optional
from uagents import Context

class AIService:
    """Main AI service that coordinates all AI operations"""
    
    def __init__(self, agent_context: Optional[Context] = None):
        self.agent_context = agent_context
        self.post_generator = PostGenerator(agent_context)
        self.image_generator = ImageGenerator(agent_context)
        self.url_extractor = URLExtractor(agent_context)
        self.ideas_generator = AIPostChain()

        # Expose image generation agent for compatibility
        self.image_generation_agent = self.image_generator.image_generation_agent
        self._pending_image_requests = self.image_generator._pending_image_requests
        self._last_image_url = self.image_generator._last_image_url
        
    async def generate_linkedin_post(self, topic: str, include_hashtags: bool = True, language: str = "en") -> Dict:
        """Generate a LinkedIn post based on a topic"""
        return await self.post_generator.generate(topic, include_hashtags, language)
    
    async def generate_image_prompt(self, topic: str) -> str:
        """Generate an image description/prompt for the topic"""
        return await self.post_generator.generate_image_prompt(topic)
    
    async def generate_image(self, prompt: str, topic: Optional[str] = None, ctx: Optional[Context] = None) -> Optional[str]:
        """Generate an image using Gemini API directly - returns URL only"""
        return await self.image_generator.generate(prompt, topic, ctx)
    
    def handle_image_response(self, sender: str, msg) -> bool:
        """Handle incoming ChatMessage responses from image generation agent"""
        return self.image_generator.handle_response(sender, msg)
    
    async def generate_linkedin_post_with_image(self, topic: str, include_image: bool = False, language: str = "en", ctx: Optional[Context] = None) -> Dict:
        """Generate a complete LinkedIn post with optional image - uses Gemini API directly"""
        post = await self.generate_linkedin_post(topic, True, language)
        
        if include_image:
            image_prompt = await self.generate_image_prompt(topic)
            image_url = await self.generate_image(image_prompt, topic=topic, ctx=ctx)
            
            if image_url:
                return {**post, "image_prompt": image_prompt, "image_url": image_url}
            else:
                return {**post, "image_prompt": image_prompt, "image_url": None, "image_error": "Gemini Image generation quota exceeded (429)"}
        
        return post
    
    async def extract_and_convert_url_to_post(self, url: str, include_image: bool = False, language: str = "en", ctx: Optional[Context] = None) -> Dict:
        """Extract content from URL and convert to LinkedIn post"""
        result = await self.url_extractor.extract_and_convert(url, include_image, language)
        
        if include_image and "error" not in result:
            try:
                image_prompt = await self.generate_image_prompt(result.get("text", "")[:200] or result.get("source_title", url))
                self._last_image_url = None
                image_url = await self.generate_image(image_prompt, topic=result.get("source_title") or url, ctx=ctx)
                
                if image_url:
                    result["image_url"] = image_url
                else:
                    result["image_error"] = "Image generation failed"
            except Exception as img_error:
                result["image_error"] = f"Image generation error: {str(img_error)}"
        
        return result
    
    async def generate_post_ideas(self, industry: Optional[str] = None, topic: Optional[str] = None, prompt: Optional[str] = None, count: int = 5, language: str = "en") -> Dict:
        """Generate LinkedIn post ideas optimized for content creators and tech professionals"""
        return await self.ideas_generator.generate(industry, topic, prompt, count, language)

