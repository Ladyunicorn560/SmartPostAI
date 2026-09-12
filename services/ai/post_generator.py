"""Post generation service - Uses LangChain for AI post generation"""
import os
import json
import re
import datetime
import aiohttp
from typing import Dict, Optional
from uagents import Context
from dotenv import load_dotenv

load_dotenv()

# Import LangChain chain - REQUIRED
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from chains.ai_chain import AIPostChain

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={GEMINI_API_KEY}"

class PostGenerator:
    """Handles LinkedIn post generation using LangChain"""
    
    def __init__(self, agent_context: Optional[Context] = None):
        self.gemini_api_key = GEMINI_API_KEY
        self.agent_context = agent_context
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        # Initialize LangChain chain - REQUIRED
        self.ai_chain = AIPostChain()
    
    async def generate(self, topic: str, include_hashtags: bool = True, language: str = "en") -> Dict:
        """Generate a LinkedIn post based on a topic using LangChain - Personal, experience-driven"""
        # Use LangChain chain - REQUIRED
        result = await self.ai_chain.generate_post(topic, language)
        if result.get("success"):
            content = result.get("content", "")
            # Extract hashtags if needed
            hashtags = []
            if include_hashtags:
                # Extract hashtags from content or generate
                hashtag_match = re.findall(r'#\w+', content)
                hashtags = hashtag_match if hashtag_match else []
            
            return {
                "text": content,
                "hashtags": hashtags,
                "has_error": False
            }
        else:
            # Return error if LangChain fails
            return {
                "text": "",
                "hashtags": [],
                "has_error": True,
                "error": result.get("error", "Failed to generate post")
            }
    
    async def _generate_direct(self, topic: str, include_hashtags: bool = True, language: str = "en") -> Dict:
        """Fallback: Direct API generation"""
        language_map = {
            'en': 'English', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian',
            'de': 'German', 'pt': 'Portuguese', 'nl': 'Dutch',
        }
        language_name = language_map.get(language, 'English')
        
        language_instructions = {
            'en': 'Write in English only. Use English words, grammar, and expressions.',
            'fr': 'Écrivez uniquement en français. Utilisez des mots, une grammaire et des expressions françaises.',
            'es': 'Escribe solo en español. Usa palabras, gramática y expresiones españolas.',
            'it': 'Scrivi solo in italiano. Usa parole, grammatica ed espressioni italiane.',
            'de': 'Schreibe nur auf Deutsch. Verwende deutsche Wörter, Grammatik und Ausdrücke.',
            'pt': 'Escreva apenas em português. Use palavras, gramática e expressões portuguesas.',
            'nl': 'Schrijf alleen in het Nederlands. Gebruik Nederlandse woorden, grammatica en uitdrukkingen.',
        }
        
        lang_instruction = language_instructions.get(language, language_instructions['en'])
        
        prompt = f"""You are a professional LinkedIn content writer. Generate a highly engaging LinkedIn post about "{topic}".

🚨 CRITICAL: USE WEB SEARCH TO GET REAL INFORMATION WITH SOURCES 🚨
- First, use google_web_search to find REAL, CURRENT information about "{topic}"
- Search for actual companies, products, services, or facts related to "{topic}"
- Use ONLY real, verified information from web search results
- Do NOT make up company names, statistics, or facts
- Base your content on actual search results and cite real sources
- IMPORTANT: Include actual source links/URLs in your post when mentioning specific companies, products, or facts
- Format links as: [Company Name](URL) or just include URLs at the end
- If you find real companies/products/services, mention them accurately WITH their source links
- Use web search to get current data, trends, and real-world examples WITH citations
- Add a "Sources:" section at the end with relevant links if discussing specific companies or facts

🚨 CRITICAL LANGUAGE REQUIREMENT - THIS IS MANDATORY 🚨
{lang_instruction}
The ENTIRE post must be written in {language_name} ONLY. 
- Do NOT use English or any other language
- Every single word, sentence, and paragraph must be in {language_name}
- If you write even one word in English, the response is WRONG
- The post content, hashtags, and all text must be in {language_name}
- This is not optional - it is a strict requirement

Content Requirements:
- The post should be deeply focused on the topic "{topic}" - make it highly relevant and topic-specific
- Use REAL information from web search - actual company names, real statistics, verified facts WITH SOURCE LINKS
- Length should be between 150-300 words
- Include a strong hook in the first line to grab attention
- Add value with insights, tips, or thought-provoking questions based on REAL information about "{topic}"
- When mentioning specific companies, products, or facts, include their source URLs/links
- Format links naturally: "Company Name (source: url)" or add links at the end
- End with a call-to-action or question to encourage engagement
- Make it sound natural and authentic, not robotic
- Use professional but conversational tone
- Write EXCLUSIVELY in {language_name} - no English, no code-switching, no mixing languages
- IMPORTANT: Only mention real companies/products/services found in web search - do not invent names
- Include source links/URLs when discussing specific companies, latest news, or facts from web search

FORMATTING REQUIREMENTS (CRITICAL):
- Use **bold text** for key points, important concepts, or emphasis (use **text** syntax)
- Use *italic text* for quotes, thoughts, or subtle emphasis (use *text* syntax)
- Combine formatting strategically: **bold** for main points, *italic* for quotes or emphasis
- Use formatting to make the post visually appealing and easy to scan
- Example: "This is a **key insight** that *everyone should know*"

EMOJI REQUIREMENTS:
- Include exactly 3-4 relevant emojis throughout the post
- Use emojis strategically: at the beginning, middle, or end to enhance engagement
- Choose emojis that match the topic "{topic}" and are professional
- Examples: 💡 🚀 ✨ 🎯 💼 🔥 📈 💪 🎨 🌟
- Do NOT overuse emojis - exactly 3-4 emojis total

{('Also suggest 3-5 relevant hashtags in ' + language_name + ' for this post. Hashtags should be relevant to ' + language_name + '-speaking LinkedIn audience and the topic "{topic}".') if include_hashtags else ''}

VERIFICATION CHECKLIST BEFORE RESPONDING:
✓ Is every word in {language_name}?
✓ Is there any English text? (If yes, rewrite it)
✓ Are hashtags in {language_name}?
✓ Does the post sound natural in {language_name}?
✓ Does the post use **bold** formatting for key points?
✓ Does the post use *italic* formatting appropriately?
✓ Does the post include exactly 3-4 emojis?
✓ Is the content deeply focused on the topic "{topic}"?

IMPORTANT: Your response must be a valid JSON object. The "text" field must contain the post written entirely in {language_name} with formatting and emojis.

Format your response as JSON:
{{
  "text": "the post content here written COMPLETELY in {language_name} with **bold** and *italic* formatting and 3-4 emojis - no English allowed",
  "hashtags": ["#hashtag1", "#hashtag2", ...]
}}"""

        try:
            headers = {"Content-Type": "application/json"}
            
            # Configure tools to enable web search using googleSearch field
            tools_config = {
                "tools": [
                    {
                        "googleSearch": {}
                    }
                ]
            }
            
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                **tools_config
            }
            
            async with aiohttp.ClientSession() as session:
                gemini_url = GEMINI_API_URL.format(GEMINI_API_KEY=self.gemini_api_key)
                async with session.post(
                    gemini_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=180)  # Increased timeout for web search
                ) as resp:
                    if resp.status == 200:
                        resp_json = await resp.json()
                        if "candidates" in resp_json and len(resp_json["candidates"]) > 0:
                            candidate = resp_json["candidates"][0]
                            
                            # Handle response with web search results
                            response_text = ""
                            
                            if "content" in candidate and "parts" in candidate["content"]:
                                parts = candidate["content"]["parts"]
                                
                                # Extract text from all text parts
                                text_parts = []
                                for part in parts:
                                    if "text" in part:
                                        text_parts.append(part["text"])
                                
                                if text_parts:
                                    response_text = " ".join(text_parts)
                                elif len(parts) > 0 and "text" in parts[0]:
                                    response_text = parts[0]["text"]
                            else:
                                # Fallback to old format
                                response_text = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
                            
                            if not response_text:
                                return {"error": "Gemini API returned empty response"}
                            
                            try:
                                json_match = re.search(r'\{[\s\S]*\}', response_text)
                                if json_match:
                                    parsed = json.loads(json_match.group(0))
                                else:
                                    parsed = json.loads(response_text)
                            except:
                                hashtags = []
                                if include_hashtags:
                                    hashtags = re.findall(r'#\w+', response_text) or []
                                text = re.sub(r'\{[\s\S]*\}', '', response_text).strip()
                                parsed = {
                                    "text": text or response_text,
                                    "hashtags": hashtags[:5],
                                }
                            
                            return {
                                "text": parsed.get("text", response_text),
                                "hashtags": parsed.get("hashtags", []),
                            }
                        else:
                            return {"error": "Gemini API returned unexpected response format"}
                    else:
                        error_text = await resp.text()
                        return {"error": f"Gemini API error (status {resp.status}): {error_text}"}
        except Exception as e:
            return {"error": f"Failed to generate LinkedIn post: {str(e)}"}
    
    async def generate_image_prompt(self, topic: str) -> str:
        """Generate a unique, varied image description/prompt for the topic - Uses ai_chain"""
        # Use ai_chain to generate image
        image_url = await self.ai_chain.generate_image(f"Professional technical image for LinkedIn post about {topic}", topic)
        if image_url:
            return image_url
        
        # Fallback to simple prompt
        import random
        
        # Add variety to image prompts
        styles = [
            "modern minimalist illustration with geometric shapes",
            "professional photography style with natural lighting",
            "abstract geometric design with bold lines",
            "isometric 3D illustration with depth",
            "flat design with vibrant gradient colors",
            "hand-drawn sketch style with artistic flair",
            "corporate infographic style with data visualization",
            "tech-focused futuristic design with neon accents",
            "warm and inviting illustration with soft colors",
            "minimalist line art with negative space"
        ]
        
        color_schemes = [
            "blue and white professional palette",
            "vibrant gradient with purple and orange",
            "warm earth tones with browns and greens",
            "cool tech colors: cyan and dark blue",
            "bold contrast: black, white, and one accent color",
            "pastel professional palette",
            "dark mode with neon accents",
            "sunset gradient: orange, pink, purple",
            "ocean theme: various shades of blue",
            "forest theme: greens and natural tones"
        ]
        
        compositions = [
            "centered focal point with negative space",
            "split-screen composition",
            "diagonal dynamic layout",
            "rule of thirds composition",
            "symmetrical balanced design",
            "asymmetric modern layout",
            "circular elements with radial design",
            "grid-based structured layout"
        ]
        
        selected_style = random.choice(styles)
        selected_colors = random.choice(color_schemes)
        selected_composition = random.choice(compositions)
        
        prompt = f"""Create a UNIQUE, detailed, professional image description for a LinkedIn post about "{topic}".

🎨 CREATIVE DIRECTION (Make it UNIQUE):
- Style: {selected_style}
- Color scheme: {selected_colors}
- Composition: {selected_composition}
- Current date context: {datetime.datetime.now().strftime('%B %Y')}

📐 TECHNICAL REQUIREMENTS:
- Professional and suitable for LinkedIn business audience
- Visually stunning, high-quality, and directly relevant to "{topic}"
- Clean, modern design with professional aesthetics
- Eye-catching and engaging to increase post visibility
- High contrast and clear composition for social media
- Professional illustration or photography style
- Avoid cluttered designs - keep it clean and focused

✨ VISUAL ELEMENTS:
- Include visual elements that represent "{topic}" clearly
- Use creative visual metaphors related to "{topic}"
- Incorporate unique design elements that stand out
- Create a memorable visual identity
- Ensure it's different from typical LinkedIn post images

🚫 AVOID:
- Generic stock photo look
- Overused visual clichés
- Cluttered or busy designs
- Low contrast or hard-to-read elements

Be SPECIFIC about:
- Visual elements that represent "{topic}" (be creative and unique)
- Color palette: {selected_colors}
- Composition: {selected_composition}
- Style: {selected_style}
- Mood and atmosphere (professional yet engaging)

Return only the detailed image description (no JSON, no markdown), suitable for an AI image generator. Make it comprehensive, specific, and UNIQUE. Ensure each generation creates a different visual approach."""

        try:
            headers = {"Content-Type": "application/json"}
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            
            async with aiohttp.ClientSession() as session:
                gemini_url = GEMINI_API_URL.format(GEMINI_API_KEY=self.gemini_api_key)
                async with session.post(
                    gemini_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        resp_json = await resp.json()
                        if "candidates" in resp_json and len(resp_json["candidates"]) > 0:
                            return resp_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                    return f"Professional illustration related to {topic}, modern business style, clean design"
        except Exception as e:
            return f"Professional illustration related to {topic}, modern business style, clean design"

