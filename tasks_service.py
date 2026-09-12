from typing import Dict, List, Optional
from datetime import datetime

class TasksService:
    def __init__(self, supabase_client=None):
        self.supabase_client = supabase_client

    async def create_task(self, user_id: str, db_name: str, task_data: Dict) -> Dict:
        """Create a new task"""
        if not self.supabase_client:
            return {"error": "Supabase client not configured"}
        
        try:
            task = {
                "user_id": user_id,
                "title": task_data.get("title", ""),
                "description": task_data.get("description"),
                "status": task_data.get("status", "pending"),
                "priority": task_data.get("priority", "medium"),
                "due_date": task_data.get("due_date"),
            }
            
            result = self.supabase_client.table("tasks").insert(task).execute()
            
            if result.data:
                return {
                    "message": "Task created successfully",
                    "task_id": result.data[0]["id"],
                }
            return {"error": "Failed to create task"}
        except Exception as e:
            return {"error": f"Failed to create task: {str(e)}"}

    async def get_all_tasks(self, user_id: str, db_name: str) -> Dict:
        """Get all tasks for a user"""
        if not self.supabase_client:
            return {"error": "Supabase client not configured"}
        
        try:
            result = self.supabase_client.table("tasks").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            
            return {"tasks": result.data or []}
        except Exception as e:
            return {"error": f"Failed to get tasks: {str(e)}"}

    async def get_task_by_id(self, user_id: str, db_name: str, task_id: str) -> Dict:
        """Get a task by ID"""
        if not self.supabase_client:
            return {"error": "Supabase client not configured"}
        
        try:
            result = self.supabase_client.table("tasks").select("*").eq("id", task_id).eq("user_id", user_id).execute()
            
            if not result.data:
                return {"error": "Task not found"}
            
            return {"task": result.data[0]}
        except Exception as e:
            return {"error": f"Failed to get task: {str(e)}"}

    async def update_task(self, user_id: str, db_name: str, task_id: str, update_data: Dict) -> Dict:
        """Update a task"""
        if not self.supabase_client:
            return {"error": "Supabase client not configured"}
        
        try:
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            # If status is completed, set completed_at
            if update_data.get("status") == "completed" and "completed_at" not in update_data:
                update_data["completed_at"] = datetime.now().isoformat()
            
            result = self.supabase_client.table("tasks").update(update_data).eq("id", task_id).eq("user_id", user_id).execute()
            
            if not result.data:
                return {"error": "Task not found"}
            
            return {
                "message": "Task updated successfully",
                "task": result.data[0],
            }
        except Exception as e:
            return {"error": f"Failed to update task: {str(e)}"}

    async def delete_task(self, user_id: str, db_name: str, task_id: str) -> Dict:
        """Delete a task"""
        if not self.supabase_client:
            return {"error": "Supabase client not configured"}
        
        try:
            result = self.supabase_client.table("tasks").delete().eq("id", task_id).eq("user_id", user_id).execute()
            
            if not result.data:
                return {"error": "Task not found"}
            
            return {"message": "Task deleted successfully"}
        except Exception as e:
            return {"error": f"Failed to delete task: {str(e)}"}
