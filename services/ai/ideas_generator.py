"""Enhanced LangChain integration for AI post generation with web search and image generation"""
from typing import Dict, Optional, List
import os
import aiohttp
import json
from dotenv import load_dotenv

load_dotenv()

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import Tool
from langchain_core.prompts import ChatPromptTemplate

# Import agent executor
create_agent = None
AgentExecutor = None
AgentType = None
USE_CREATE_AGENT = False

try:
    from langchain.agents import create_agent
    from langchain.agents import AgentType
    USE_CREATE_AGENT = True
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
    """Enhanced LangChain-based AI post generation with web search and image generation"""
    
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash-lite",
            google_api_key=self.gemini_api_key,
            temperature=0.8,  # Higher temperature for more creative, personal content
        )
        self.tools = self._create_tools()
        self.agent = self._create_agent()
    
    def _create_tools(self):
        """Create LangChain tools for web search and content generation"""
        self_ref = self
        
        def web_search_sync(query: str) -> str:
            """Sync wrapper for web search"""
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
                description="Search the web for real-time, current information about tech trends, programming topics, tools, and latest developments. Always use this to find factual, up-to-date information with sources and links.",
                func=web_search_sync
            )
        ]
    
    async def _web_search_async(self, query: str) -> str:
        """Async web search using Gemini's googleSearch tool with enhanced results"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_api_key}"
                
                payload = {
                    "contents": [{
                        "parts": [{"text": f"Search web for LATEST INFORMATION about: {query}\n\nProvide:\n1. Most recent news/updates\n2. Official sources and links\n3. Key statistics or data\n4. Real-world examples\n5. Source URLs"}]
                    }],
                    "tools": [{"googleSearch": {}}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 1500,
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
                prompt = ChatPromptTemplate.from_messages([
                    ("system", self._get_system_prompt()),
                    ("human", "{input}"),
                ])
                
                agent = create_agent(self.llm, self.tools, prompt)
                if hasattr(agent, 'ainvoke'):
                    return agent
                if AgentExecutor:
                    return AgentExecutor(agent=agent, tools=self.tools, verbose=False, max_iterations=3)
                return agent
            else:
                from langchain.agents import initialize_agent, AgentType
                return initialize_agent(
                    self.tools,
                    self.llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=False,
                    max_iterations=3
                )
        except Exception:
            try:
                from langchain.agents import initialize_agent, AgentType
                return initialize_agent(
                    self.tools,
                    self.llm,
                    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
                    verbose=False,
                    max_iterations=3
                )
            except Exception:
                return None
    
    def _get_system_prompt(self) -> str:
        """Enhanced system prompt for personal, authentic tech content"""
        return """You are an authentic tech creator who shares PERSONAL EXPERIENCES and GENUINE INSIGHTS - NOT generic ChatGPT content.

🎯 YOUR UNIQUE VOICE:
- Share YOUR perspective, not regurgitated common knowledge
- Write like you're talking to peers, not lecturing
- Include personal lessons learned and failures, not just wins
- Be specific with technical details and real examples
- Show genuine passion for tech topics

🚨 CRITICAL RULES:
- NO meta-commentary ("Here's a post...", "Here's a draft...")
- NO generic advice or buzzwords
- START DIRECTLY with authentic content
- NO ChatGPT-like corporate tone
- Write naturally, like a real human

📚 CONTENT REQUIREMENTS:
- ALWAYS use web_search to find REAL, LATEST information
- Include personal experience with the topic
- Share specific technical details and real tools/projects
- Link to sources and references
- Focus on actionable insights
- Use conversational, authentic language

✨ WHAT MAKES IT AUTHENTIC:
- Share what YOU actually learned
- Include specific numbers, frameworks, or tools YOU use
- Mention real projects or experiences (anonymized if needed)
- Be honest about challenges and failures
- Show real technical depth, not surface-level understanding"""
    
    async def generate_post(self, topic: str, language: str = "en", personal_context: Optional[str] = None) -> Dict:
        """
        Generate LinkedIn post with personal touch and web search
        
        Args:
            topic: The post topic
            language: Language code (en, fr, es, etc.)
            personal_context: Optional personal experience or context to include
        """
        try:
            language_map = {
                'en': 'English', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian',
                'de': 'German', 'pt': 'Portuguese', 'nl': 'Dutch', 'hi': 'Hindi'
            }
            language_name = language_map.get(language, 'English')
            
            if self.agent:
                return await self._generate_with_langchain(topic, language_name, personal_context)
            else:
                return await self._generate_direct_fallback(topic, language_name, personal_context)
        except Exception as e:
            import traceback
            return {
                "success": False,
                "content": "",
                "error": f"{str(e)}\n{traceback.format_exc()}"
            }
    
    async def _generate_direct_fallback(self, topic: str, language_name: str, personal_context: Optional[str] = None) -> Dict:
        """Fallback generation with enhanced personal content prompt"""
        personal_instruction = f"\n\nPERSONAL CONTEXT: {personal_context}" if personal_context else ""
        
        prompt = f"""You are an authentic tech creator sharing PERSONAL EXPERIENCES and GENUINE INSIGHTS.
TOPIC: "{topic}"{personal_instruction}

🚨 CRITICAL: Generate authentic, personal content - NOT generic ChatGPT-like posts
- Share YOUR perspective and personal experience
- Include specific technical details and real examples
- Avoid buzzwords and generic advice
- Write naturally like talking to peers
- START DIRECTLY with content (no introductions)

INSTRUCTIONS:
1. SEARCH FIRST: Use web_search to find latest information about "{topic}"
2. ADD PERSONAL TOUCH: Include your own experience, lessons learned, or specific technical insights
3. BE SPECIFIC: Use real tools, frameworks, projects, numbers, or technical details
4. AUTHENTIC TONE: Write conversationally, not like corporate content
5. INCLUDE SOURCES: Link all facts and information with markdown [Source](URL)

FORMAT:
- **bold** for key points
- `code` for technical terms and tools
- 200-300 words
- 3-5 relevant hashtags
- 1-2 strategic emojis
- Start with hook, end with question/CTA
- Write ENTIRELY in {language_name}

OUTPUT: Start directly with post content - no meta-commentary or explanations."""
        
        async with aiohttp.ClientSession() as session:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_api_key}"
            
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"googleSearch": {}}],
                "generationConfig": {
                    "temperature": 0.85,
                    "maxOutputTokens": 2048,
                }
            }
            
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return {
                        "success": False,
                        "content": "",
                        "error": f"API error: {resp.status} - {error_text}"
                    }
                
                data = await resp.json()
                
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        text_parts = []
                        for part in candidate["content"]["parts"]:
                            if "text" in part:
                                text_parts.append(part["text"])
                        
                        content = "\n".join(text_parts)
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
    
    async def _generate_with_langchain(self, topic: str, language_name: str, personal_context: Optional[str] = None) -> Dict:
        """Enhanced generation with personal context support"""
        try:
            import random
            
            # Varied hooks for authentic content
            hooks = [
                "Share a personal insight or lesson learned",
                "Start with a surprising technical discovery",
                "Begin with a real problem you faced",
                "Open with a contrarian take",
                "Start with specific technical depth",
                "Begin with a personal 'aha moment'"
            ]
            
            structures = [
                "Personal experience + Technical insight format",
                "Problem I faced, Solution I found, Lessons learned",
                "Real example from my work + Key takeaways",
                "Specific technical details + Practical application",
                "Challenge I overcame + Actionable advice",
                "Technical deep-dive + Personal perspective"
            ]
            
            ctas = [
                "Ask what others have experienced with this",
                "Invite others to share their approach",
                "Ask for feedback or counter-opinions",
                "Challenge readers with a question",
                "Ask what tools they recommend",
                "Invite specific recommendations or experiences"
            ]
            
            selected_hook = random.choice(hooks)
            selected_structure = random.choice(structures)
            selected_cta = random.choice(ctas)
            
            personal_section = f"\n\nYOUR PERSONAL CONTEXT/EXPERIENCE:\n{personal_context}" if personal_context else ""
            
            input_text = f"""Generate an AUTHENTIC, PERSONAL tech LinkedIn post:

TOPIC: "{topic}"{personal_section}

🎯 BE AUTHENTIC AND PERSONAL - NOT GENERIC:
Your voice: Real person sharing genuine insights, NOT ChatGPT corporate tone
- Include personal experience, lessons learned, or specific insights
- Share real technical details and specific tools/projects you use
- Be honest about challenges and learning journey
- Write conversationally like talking to tech peers

🚨 CRITICAL - START DIRECTLY WITH CONTENT:
- NO "Here's a post..." or meta-commentary
- First words are actual post content
- Write as if posting directly to LinkedIn

📝 CONTENT STRUCTURE ({selected_structure}):
1. {selected_hook}
2. Use web_search to find LATEST information about "{topic}"
3. Add YOUR personal perspective and experience
4. Include specific technical details, real tools, or examples
5. {selected_cta}

📋 FORMAT REQUIREMENTS:
- Use **bold** for key technical concepts
- Use `code` for tools, frameworks, languages, libraries
- Include [Source links](URL) for all facts
- 200-300 words
- Strategic placement of 1-2 emojis
- 3-5 relevant hashtags
- Conversational, authentic language
- ENTIRELY in {language_name}

✅ AUTHENTICITY CHECKLIST:
- Shares personal experience or perspective? ✓
- Includes specific technical details? ✓
- Uses real tools/projects/numbers? ✓
- Avoids generic corporate language? ✓
- Conversational tone like real person? ✓
- Includes web search results? ✓

Generate UNIQUE, AUTHENTIC content starting directly with the post."""
            
            result = await self.agent.ainvoke({"input": input_text})
            content = result.get("output", "")
            content = self._remove_meta_commentary(content)
            
            return {
                "success": True,
                "content": content.strip(),
                "error": None
            }
        except Exception as e:
            import traceback
            return {
                "success": False,
                "content": "",
                "error": f"Generation failed: {str(e)}\n{traceback.format_exc()}"
            }
    
    async def generate_image_prompt(self, post_content: str) -> str:
        """
        NEW: Generate an optimized image prompt for the post content
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_api_key}"
                
                prompt = f"""Based on this tech LinkedIn post, create a PROFESSIONAL, CLEAN image prompt for generating a featured image.

POST CONTENT:
{post_content}

REQUIREMENTS:
- Describe a professional, minimalist tech-themed image
- Include relevant visual elements (code, tech symbols, charts if applicable)
- Use a modern, professional color scheme (blues, teals, grays, with accent color)
- Style: Clean, modern, professional
- NO people, NO stock photo vibes, NO cartoons
- Should look like professional tech blog/LinkedIn featured image
- Include specific technical visual elements related to the post topic

RESPOND WITH ONLY THE IMAGE PROMPT (no explanations)"""
                
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": 256,
                    }
                }
                
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "candidates" in data and len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                for part in candidate["content"]["parts"]:
                                    if "text" in part:
                                        return part["text"].strip()
            return ""
        except Exception:
            return ""
    
    def _remove_meta_commentary(self, text: str) -> str:
        """Remove meta-commentary from generated content"""
        import re
        
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
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line_lower = line.lower().strip()
            if any(phrase in line_lower for phrase in [
                "here's a linkedin", "here is a linkedin", "this is a linkedin",
                "linkedin post draft", "designed to be", "optimized for",
                "incorporating real-world", "below is", "following is"
            ]):
                continue
            
            if line.strip() and not line.strip().startswith(('Here', 'This', 'Below', 'Following')):
                cleaned_lines.append(line)
            elif line.strip():
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    async def generate(self, industry: Optional[str] = None, topic: Optional[str] = None, prompt: Optional[str] = None, count: int = 5, language: str = "en") -> Dict:
        """Generate LinkedIn post ideas optimized for content creators and tech professionals"""
        try:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                return {"error": "GEMINI_API_KEY not found"}
            
            url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
            
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            }
            
            # Create a comprehensive prompt for generating post ideas
            ideas_prompt = f"""
            Generate {count} LinkedIn post ideas for content creators and tech professionals.
            
            Parameters:
            - Industry: {industry or 'General'}
            - Topic: {topic or 'General'}
            - Custom prompt: {prompt or 'None'}
            - Language: {language}
            
            Requirements:
            1. Each idea should be engaging and professional
            2. Ideas should be suitable for LinkedIn audience
            3. Include a mix of content types (tips, insights, questions, stories)
            4. Each idea should be 1-2 sentences long
            5. Focus on value-driven content that encourages engagement
            6. Ideas should be actionable or thought-provoking
            
            Format the response as a numbered list of {count} ideas.
            """
            
            payload = {
                "contents": [{
                    "parts": [{
                        "text": ideas_prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.8,
                    "maxOutputTokens": 1000
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'candidates' in data and len(data['candidates']) > 0:
                            content = data['candidates'][0]['content']['parts'][0]['text']
                            
                            # Parse the ideas from the response
                            ideas = []
                            lines = content.strip().split('\n')
                            
                            for line in lines:
                                line = line.strip()
                                # Remove numbering and bullet points
                                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                                    idea = line
                                    # Remove numbering at the start
                                    if line[0].isdigit():
                                        idea = line.split('.', 1)[1].strip() if '.' in line else line
                                    elif line.startswith('-') or line.startswith('•'):
                                        idea = line[1:].strip()
                                    
                                    if idea and len(idea) > 10:  # Filter out very short lines
                                        ideas.append(idea)
                            
                            # Ensure we have the requested number of ideas
                            while len(ideas) < count:
                                ideas.append(f"Engaging post idea about {topic or industry or 'business'}")
                            
                            return {
                                "ideas": ideas[:count],
                                "error": None
                            }
                    else:
                        error_text = await response.text()
                        return {"error": f"Gemini API error: {response.status} - {error_text}"}
                        
        except Exception as e:
            return {"error": f"Error generating ideas: {str(e)}"}
    
    async def extract_url_to_post(self, url: str, language: str = "en") -> Dict:
        """Extract content from URL and convert to LinkedIn post"""
        try:
            import re
            from html import unescape
            
            # Fetch URL content
            async with aiohttp.ClientSession() as session:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        return {"error": f"Failed to fetch URL: HTTP {resp.status}"}
                    
                    html_content = await resp.text()
                    html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                    html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                    
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
                    title = unescape(title_match.group(1).strip()) if title_match else None
                    
                    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.IGNORECASE | re.DOTALL)
                    body_content = body_match.group(1) if body_match else html_content
                    
                    # Clean HTML tags
                    clean_text = re.sub(r'<[^>]+>', '\n', body_content)
                    clean_text = re.sub(r'\n+', '\n', clean_text).strip()
                    
                    # Limit text length
                    if len(clean_text) > 3000:
                        clean_text = clean_text[:3000] + "..."
                    
                    # Generate LinkedIn post using Gemini
                    language_map = {
                        'en': 'English', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian',
                        'de': 'German', 'pt': 'Portuguese', 'nl': 'Dutch',
                    }
                    language_name = language_map.get(language, 'English')
                    
                    prompt = f"""Convert this web content into a professional LinkedIn post in {language_name}.

Title: {title or 'No title'}

Content:
{clean_text}

Requirements:
- Write as if you personally discovered this content
- Share your genuine insights and takeaways
- Make it conversational and authentic
- Include relevant hashtags
- Keep it under 300 words
- Start with the content directly (no "Here's a post about...")
- Focus on what professionals would find valuable

Return JSON format:
{{
  "text": "the post content here written COMPLETELY in {language_name}, starting directly with the content",
  "hashtags": ["#hashtag1", "#hashtag2", ...]
}}"""

                    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={self.gemini_api_key}"
                    
                    headers = {"Content-Type": "application/json"}
                    payload = {"contents": [{"parts": [{"text": prompt}]}]}
                    
                    async with aiohttp.ClientSession() as gemini_session:
                        async with gemini_session.post(
                            gemini_url,
                            json=payload,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=120)
                        ) as gemini_resp:
                            if gemini_resp.status == 200:
                                resp_json = await gemini_resp.json()
                                if "candidates" in resp_json and len(resp_json["candidates"]) > 0:
                                    response_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                                    
                                    try:
                                        json_match = re.search(r'\{[\s\S]*\}', response_text)
                                        if json_match:
                                            parsed = json.loads(json_match.group(0))
                                        else:
                                            parsed = json.loads(response_text)
                                    except:
                                        hashtags = re.findall(r'#\w+', response_text) or []
                                        text = re.sub(r'\{[\s\S]*\}', '', response_text).strip()
                                        parsed = {
                                            "text": text or response_text,
                                            "hashtags": hashtags[:5],
                                        }
                                    
                                    result = {
                                        "text": parsed.get("text", response_text),
                                        "hashtags": parsed.get("hashtags", []),
                                        "source_url": url,
                                        "source_title": title,
                                    }
                                    
                                    return result
                                else:
                                    return {"error": "Failed to generate post from URL content"}
                            else:
                                error_text = await gemini_resp.text()
                                return {"error": f"API error: {error_text}"}
                                
        except Exception as e:
            return {"error": f"Error extracting URL: {str(e)}"}
