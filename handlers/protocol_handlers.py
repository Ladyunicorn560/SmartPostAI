"""Protocol message handlers"""
from enum import Enum
from uagents import Context, Model
from uagents.experimental.quota import QuotaProtocol, RateLimit
from protocol import (
    GeneratePostRequest,
    GeneratePostResponse,
    GenerateImageRequest,
    GenerateImageResponse,
    LinkedInAuthRequest,
    LinkedInAuthResponse,
    LinkedInCallbackRequest,
    LinkedInCallbackResponse,
    LinkedInPostRequest,
    LinkedInPostResponse,
    LinkedInAIPostRequest,
    LinkedInAIPostResponse,
    LinkedInConnectionStatusRequest,
    LinkedInConnectionStatusResponse,
    CreateScheduleRequest,
    CreateScheduleResponse,
    GetSchedulesRequest,
    GetSchedulesResponse,
    ScheduleActionRequest,
    ScheduleActionResponse,
    CreateTaskRequest,
    CreateTaskResponse,
    GetTasksRequest,
    GetTasksResponse,
    GetTaskRequest,
    GetTaskResponse,
    UpdateTaskRequest,
    UpdateTaskResponse,
    DeleteTaskRequest,
    DeleteTaskResponse,
)
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent, StartSessionContent, EndSessionContent, ChatAcknowledgement

def register_protocol_handlers(agent, ai_service, linkedin_service, scheduler_service, tasks_service):
    """Register all protocol message handlers"""
    
    # ==================== AI PROTOCOL ====================
    ai_protocol = QuotaProtocol(
        storage_reference=agent.storage,
        name="AI-Service-Protocol",
        version="0.1.0",
        default_rate_limit=RateLimit(window_size_minutes=60, max_requests=100),
    )
    
    @ai_protocol.on_message(GeneratePostRequest, replies={GeneratePostResponse})
    async def handle_generate_post(ctx: Context, sender: str, msg: GeneratePostRequest):
        try:
            result = await ai_service.generate_linkedin_post(
                msg.topic,
                msg.include_hashtags,
                msg.language
            )
            if "error" in result:
                await ctx.send(sender, GeneratePostResponse(error=result["error"]))
            else:
                await ctx.send(sender, GeneratePostResponse(
                    text=result["text"],
                    hashtags=result.get("hashtags", []),
                ))
        except Exception as e:
            await ctx.send(sender, GeneratePostResponse(error=str(e)))
    
    @ai_protocol.on_message(GenerateImageRequest, replies={GenerateImageResponse})
    async def handle_generate_image(ctx: Context, sender: str, msg: GenerateImageRequest):
        try:
            image_prompt = await ai_service.generate_image_prompt(msg.topic)
            image_url = await ai_service.generate_image(image_prompt, ctx=ctx)
            
            if image_url:
                await ctx.send(sender, GenerateImageResponse(
                    image_prompt=image_prompt,
                    image_url=image_url,
                ))
            else:
                await ctx.send(sender, GenerateImageResponse(
                    image_prompt=image_prompt,
                    error="Image generation failed"
                ))
        except Exception as e:
            await ctx.send(sender, GenerateImageResponse(image_prompt="", error=str(e)))
    
    # ==================== LINKEDIN PROTOCOL ====================
    linkedin_protocol = QuotaProtocol(
        storage_reference=agent.storage,
        name="LinkedIn-Service-Protocol",
        version="0.1.0",
        default_rate_limit=RateLimit(window_size_minutes=60, max_requests=50),
    )
    
    @linkedin_protocol.on_message(LinkedInAuthRequest, replies={LinkedInAuthResponse})
    async def handle_linkedin_auth(ctx: Context, sender: str, msg: LinkedInAuthRequest):
        try:
            result = linkedin_service.generate_auth_url(msg.user_id)
            await ctx.send(sender, LinkedInAuthResponse(auth_url=result["auth_url"]))
        except Exception as e:
            await ctx.send(sender, LinkedInAuthResponse(auth_url="", error=str(e)))
    
    @linkedin_protocol.on_message(LinkedInCallbackRequest, replies={LinkedInCallbackResponse})
    async def handle_linkedin_callback(ctx: Context, sender: str, msg: LinkedInCallbackRequest):
        try:
            result = await linkedin_service.handle_callback(msg.code, msg.state)
            await ctx.send(sender, LinkedInCallbackResponse(
                message=result.get("message", ""),
                profile=result.get("profile"),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, LinkedInCallbackResponse(message="", error=str(e)))
    
    @linkedin_protocol.on_message(LinkedInPostRequest, replies={LinkedInPostResponse})
    async def handle_linkedin_post(ctx: Context, sender: str, msg: LinkedInPostRequest):
        try:
            if msg.image_base64:
                result = await linkedin_service.post_with_image(msg.user_id, msg.text, msg.image_base64)
            else:
                result = await linkedin_service.post_text(msg.user_id, msg.text)
            
            await ctx.send(sender, LinkedInPostResponse(
                message=result.get("message", ""),
                post_id=result.get("post_id"),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, LinkedInPostResponse(message="", error=str(e)))
    
    @linkedin_protocol.on_message(LinkedInAIPostRequest, replies={LinkedInAIPostResponse})
    async def handle_linkedin_ai_post(ctx: Context, sender: str, msg: LinkedInAIPostRequest):
        try:
            result = await ai_service.generate_linkedin_post_with_image(
                msg.topic,
                msg.include_image,
                msg.language,
                ctx=ctx  # Pass ctx for proper image URL handling
            )
            
            if "error" in result:
                await ctx.send(sender, LinkedInAIPostResponse(error=result["error"]))
            else:
                full_text = result["text"]
                if result.get("hashtags"):
                    full_text += "\n\n" + " ".join(result["hashtags"])
                
                await ctx.send(sender, LinkedInAIPostResponse(
                    text=full_text,
                    hashtags=result.get("hashtags", []),
                    image_url=result.get("image_url"),  # URL from agent, not base64
                ))
        except Exception as e:
            await ctx.send(sender, LinkedInAIPostResponse(text="", error=str(e)))
    
    @linkedin_protocol.on_message(LinkedInConnectionStatusRequest, replies={LinkedInConnectionStatusResponse})
    async def handle_linkedin_status(ctx: Context, sender: str, msg: LinkedInConnectionStatusRequest):
        try:
            result = await linkedin_service.get_connection_status(msg.user_id)
            await ctx.send(sender, LinkedInConnectionStatusResponse(
                is_connected=result.get("is_connected", False),
                profile=result.get("profile"),
                expires_at=result.get("expires_at"),
            ))
        except Exception as e:
            await ctx.send(sender, LinkedInConnectionStatusResponse(is_connected=False, error=str(e)))
    
    # ==================== SCHEDULER PROTOCOL ====================
    scheduler_protocol = QuotaProtocol(
        storage_reference=agent.storage,
        name="Scheduler-Service-Protocol",
        version="0.1.0",
        default_rate_limit=RateLimit(window_size_minutes=60, max_requests=30),
    )
    
    @scheduler_protocol.on_message(CreateScheduleRequest, replies={CreateScheduleResponse})
    async def handle_create_schedule(ctx: Context, sender: str, msg: CreateScheduleRequest):
        try:
            # If include_image is True, generate image URL first
            image_url = None
            if msg.include_image:
                try:
                    image_prompt = await ai_service.generate_image_prompt(msg.topic)
                    image_url = await ai_service.generate_image(image_prompt, topic=msg.topic, ctx=ctx)
                    if image_url:
                        pass
                    else:
                        pass
                except Exception as img_error:
                    pass
                    # Continue without image - will generate on execution
            
            result = await scheduler_service.create_scheduled_post(
                msg.user_id,
                msg.topic,
                msg.schedule,
                msg.include_image,
                msg.custom_text,
                image_url=image_url  # Pass generated image URL
            )
            await ctx.send(sender, CreateScheduleResponse(
                message=result.get("message", ""),
                schedule_id=result.get("schedule_id"),
                next_post_at=result.get("next_post_at"),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, CreateScheduleResponse(message="", error=str(e)))
    
    @scheduler_protocol.on_message(GetSchedulesRequest, replies={GetSchedulesResponse})
    async def handle_get_schedules(ctx: Context, sender: str, msg: GetSchedulesRequest):
        try:
            result = await scheduler_service.get_scheduled_posts(msg.user_id)
            await ctx.send(sender, GetSchedulesResponse(
                schedules=result.get("schedules", []),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, GetSchedulesResponse(schedules=[], error=str(e)))
    
    @scheduler_protocol.on_message(ScheduleActionRequest, replies={ScheduleActionResponse})
    async def handle_schedule_action(ctx: Context, sender: str, msg: ScheduleActionRequest):
        try:
            if msg.action == "activate":
                result = await scheduler_service.activate_schedule(msg.user_id, msg.schedule_id)
            elif msg.action == "deactivate":
                result = await scheduler_service.deactivate_schedule(msg.user_id, msg.schedule_id)
            elif msg.action == "delete":
                result = await scheduler_service.delete_schedule(msg.user_id, msg.schedule_id)
            else:
                result = {"error": "Invalid action"}
            
            await ctx.send(sender, ScheduleActionResponse(
                message=result.get("message", ""),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, ScheduleActionResponse(message="", error=str(e)))
    
    # ==================== TASKS PROTOCOL ====================
    tasks_protocol = QuotaProtocol(
        storage_reference=agent.storage,
        name="Tasks-Service-Protocol",
        version="0.1.0",
        default_rate_limit=RateLimit(window_size_minutes=60, max_requests=100),
    )
    
    @tasks_protocol.on_message(CreateTaskRequest, replies={CreateTaskResponse})
    async def handle_create_task(ctx: Context, sender: str, msg: CreateTaskRequest):
        try:
            task_data = {
                "title": msg.title,
                "description": msg.description,
                "status": msg.status,
            }
            result = await tasks_service.create_task(msg.user_id, msg.db_name, task_data)
            await ctx.send(sender, CreateTaskResponse(
                message=result.get("message", ""),
                task_id=result.get("task_id"),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, CreateTaskResponse(message="", error=str(e)))
    
    @tasks_protocol.on_message(GetTasksRequest, replies={GetTasksResponse})
    async def handle_get_tasks(ctx: Context, sender: str, msg: GetTasksRequest):
        try:
            result = await tasks_service.get_all_tasks(msg.user_id, msg.db_name)
            await ctx.send(sender, GetTasksResponse(
                tasks=result.get("tasks", []),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, GetTasksResponse(tasks=[], error=str(e)))
    
    @tasks_protocol.on_message(GetTaskRequest, replies={GetTaskResponse})
    async def handle_get_task(ctx: Context, sender: str, msg: GetTaskRequest):
        try:
            result = await tasks_service.get_task_by_id(msg.user_id, msg.db_name, msg.task_id)
            await ctx.send(sender, GetTaskResponse(
                task=result.get("task"),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, GetTaskResponse(task=None, error=str(e)))
    
    @tasks_protocol.on_message(UpdateTaskRequest, replies={UpdateTaskResponse})
    async def handle_update_task(ctx: Context, sender: str, msg: UpdateTaskRequest):
        try:
            update_data = {
                "title": msg.title,
                "description": msg.description,
                "status": msg.status,
            }
            result = await tasks_service.update_task(msg.user_id, msg.db_name, msg.task_id, update_data)
            await ctx.send(sender, UpdateTaskResponse(
                message=result.get("message", ""),
                task=result.get("task"),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, UpdateTaskResponse(message="", error=str(e)))
    
    @tasks_protocol.on_message(DeleteTaskRequest, replies={DeleteTaskResponse})
    async def handle_delete_task(ctx: Context, sender: str, msg: DeleteTaskRequest):
        try:
            result = await tasks_service.delete_task(msg.user_id, msg.db_name, msg.task_id)
            await ctx.send(sender, DeleteTaskResponse(
                message=result.get("message", ""),
                error=result.get("error"),
            ))
        except Exception as e:
            await ctx.send(sender, DeleteTaskResponse(message="", error=str(e)))
    
    # Include all protocols
    agent.include(ai_protocol, publish_manifest=True)
    agent.include(linkedin_protocol, publish_manifest=True)
    agent.include(scheduler_protocol, publish_manifest=True)
    agent.include(tasks_protocol, publish_manifest=True)
    
    return {
        'ai_protocol': ai_protocol,
        'linkedin_protocol': linkedin_protocol,
        'scheduler_protocol': scheduler_protocol,
        'tasks_protocol': tasks_protocol,
    }

def register_chat_protocol(agent, chat_proto, ai_service):
    """Register chat protocol handlers"""
    from datetime import datetime
    
    @chat_proto.on_message(ChatMessage)
    async def handle_chat_message(ctx: Context, sender: str, msg: ChatMessage):
        msg_key = f"{sender}:{msg.msg_id}"
        if hasattr(ctx, '_processed_messages'):
            if msg_key in ctx._processed_messages:
                return
            ctx._processed_messages.add(msg_key)
        else:
            ctx._processed_messages = {msg_key}
        
        if msg.content and isinstance(msg.content[0], TextContent):
            text_content = msg.content[0].text
            if sender == ai_service.image_generation_agent:
                pass
            else:
                pass
        
        ctx.storage.set(str(ctx.session), sender)
        
        if sender == ai_service.image_generation_agent:
            # Extract response text for logging
            response_text = ""
            for item in msg.content:
                if isinstance(item, TextContent):
                    response_text += item.text
            
            if response_text:
                pass
            
            processed = ai_service.handle_image_response(sender, msg)
            if processed:
                pass
            await ctx.send(
                sender,
                ChatAcknowledgement(
                    timestamp=datetime.utcnow(),
                    acknowledged_msg_id=msg.msg_id
                )
            )
            return
        
        await ctx.send(
            sender,
            ChatAcknowledgement(
                timestamp=datetime.utcnow(),
                acknowledged_msg_id=msg.msg_id
            )
        )
        
        for item in msg.content:
            if isinstance(item, StartSessionContent):
                pass
            elif isinstance(item, TextContent):
                pass
            elif isinstance(item, EndSessionContent):
                pass
    
    @chat_proto.on_message(ChatAcknowledgement)
    async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
        """Handle chat acknowledgement"""
        pass
    
    agent.include(chat_proto, publish_manifest=True)

def register_health_protocol(agent, agent_name):
    """Register health check protocol"""
    from uagents import Model
    
    class HealthCheck(Model):
        pass
    
    class HealthStatus(str, Enum):
        HEALTHY = "healthy"
        UNHEALTHY = "unhealthy"
    
    class AgentHealth(Model):
        agent_name: str
        status: HealthStatus
    
    def agent_is_healthy() -> bool:
        return True
    
    health_protocol = QuotaProtocol(
        storage_reference=agent.storage, 
        name="HealthProtocol", 
        version="0.1.0"
    )
    
    @health_protocol.on_message(HealthCheck, replies={AgentHealth})
    async def handle_health_check(ctx: Context, sender: str, msg: HealthCheck):
        status = HealthStatus.UNHEALTHY
        try:
            if agent_is_healthy():
                status = HealthStatus.HEALTHY
        except Exception as err:
            pass
        finally:
            await ctx.send(sender, AgentHealth(agent_name=agent_name, status=status))
    
    agent.include(health_protocol, publish_manifest=True)

