"""Task REST handlers"""
from typing import Dict, Any
from uagents import Context
from rest_models import (
    CreateTaskRESTRequest,
    CreateTaskRESTResponse,
    GetTasksRESTResponse,
    GetTaskRESTResponse,
    UpdateTaskRESTRequest,
    UpdateTaskRESTResponse,
    DeleteTaskRESTRequest,
    DeleteTaskRESTResponse,
)

def register_task_handlers(agent, tasks_service):
    """Register task-related REST handlers"""
    
    @agent.on_rest_post("/api/tasks/create", CreateTaskRESTRequest, CreateTaskRESTResponse)
    async def handle_create_task_rest(ctx: Context, req: CreateTaskRESTRequest) -> CreateTaskRESTResponse:
        """Create task via REST"""
        try:
            task_data = {
                "title": req.title,
                "description": req.description,
                "status": req.status,
            }
            result = await tasks_service.create_task(req.user_id, req.db_name, task_data)
            return CreateTaskRESTResponse(
                message=result.get("message", ""),
                task_id=result.get("task_id"),
                error=result.get("error"),
            )
        except Exception as e:
            return CreateTaskRESTResponse(message="", error=str(e))
    
    @agent.on_rest_get("/api/tasks", GetTasksRESTResponse)
    async def handle_get_tasks_rest(ctx: Context, user_id: str = None, db_name: str = None) -> Dict[str, Any]:
        """Get all tasks via REST"""
        try:
            if not user_id:
                user_id = ctx.rest_params.get("user_id") if hasattr(ctx, 'rest_params') else None
            if not db_name:
                db_name = ctx.rest_params.get("db_name") if hasattr(ctx, 'rest_params') else None
            if not user_id or not db_name:
                return {"error": "user_id and db_name are required"}
            
            result = await tasks_service.get_all_tasks(user_id, db_name)
            return {
                "tasks": result.get("tasks", []),
                "error": result.get("error"),
            }
        except Exception as e:
            return {"error": str(e)}
    
    @agent.on_rest_get("/api/tasks/task", GetTaskRESTResponse)
    async def handle_get_task_rest(ctx: Context, user_id: str = None, db_name: str = None, task_id: str = None) -> Dict[str, Any]:
        """Get task by ID via REST"""
        try:
            if not user_id:
                user_id = ctx.rest_params.get("user_id") if hasattr(ctx, 'rest_params') else None
            if not db_name:
                db_name = ctx.rest_params.get("db_name") if hasattr(ctx, 'rest_params') else None
            if not task_id:
                task_id = ctx.rest_params.get("task_id") if hasattr(ctx, 'rest_params') else None
            if not user_id or not db_name or not task_id:
                return {"error": "user_id, db_name, and task_id are required"}
            
            result = await tasks_service.get_task_by_id(user_id, db_name, task_id)
            return {
                "task": result.get("task"),
                "error": result.get("error"),
            }
        except Exception as e:
            return {"error": str(e)}
    
    @agent.on_rest_post("/api/tasks/update", UpdateTaskRESTRequest, UpdateTaskRESTResponse)
    async def handle_update_task_rest(ctx: Context, req: UpdateTaskRESTRequest) -> UpdateTaskRESTResponse:
        """Update task via REST"""
        try:
            update_data = {
                "title": req.title,
                "description": req.description,
                "status": req.status,
            }
            result = await tasks_service.update_task(req.user_id, req.db_name, req.task_id, update_data)
            return UpdateTaskRESTResponse(
                message=result.get("message", ""),
                task=result.get("task"),
                error=result.get("error"),
            )
        except Exception as e:
            return UpdateTaskRESTResponse(message="", error=str(e))
    
    @agent.on_rest_post("/api/tasks/delete", DeleteTaskRESTRequest, DeleteTaskRESTResponse)
    async def handle_delete_task_rest(ctx: Context, req: DeleteTaskRESTRequest) -> DeleteTaskRESTResponse:
        """Delete task via REST"""
        try:
            result = await tasks_service.delete_task(req.user_id, req.db_name, req.task_id)
            return DeleteTaskRESTResponse(
                message=result.get("message", ""),
                error=result.get("error"),
            )
        except Exception as e:
            return DeleteTaskRESTResponse(message="", error=str(e))

