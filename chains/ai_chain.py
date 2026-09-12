"""LangChain integration for AI post generation with tool calling - Handles content, images, ideas, and URL extraction"""
from typing import Dict, Optional, List, Tuple
import os
import aiohttp
import json
import re
import base64
import random
from io import BytesIO
from html import unescape
from dotenv import load_dotenv

load_dotenv()

# Check for mock mode (for development when API quota is exceeded)
USE_MOCK_MODE = os.getenv("USE_MOCK_MODE", "false").lower() == "true"

# LangChain imports - REQUIRED
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Import agent executor - use compatible approach for langchain 1.2.0
create_agent = None
AgentExecutor = None
AgentType = None
USE_CREATE_AGENT = False

try:
    from langchain.agents import create_agent
    from langchain.agents import AgentType
    USE_CREATE_AGENT = True
    # Try to import AgentExecutor from various locations
    try:
        from langchain.agents import AgentExecutor
    except ImportError:
        try:
            from langchain.agents.agent import AgentExecutor
        except ImportError:
            try:
                from langchain.agents.agent_executor import AgentExecutor
            except ImportError:
                AgentExecutor = None
except ImportError:
    try:
        from langchain.agents import initialize_agent, AgentType
        USE_CREATE_AGENT = False
        try:
            from langchain.agents import AgentExecutor
        except ImportError:
            try:
                from langchain.agents.agent import AgentExecutor
            except ImportError:
                AgentExecutor = None
    except ImportError:
        pass

class AIPostChain:
    """LangChain-based AI post generation with web search - Handles content, images, ideas, and URL extraction"""
    
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        # Initialize LangChain - REQUIRED
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            google_api_key=self.gemini_api_key,
            temperature=0.8,  # Higher for more creative, personal content
        )
        self.tools = self._create_tools()
        self.agent = self._create_agent()
        
        # Image generation settings - use gemini-2.5-flash-image
        self.image_model = "gemini-2.5-flash-image"
        self.image_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.image_model}:generateContent"
        self.tmpfiles_api_url = "https://tmpfiles.org/api/v1/upload"
        
        # Agent can be None if LangChain setup fails - will use fallback in generate_post
    
    def _create_tools(self):
        """Create LangChain tools for web search"""
        # Store reference to self for async call
        self_ref = self
        
        def web_search_sync(query: str) -> str:
            """Sync wrapper for web search - LangChain tools need sync functions"""
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(self_ref._web_search_async(query))
        
        return [
            Tool(
                name="web_search",
                description="Search the web for real-time, current information about topics, companies, products, or trends. Always use this to get factual, up-to-date information with sources.",
                func=web_search_sync
            )
        ]
    
    async def _web_search_async(self, query: str) -> str:
        """Async web search using Gemini's googleSearch tool"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_api_key}"
                
                payload = {
                    "contents": [{
                        "parts": [{"text": f"Search web for: {query}. Return factual, current information with sources."}]
                    }],
                    "tools": [{"googleSearch": {}}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 1024,
                    }
                }
                
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "candidates" in data and len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                text_parts = []
                                for part in candidate["content"]["parts"]:
                                    if "text" in part:
                                        text_parts.append(part["text"])
                                return "\n".join(text_parts)
            return ""
        except Exception:
            return ""
    
    def _create_agent(self):
        """Create LangChain agent with tools"""
        try:
            if USE_CREATE_AGENT and create_agent:
                # Use create_agent for langchain 1.2.0+
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are an expert LinkedIn content creator who writes PERSONAL, EXPERIENCE-DRIVEN posts. Generate LinkedIn posts directly - NO INTRODUCTORY TEXT, NO META-COMMENTARY.

CRITICAL RULES:
- DO NOT write "Here's a LinkedIn post..." or "Here's a draft..." or any similar meta-commentary
- DO NOT explain what you're creating or describe the post
- START IMMEDIATELY with the actual post content (hook, first sentence, etc.)
- Write as if you're posting directly on LinkedIn
- DO NOT mention dates, years, or time-specific references

CONTENT STYLE (PERSONAL & EXPERIENCE-DRIVEN):
- Write from FIRST-PERSON perspective ("I spent...", "I learned...", "I built...")
- Share PERSONAL EXPERIENCES and REAL LESSONS LEARNED
- Make it ACTIONABLE and EXPERIENCE-DRIVEN, not theoretical
- Use SHORT PARAGRAPHS or bullet points for easy skimming
- Professional, confident, and insightful tone
- End with a thoughtful question to encourage engagement
- Use emojis ONLY where they improve clarity (no overuse)

CONTENT GUIDELINES:
- Always use web_search tool to get current, factual, and technical information
- Include sources and links in markdown format: [Source Name](URL)
- Write in a professional yet conversational tone
- Focus on actionable insights from real experience
- Use code formatting (`backticks`) for technical terms, tools, or technologies
- Start directly with the post content, no introductions
- Share specific examples, numbers, tools, or frameworks you've used"""),
                    ("human", "{input}"),
                ])
                
                agent = create_agent(self.llm, self.tools, prompt)
                # For langchain 1.2.0, create_agent returns an agent executor directly
                if hasattr(agent, 'ainvoke'):
                    return agent
                # Otherwise wrap it
                if AgentExecutor:
                    return AgentExecutor(agent=agent, tools=self.tools, verbose=False, max_iterations=3, handle_parsing_errors=True)
                return agent
            else:
                # Fallback: use initialize_agent
                from langchain.agents import initialize_agent, AgentType
                return initialize_agent(
                    self.tools,
                    self.llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=False,
                    max_iterations=3,
                    handle_parsing_errors=True
                )
        except Exception as e:
            # Final fallback: use simple agent without tools
            try:
                from langchain.agents import initialize_agent, AgentType
                return initialize_agent(
                    self.tools,
                    self.llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=False,
                    max_iterations=3,
                    handle_parsing_errors=True
                )
            except Exception:
                # Last resort: return None and handle in generate_post
                return None
    
    async def generate_post(self, topic: str, language: str = "en") -> Dict:
        """Generate LinkedIn post using LangChain agent with web search"""
        try:
            # Mock mode for development when API quota is exceeded
            if USE_MOCK_MODE:
                return self._generate_mock_post(topic, language)
            
            language_map = {
                'en': 'English', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian',
                'de': 'German', 'pt': 'Portuguese', 'nl': 'Dutch',
            }
            language_name = language_map.get(language, 'English')
            
            # Use LangChain agent if available
            if self.agent:
                result = await self._generate_with_langchain(topic, language_name)
                if result.get("success") and result.get("content") and "Agent stopped" not in result.get("content"):
                    return result
            
            # Fallback to direct API if agent not available or hit iteration limit
            return await self._generate_direct_fallback(topic, language_name)
        except Exception as e:
            import traceback
            return {
                "success": False,
                "content": "",
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }
    
    def _generate_mock_post(self, topic: str, language: str = "en") -> Dict:
        """Generate mock post for development when API quota is exceeded"""
        mock_posts = {
            'en': f"""🚀 Excited to share insights on {topic}!

After working with this technology extensively, I've discovered 3 key game-changers:

1️⃣ **Automation is everything** - What used to take hours now takes minutes
2️⃣ **Quality over quantity** - Focus on value, not volume
3️⃣ **Community matters** - The best solutions come from collaboration

The results have been remarkable: 300% productivity boost and significantly better outcomes.

What's your experience with {topic}? Would love to hear your thoughts in the comments! 👇

#{topic.replace(' ', '').replace(',', '').replace('.', '')} #Innovation #Productivity #Tech""",
            
            'fr': f"""🚀 Ravi de partager mes idées sur {topic}!

Après avoir travaillé intensivement avec cette technologie, j'ai découvert 3 éléments clés :

1️⃣ **L'automatisation est essentielle** - Ce qui prenait des heures prend maintenant des minutes
2️⃣ **La qualité avant la quantité** - Concentrez-vous sur la valeur, pas le volume
3️⃣ **La communauté compte** - Les meilleures solutions viennent de la collaboration

Les résultats ont été remarquables : 300% d'amélioration de la productivité et de bien meilleurs résultats.

Quelle est votre expérience avec {topic} ? J'aimerais avoir vos pensées dans les commentaires ! 👇

#{topic.replace(' ', '').replace(',', '').replace('.', '')} #Innovation #Productivité #Tech"""
        }
        
        content = mock_posts.get(language, mock_posts['en'])
        
        return {
            "success": True,
            "content": content,
            "hashtags": [f"#{topic.replace(' ', '')}", "#Innovation", "#Productivity", "#Tech"],
            "image_prompt": f"Professional image representing {topic} in a modern business setting",
            "error": None
        }
    
    async def _generate_direct_fallback(self, topic: str, language_name: str) -> Dict:
        """Fallback: Direct API generation when LangChain agent unavailable"""
        prompt = f"""You are an expert LinkedIn content creator who writes PERSONAL, EXPERIENCE-DRIVEN posts. Generate a LinkedIn post directly - NO INTRODUCTORY TEXT, NO META-COMMENTARY.

🚨 CRITICAL: START DIRECTLY WITH THE POST CONTENT 🚨
- DO NOT write "Here's a LinkedIn post..." or "Here's a draft..." or any similar meta-commentary
- DO NOT explain what you're creating or describe the post
- START IMMEDIATELY with the actual post content (hook, first sentence, etc.)
- Write as if you're posting directly on LinkedIn
- DO NOT mention dates, years, or time-specific references

TOPIC: "{topic}"
LANGUAGE: {language_name}

CONTENT STYLE (PERSONAL & EXPERIENCE-DRIVEN):
- Write from FIRST-PERSON perspective ("I spent...", "I learned...", "I built...")
- Share PERSONAL EXPERIENCES and REAL LESSONS LEARNED about "{topic}"
- Make it ACTIONABLE and EXPERIENCE-DRIVEN, not theoretical
- Use SHORT PARAGRAPHS or bullet points for easy skimming
- Professional, confident, and insightful tone
- End with a thoughtful question to encourage engagement
- Use emojis ONLY where they improve clarity (no overuse or decoration)

CONTENT REQUIREMENTS:
- Use googleSearch tool to find REAL, CURRENT information about "{topic}"
- Share 3-5 practical key learnings from your experience
- Include specific examples, tools, frameworks, or numbers you've used
- Use markdown formatting: **bold**, *italics*, [links](URL), `code` for technical terms
- Include 3-5 relevant hashtags
- Write 200-300 words
- Start with a personal hook (e.g., "I spent...", "I learned...")
- End with a thoughtful question
- Include real sources in markdown: [Source](URL)
- Focus on actionable insights from real experience"""
        
        async with aiohttp.ClientSession() as session:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_api_key}"
            
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"googleSearch": {}}],
                "generationConfig": {
                    "temperature": 0.8,
                    "maxOutputTokens": 2048,
                }
            }
            
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    # Fallback without googleSearch tool (free-tier key quota protection)
                    payload_no_tools = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.8,
                            "maxOutputTokens": 2048,
                        }
                    }
                    async with session.post(url, json=payload_no_tools, timeout=aiohttp.ClientTimeout(total=180)) as resp_fallback:
                        if resp_fallback.status != 200:
                            error_text = await resp_fallback.text()
                            return {
                                "success": False,
                                "content": "",
                                "error": f"API error: {resp_fallback.status} - {error_text}"
                            }
                        data = await resp_fallback.json()
                else:
                    data = await resp.json()
                
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        text_parts = []
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                text_parts.append(part["text"])
                        
                        content = "\n".join(text_parts)
                        # Remove any meta-commentary
                        content = self._remove_meta_commentary(content)
                        
                        return {
                            "success": True,
                            "content": content.strip(),
                            "error": None
                        }
                
                return {
                    "success": False,
                    "content": "",
                    "error": "No content generated"
                }
    
    async def _generate_with_langchain(self, topic: str, language_name: str) -> Dict:
        """Generate post using LangChain agent"""
        try:
            import random
            
            # Add variety to prompts
            hooks = [
                "Start with a surprising statistic or fact",
                "Begin with a thought-provoking question",
                "Open with a bold statement or prediction",
                "Start with a personal story or anecdote",
                "Begin with a controversial opinion",
                "Open with a comparison or analogy"
            ]
            
            structures = [
                "Problem-Solution format",
                "Storytelling with beginning, middle, and end",
                "List format with actionable insights",
                "Case study format",
                "Before-After comparison",
                "Step-by-step guide format"
            ]
            
            ctas = [
                "End with a question that encourages discussion",
                "End with a call-to-action to share experiences",
                "End with a challenge for readers",
                "End with a request for opinions",
                "End with a thought-provoking statement",
                "End with an invitation to connect"
            ]
            
            selected_hook = random.choice(hooks)
            selected_structure = random.choice(structures)
            selected_cta = random.choice(ctas)
            
            input_text = f"""You are an expert LinkedIn content creator who writes PERSONAL, EXPERIENCE-DRIVEN posts. Generate a LinkedIn post directly - NO INTRODUCTORY TEXT, NO META-COMMENTARY.

TOPIC: "{topic}"
LANGUAGE: {language_name}

🚨 CRITICAL: START DIRECTLY WITH THE POST CONTENT 🚨
- DO NOT write "Here's a LinkedIn post..." or "Here's a draft..." or any similar meta-commentary
- DO NOT explain what you're creating or describe the post
- START IMMEDIATELY with the actual post content (hook, first sentence, etc.)
- Write as if you're posting directly on LinkedIn
- DO NOT mention dates, years, or time-specific references

🎯 CONTENT STYLE (PERSONAL & EXPERIENCE-DRIVEN):
- Write from FIRST-PERSON perspective ("I spent...", "I learned...", "I built...")
- Share PERSONAL EXPERIENCES and REAL LESSONS LEARNED about "{topic}"
- Make it ACTIONABLE and EXPERIENCE-DRIVEN, not theoretical
- Use SHORT PARAGRAPHS or bullet points for easy skimming
- Professional, confident, and insightful tone
- End with a thoughtful question to encourage engagement
- Use emojis ONLY where they improve clarity (no overuse or decoration)

📝 CONTENT GENERATION INSTRUCTIONS:

1. **ALWAYS USE WEB SEARCH FIRST**: Use web_search tool to find REAL, CURRENT information about "{topic}"
   - Search for latest trends, tools, frameworks, or best practices
   - Find actual examples, case studies, or real-world applications
   - Get specific data, statistics, or technical details
   - Use this information to inform your personal experience narrative

2. **SHARE 3-5 PRACTICAL KEY LEARNINGS**:
   - Each learning should be from YOUR experience
   - Start each with a personal statement (e.g., "I learned...", "We discovered...", "The biggest surprise was...")
   - Include specific examples, tools, numbers, or frameworks
   - Make each learning actionable and practical
   - Use {selected_structure} to organize your content

3. **PERSONAL EXPERIENCE FOCUS**:
   - Write as if you've actually worked with "{topic}"
   - Share what surprised you (positive or negative)
   - Include specific challenges you faced and how you solved them
   - Mention real tools, frameworks, or technologies you used
   - Be honest about failures and what you learned from them

4. **FORMATTING REQUIREMENTS**:
   - Use **bold** for key points and important concepts
   - Use *italics* for emphasis or quotes
   - Use bullet points (- or *) for lists and learnings
   - Use SHORT PARAGRAPHS (2-3 sentences max) for easy skimming
   - Include [source links](URL) in markdown format for facts/claims
   - Use code formatting (`backticks`) for technical terms, tools, or technologies

5. **ENGAGEMENT ELEMENTS**:
   - Start with a personal hook (e.g., "I spent...", "I learned...", "Here's what nobody tells you...")
   - Include 2-3 emojis ONLY where they improve clarity (no decoration)
   - Add 3-5 relevant hashtags at the end
   - Write 200-300 words (optimal LinkedIn length)
   - End with a thoughtful question (e.g., "What's been your biggest surprise...?", "What tools do you recommend...?")

6. **LANGUAGE REQUIREMENT**:
   - Write ENTIRELY in {language_name} - no English, no code-switching
   - Use natural {language_name} expressions and idioms
   - Hashtags should be in {language_name} or universal format

7. **VERIFICATION**:
   - ✓ Written in FIRST-PERSON perspective
   - ✓ Shares personal experiences and real lessons learned
   - ✓ Includes 3-5 practical, actionable learnings
   - ✓ Uses short paragraphs or bullet points
   - ✓ Professional, confident, and insightful tone
   - ✓ Ends with thoughtful question
   - ✓ Emojis used only for clarity, not decoration
   - ✓ Written entirely in {language_name}
   - ✓ No dates, years, or time-specific references

🚨 OUTPUT FORMAT - CRITICAL 🚨
- START DIRECTLY with the post content (first sentence/hook)
- DO NOT write "Here's a LinkedIn post..." or "Here's a draft..." or any meta-commentary
- DO NOT explain what you're creating or describe the post
- Write as if you're posting directly on LinkedIn
- The first word should be the actual post content, not an introduction

Generate a PERSONAL, EXPERIENCE-DRIVEN LinkedIn post about "{topic}" in {language_name}. Share 3-5 practical key learnings from your experience. Start directly with the post content - no introductions or meta-commentary."""
            
            result = await self.agent.ainvoke({"input": input_text})
            content = result.get("output", "")
            
            # Remove any meta-commentary that might have slipped through
            content = self._remove_meta_commentary(content)
            
            return {
                "success": True,
                "content": content.strip(),
                "error": None
            }
        except Exception as e:
            err_str = str(e)
            if "Could not parse LLM output:" in err_str:
                import re
                match = re.search(r"Could not parse LLM output:\s*`?(.*?)`?\s*(?:For troubleshooting|$)", err_str, re.DOTALL)
                if match:
                    extracted_text = match.group(1).strip().strip("`").strip()
                    extracted_text = self._remove_meta_commentary(extracted_text)
                    if extracted_text:
                        return {
                            "success": True,
                            "content": extracted_text,
                            "error": None
                        }
            import traceback
            return {
                "success": False,
                "content": "",
                "error": f"LangChain generation failed: {str(e)}"
            }
    
    def _remove_meta_commentary(self, text: str) -> str:
        """Remove meta-commentary like 'Here's a LinkedIn post...' from generated content"""
        import re
        
        # Patterns to remove
        patterns = [
            r'^Here\'s a LinkedIn post.*?:?\s*',
            r'^Here\'s a draft.*?:?\s*',
            r'^Here is a LinkedIn post.*?:?\s*',
            r'^Here is a draft.*?:?\s*',
            r'^This is a LinkedIn post.*?:?\s*',
            r'^This LinkedIn post.*?:?\s*',
            r'^LinkedIn post draft.*?:?\s*',
            r'^designed to be engaging.*?:?\s*',
            r'^optimized for clarity.*?:?\s*',
            r'^incorporating real-world examples.*?:?\s*',
            r'^Below is.*?:?\s*',
            r'^Following is.*?:?\s*',
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove lines that are just meta-commentary
        lines = text.split('\n')
        cleaned_lines = []
        skip_next = False
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            # Skip lines that are clearly meta-commentary
            if any(phrase in line_lower for phrase in [
                "here's a linkedin",
                "here is a linkedin",
                "this is a linkedin",
                "linkedin post draft",
                "designed to be",
                "optimized for",
                "incorporating real-world",
                "below is",
                "following is"
            ]):
                continue
            
            # If we find the actual content (starts with a hook-like pattern), keep everything from here
            if line.strip() and not line.strip().startswith(('Here', 'This', 'Below', 'Following')):
                cleaned_lines.append(line)
            elif line.strip():
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    async def generate_image(self, prompt: str, topic: Optional[str] = None) -> Optional[str]:
        """Generate an image using Gemini 3 Pro Image API and upload to tmpfiles.org"""
        try:
            import base64
            from io import BytesIO
            
            # Enhanced prompt for better image generation
            enhanced_prompt = f"""Create a UNIQUE, professional, high-quality TECHNICAL image for a LinkedIn post about "{topic or prompt}".

Original prompt: {prompt}

🎨 CREATIVE DIRECTION (Make it UNIQUE and TECHNICAL):
- Style: modern technical illustration with clean lines
- Color scheme: professional blue and white palette with tech accents
- Composition: centered focal point with negative space
- Focus: TECHNICAL and PROFESSIONAL imagery (diagrams, code snippets, technical architecture, data visualizations, tech concepts)

📐 TECHNICAL REQUIREMENTS:
- High resolution (2K), crisp and clear visuals
- Professional TECHNICAL aesthetic suitable for LinkedIn
- Modern, clean design with excellent composition
- Visually striking and eye-catching
- Suitable for social media sharing
- High contrast for better visibility on LinkedIn feed
- Engaging and professional TECHNICAL appearance
- Avoid cluttered designs - keep it clean and focused
- Unique visual approach that stands out from generic stock images
- PRIORITIZE: Technical diagrams, code visualizations, architecture diagrams, data charts, tech icons, professional infographics

🚫 AVOID:
- Generic stock photo look
- Overused visual clichés
- Cluttered or busy designs
- Low contrast or hard-to-read elements
- Unprofessional or casual styles
- Non-technical imagery (people, landscapes, abstract art without technical context)

✨ MAKE IT TECHNICAL AND UNIQUE:
- Use creative visual metaphors related to "{topic or prompt}" with TECHNICAL elements
- Incorporate technical design elements (code, diagrams, charts, architecture)
- Create a memorable TECHNICAL visual identity
- Ensure it's different from typical LinkedIn post images
- Focus on technical concepts, tools, technologies, or professional insights"""
            
            # Make API request to Gemini 3 Pro Image
            async with aiohttp.ClientSession() as session:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.image_model}:generateContent?key={self.gemini_api_key}"
                
                payload = {
                    "contents": [{
                        "parts": [{"text": enhanced_prompt}]
                    }],
                    "generationConfig": {
                        "imageConfig": {
                            "aspectRatio": "1:1",
                            "imageSize": "2K"
                        }
                    }
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.gemini_api_key
                }
                
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Gemini API request failed with status {response.status}: {error_text}")
                        return None
                    
                    data = await response.json()
                    
                    if 'candidates' not in data or not data['candidates']:
                        print("No candidates in Gemini API response")
                        return None
                    
                    candidate = data['candidates'][0]
                    content = candidate.get('content', {})
                    
                    # Extract image data
                    image_data = None
                    content_type = 'image/png'
                    
                    for part in content.get('parts', []):
                        inline_data = part.get('inlineData') or part.get('inline_data')
                        if inline_data:
                            base64_data = inline_data.get('data')
                            if base64_data:
                                image_data = base64.b64decode(base64_data)
                                content_type = inline_data.get('mimeType') or inline_data.get('mime_type', 'image/png')
                                break
                    
                    if not image_data:
                        print("No image data in Gemini API response")
                        return None
                    
                    # Upload to tmpfiles.org
                    return await self._upload_to_tmpfiles(image_data, content_type)
                    
        except Exception as e:
            print(f"Error generating image: {str(e)}")
            return None
    
    async def _upload_to_tmpfiles(self, image_data: bytes, content_type: str) -> Optional[str]:
        """Upload image to tmpfiles.org and return the download URL"""
        try:
            import asyncio
            
            # Determine file extension from content type
            ext_map = {
                "image/png": "png",
                "image/jpeg": "jpg",
                "image/jpg": "jpg",
                "image/gif": "gif",
                "image/webp": "webp"
            }
            ext = ext_map.get(content_type, "png")
            
            # Retry logic for upload
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    timeout = aiohttp.ClientTimeout(total=60)
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        form_data = aiohttp.FormData()
                        file_obj = BytesIO(image_data)
                        form_data.add_field('file', 
                                          file_obj, 
                                          filename=f"gemini_image.{ext}", 
                                          content_type=content_type)
                        
                        async with session.post(self.tmpfiles_api_url, data=form_data) as response:
                            if response.status == 200:
                                result = await response.json()
                                
                                # Handle different response formats
                                if isinstance(result, dict):
                                    if "status" in result and result.get("status") == "success":
                                        if "data" in result and isinstance(result["data"], dict):
                                            file_url = result["data"].get("url", "")
                                        else:
                                            file_url = result.get("url", "")
                                    else:
                                        file_url = result.get("url", "")
                                    
                                    if file_url:
                                        # Convert to direct download link
                                        download_url = file_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                                        if download_url.startswith("http://"):
                                            download_url = download_url.replace("http://", "https://", 1)
                                        return download_url
                                
                                # If response is a string URL
                                if isinstance(result, str):
                                    file_url = result
                                    download_url = file_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                                    if download_url.startswith("http://"):
                                        download_url = download_url.replace("http://", "https://", 1)
                                    return download_url
                            else:
                                error_text = await response.text()
                                print(f"tmpfiles.org upload failed with status {response.status}: {error_text}")
                                
                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        print(f"Failed to upload to tmpfiles.org after {max_retries} attempts: {str(e)}")
                        return None
                except Exception as e:
                    print(f"Failed to upload to tmpfiles.org: {str(e)}")
                    return None
            
            print(f"Failed to upload to tmpfiles.org after {max_retries} attempts")
            return None
            
        except Exception as e:
            print(f"Error in _upload_to_tmpfiles: {str(e)}")
            return None
