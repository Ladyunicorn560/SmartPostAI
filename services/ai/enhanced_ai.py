import os
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import Tool
from langchain_core.messages import HumanMessage, AIMessage
import google.generativeai as genai
import json
import time

class EnhancedAIService:
    """Enhanced AI Service using LangChain for smarter LinkedIn content generation"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        # Initialize LangChain with Gemini
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            google_api_key=self.api_key,
            temperature=0.7,
            max_tokens=2048
        )
        
        # Initialize memory for conversation context
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Setup specialized prompts
        self.setup_prompts()
        
        # Setup tools for agent
        self.setup_tools()
        
        # Create agent for complex tasks
        self.setup_agent()
    
    def setup_prompts(self):
        """Setup specialized prompts for different content types"""
        
        # LinkedIn post generation prompt
        self.linkedin_post_prompt = PromptTemplate(
            input_variables=["topic", "tone", "audience", "length"],
            template="""
You are a professional LinkedIn content creator. Create an engaging LinkedIn post about: {topic}

Requirements:
- Tone: {tone}
- Target Audience: {audience}
- Length: {length} words
- Include relevant hashtags
- Make it engaging and professional
- Add a call-to-action if appropriate

Format the post professionally for LinkedIn.
"""
        )
        
        # Post ideas generation prompt
        self.ideas_prompt = PromptTemplate(
            input_variables=["industry", "target_audience", "content_goals"],
            template="""
Generate 10 creative LinkedIn post ideas for:
- Industry: {industry}
- Target Audience: {target_audience}
- Content Goals: {content_goals}

For each idea, provide:
1. Catchy title/hook
2. Brief description
3. Best posting time
4. Suggested hashtags

Make the ideas actionable and engaging.
"""
        )
        
        # URL to post conversion prompt
        self.url_conversion_prompt = PromptTemplate(
            input_variables=["url", "angle"],
            template="""
Convert the content from this URL into an engaging LinkedIn post: {url}

Angle/Focus: {angle}

Requirements:
- Extract key insights
- Make it professional and engaging
- Add personal perspective
- Include relevant hashtags
- Keep it under 300 words

Create a compelling LinkedIn post that adds value to the original content.
"""
        )
    
    def setup_tools(self):
        """Setup tools for the LangChain agent"""
        
        def research_topic(topic: str) -> str:
            """Research tool for getting background information"""
            # This could integrate with a search API or news API
            research_prompt = ChatPromptTemplate.from_template(
                "Provide key insights and trends about: {topic}. "
                "Focus on recent developments and professional perspectives."
            )
            chain = LLMChain(llm=self.llm, prompt=research_prompt)
            return chain.run(topic=topic)
        
        def generate_hashtags(content: str) -> str:
            """Generate relevant hashtags for content"""
            hashtag_prompt = ChatPromptTemplate.from_template(
                "Generate 5-7 relevant hashtags for this LinkedIn content: {content}. "
                "Focus on trending and industry-specific hashtags."
            )
            chain = LLMChain(llm=self.llm, prompt=hashtag_prompt)
            return chain.run(content=content)
        
        def optimize_for_engagement(post: str) -> str:
            """Optimize post for better engagement"""
            optimize_prompt = ChatPromptTemplate.from_template(
                "Optimize this LinkedIn post for maximum engagement: {post}. "
                "Add questions, improve hooks, and make it more interactive."
            )
            chain = LLMChain(llm=self.llm, prompt=optimize_prompt)
            return chain.run(content=post)
        
        self.tools = [
            Tool(
                name="research_topic",
                description="Research background information about a topic",
                func=research_topic
            ),
            Tool(
                name="generate_hashtags",
                description="Generate relevant hashtags for LinkedIn content",
                func=generate_hashtags
            ),
            Tool(
                name="optimize_engagement",
                description="Optimize content for better engagement",
                func=optimize_for_engagement
            )
        ]
    
    def setup_agent(self):
        """Setup the LangChain agent for complex content creation"""
        
        agent_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert LinkedIn content creator and social media strategist.
            You have access to tools for research, hashtag generation, and engagement optimization.
            Create professional, engaging LinkedIn content that drives results.
            Always consider the target audience and platform best practices."""),
            ("human", "{input}"),
            ("assistant", "Let me create amazing LinkedIn content for you!"),
            ("placeholder", "{agent_scratchpad}")
        ])
        
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=agent_prompt
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            memory=self.memory
        )
    
    async def generate_linkedin_post_with_agent(
        self, 
        topic: str, 
        tone: str = "professional",
        audience: str = "professionals",
        length: str = "200-300",
        use_agent: bool = True
    ) -> Dict[str, Any]:
        """Generate LinkedIn post using LangChain agent"""
        
        try:
            if use_agent:
                # Use agent for intelligent content creation
                agent_input = f"""
                Create a LinkedIn post about: {topic}
                Tone: {tone}
                Audience: {audience}
                Length: {length} words
                
                Use your tools to research the topic, generate relevant hashtags, and optimize for engagement.
                """
                
                result = await self.agent_executor.ainvoke({"input": agent_input})
                post_content = result.get("output", "")
                
            else:
                # Use simple chain for basic generation
                chain = LLMChain(llm=self.llm, prompt=self.linkedin_post_prompt)
                post_content = chain.run(
                    topic=topic,
                    tone=tone,
                    audience=audience,
                    length=length
                )
            
            return {
                "success": True,
                "content": post_content.strip(),
                "metadata": {
                    "topic": topic,
                    "tone": tone,
                    "audience": audience,
                    "generated_with": "agent" if use_agent else "chain"
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_post_ideas_with_research(
        self, 
        industry: str, 
        target_audience: str, 
        content_goals: str
    ) -> Dict[str, Any]:
        """Generate post ideas with research using LangChain"""
        
        try:
            # Use agent to research and generate ideas
            agent_input = f"""
            Generate 10 creative LinkedIn post ideas for:
            Industry: {industry}
            Target Audience: {target_audience}
            Content Goals: {content_goals}
            
            Research current trends in this industry and create actionable, engaging ideas.
            Use your tools to gather insights and optimize the ideas.
            """
            
            result = await self.agent_executor.ainvoke({"input": agent_input})
            ideas = result.get("output", "")
            
            return {
                "success": True,
                "ideas": ideas.strip(),
                "metadata": {
                    "industry": industry,
                    "target_audience": target_audience,
                    "content_goals": content_goals
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def convert_url_to_post_intelligent(
        self, 
        url: str, 
        angle: str = "professional insights"
    ) -> Dict[str, Any]:
        """Convert URL to LinkedIn post with intelligent analysis"""
        
        try:
            # Use agent for intelligent URL conversion
            agent_input = f"""
            Convert this URL into an engaging LinkedIn post: {url}
            Focus angle: {angle}
            
            Research the content, extract key insights, and create a professional LinkedIn post
            that adds value beyond just sharing the link. Use your tools to optimize engagement.
            """
            
            result = await self.agent_executor.ainvoke({"input": agent_input})
            post_content = result.get("output", "")
            
            return {
                "success": True,
                "content": post_content.strip(),
                "original_url": url,
                "angle": angle
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_conversation_memory(self) -> List[Dict]:
        """Get conversation history"""
        return [
            {"type": type(msg).__name__, "content": msg.content}
            for msg in self.memory.chat_memory.messages
        ]
    
    def clear_memory(self):
        """Clear conversation memory"""
        self.memory.clear()
