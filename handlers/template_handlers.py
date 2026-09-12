"""Template REST handlers"""
from typing import Dict, Any
from uagents import Context
from rest_models import (
    CreateTemplateRESTRequest,
    CreateTemplateRESTResponse,
    GetTemplatesRESTResponse,
    UseTemplateRESTRequest,
    UseTemplateRESTResponse,
    DeleteTemplateRESTRequest,
    DeleteTemplateRESTResponse,
)
from utils.auth import _get_user_id_from_token

def register_template_handlers(agent, payment_service, supabase_admin):
    """Register template-related REST handlers"""
    
    @agent.on_rest_post("/linkedin/templates/create", CreateTemplateRESTRequest, CreateTemplateRESTResponse)
    async def handle_create_template_frontend(ctx: Context, req: CreateTemplateRESTRequest) -> Dict[str, Any]:
        """Create post template - Frontend version"""
        try:
            if not req.user_id:
                req.user_id = await _get_user_id_from_token(ctx)
            if not req.user_id:
                return {"message": "", "template_id": None, "error": "Authentication required"}
            
            # Free mode: no payment check
            
            if not supabase_admin:
                return {"message": "", "template_id": None, "error": "Database not configured"}
            
            import re
            variables = re.findall(r'\{\{(\w+)\}\}', req.content)
            
            template_data = {
                "user_id": req.user_id,
                "name": req.name,
                "content": req.content,
                "description": req.description,
                "variables": variables
            }
            
            result = supabase_admin.table("post_templates").insert(template_data).execute()
            
            if result.data and len(result.data) > 0:
                return {
                    "message": "Template created successfully",
                    "template_id": result.data[0]["id"],
                    "error": None,
                }
            else:
                return {"message": "", "template_id": None, "error": "Failed to create template"}
        except Exception as e:
            return {"message": "", "template_id": None, "error": str(e)}
    
    @agent.on_rest_get("/linkedin/templates", GetTemplatesRESTResponse)
    async def handle_get_templates_frontend(ctx: Context) -> Dict[str, Any]:
        """Get all templates for user - Frontend version"""
        try:
            user_id = await _get_user_id_from_token(ctx)
            if not user_id:
                return {"templates": [], "error": "Authentication required"}
            
            if not supabase_admin:
                return {"templates": [], "error": "Database not configured"}
            
            result = supabase_admin.table("post_templates").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            
            return {
                "templates": result.data if result.data else [],
                "error": None,
            }
        except Exception as e:
            return {"templates": [], "error": str(e)}
    
    @agent.on_rest_post("/linkedin/templates/use", UseTemplateRESTRequest, UseTemplateRESTResponse)
    async def handle_use_template_frontend(ctx: Context, req: UseTemplateRESTRequest) -> Dict[str, Any]:
        """Use template to generate post content - Frontend version"""
        try:
            if not req.user_id:
                req.user_id = await _get_user_id_from_token(ctx)
            if not req.user_id:
                return {"content": "", "error": "Authentication required"}
            
            if not supabase_admin:
                return {"content": "", "error": "Database not configured"}
            
            result = supabase_admin.table("post_templates").select("*").eq("id", req.template_id).eq("user_id", req.user_id).execute()
            
            if not result.data or len(result.data) == 0:
                return {"content": "", "error": "Template not found"}
            
            template = result.data[0]
            content = template["content"]
            
            if req.variables:
                for key, value in req.variables.items():
                    content = content.replace(f"{{{{{key}}}}}", value)
            
            return {
                "content": content,
                "error": None,
            }
        except Exception as e:
            return {"content": "", "error": str(e)}
    
    @agent.on_rest_post("/linkedin/templates/delete", DeleteTemplateRESTRequest, DeleteTemplateRESTResponse)
    async def handle_delete_template_frontend(ctx: Context, req: DeleteTemplateRESTRequest) -> Dict[str, Any]:
        """Delete template - Frontend version"""
        try:
            if not req.user_id:
                req.user_id = await _get_user_id_from_token(ctx)
            if not req.user_id:
                return {"message": "", "error": "Authentication required"}
            
            if not supabase_admin:
                return {"message": "", "error": "Database not configured"}
            
            result = supabase_admin.table("post_templates").delete().eq("id", req.template_id).eq("user_id", req.user_id).execute()
            
            return {
                "message": "Template deleted successfully",
                "error": None,
            }
        except Exception as e:
            return {"message": "", "error": str(e)}

