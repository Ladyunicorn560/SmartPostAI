from typing import Optional, List, Dict, Any
from uagents import Model

# ==================== AUTH REST MODELS ====================

class LoginRequest(Model):
    email: str
    password: str

class RegisterRequest(Model):
    email: str
    password: str
    name: str

class AuthResponse(Model):
    success: bool
    token: Optional[str] = None
    accessToken: Optional[str] = None  # Frontend expects this field
    user: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class UserProfileRESTResponse(Model):
    success: bool
    user: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# ==================== AI REST MODELS ====================

class GeneratePostRESTRequest(Model):
    topic: str
    include_hashtags: bool = True
    language: str = "en"
    include_image: bool = False
    schedule: Optional[str] = None  # Cron expression for scheduling
    scheduled_at: Optional[str] = None  # ISO datetime string for one-time schedule
    require_approval: bool = False  # Require team approval before posting

class GeneratePostRESTResponse(Model):
    text: str
    hashtags: List[str] = []
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None
    schedule_id: Optional[str] = None  # If scheduled
    review_link: Optional[str] = None  # Link for team review/approval
    error: Optional[str] = None

class GenerateImageRESTRequest(Model):
    topic: str

class GenerateImageRESTResponse(Model):
    image_prompt: str
    image_url: Optional[str] = None  # URL from image generation agent
    error: Optional[str] = None

# ==================== LINKEDIN REST MODELS ====================

class LinkedInAuthRESTRequest(Model):
    user_id: str

class LinkedInAuthRESTResponse(Model):
    auth_url: str
    error: Optional[str] = None
    
    def model_dump(self, **kwargs):
        """Override to include camelCase field for frontend"""
        data = super().model_dump(**kwargs)
        # Add camelCase version for frontend compatibility
        if 'auth_url' in data:
            data['authUrl'] = data['auth_url']
        return data

class LinkedInCallbackRESTRequest(Model):
    code: str
    state: str

class LinkedInCallbackRESTResponse(Model):
    message: str
    profile: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class LinkedInCallbackRedirectResponse(Model):
    success: Optional[bool] = None
    message: Optional[str] = None
    error: Optional[str] = None
    redirect: Optional[str] = None

class LinkedInPostRESTRequest(Model):
    user_id: Optional[str] = None  # Optional, can be extracted from token
    text: str
    image_base64: Optional[str] = None
    imageUrl: Optional[str] = None  # Alternative field name from frontend

class LinkedInPostRESTResponse(Model):
    message: str
    post_id: Optional[str] = None
    linkedin_post_url: Optional[str] = None
    error: Optional[str] = None

class UploadImageRESTRequest(Model):
    image_base64: str  # Base64 encoded image

class UploadImageRESTResponse(Model):
    image_url: Optional[str] = None
    error: Optional[str] = None

class LinkedInAIPostRESTRequest(Model):
    user_id: Optional[str] = None  # Optional, can be extracted from token
    topic: str
    include_image: bool = False
    includeImage: Optional[bool] = None  # Accept camelCase from frontend
    language: str = "en"
    schedule: Optional[str] = None  # Cron expression for scheduling
    scheduled_at: Optional[str] = None  # ISO datetime string for one-time schedule
    require_approval: bool = False  # Require team approval before posting
    team_emails: Optional[List[str]] = None  # List of team member emails for approval

class LinkedInAIPostRESTResponse(Model):
    text: Optional[str] = ""
    hashtags: List[str] = []
    image_base64: Optional[str] = None
    imageUrl: Optional[str] = None  # Image URL (preferred over base64)
    image: Optional[str] = None  # Alias for imageUrl
    image_url: Optional[str] = None  # Snake case version
    postId: Optional[str] = None  # Saved post ID
    schedule_id: Optional[str] = None  # If scheduled
    review_link: Optional[str] = None  # Link for team review/approval
    error: Optional[str] = None

class LinkedInStatusRESTResponse(Model):
    is_connected: bool
    profile: Optional[Dict[str, Any]] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None
    
    def model_dump(self, **kwargs):
        """Override to include camelCase fields for frontend compatibility"""
        data = super().model_dump(**kwargs)
        # Add camelCase versions for frontend
        if 'is_connected' in data:
            data['isConnected'] = data['is_connected']
        if 'expires_at' in data:
            data['expiresAt'] = data['expires_at']
        return data

class LinkedInDisconnectRESTRequest(Model):
    user_id: Optional[str] = None

class LinkedInDisconnectRESTResponse(Model):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

# ==================== SCHEDULER REST MODELS ====================

class CreateScheduleRESTRequest(Model):
    user_id: Optional[str] = None
    topic: str
    schedule: Optional[str] = None  # Cron expression (optional if scheduled_at provided)
    scheduled_at: Optional[str] = None  # ISO datetime string for one-time schedule
    include_image: bool = False
    includeImage: Optional[bool] = None
    custom_text: Optional[str] = None
    imageUrl: Optional[str] = None  # Image URL for scheduled post
    require_approval: bool = False  # Require team approval before posting
    team_emails: Optional[List[str]] = None  # List of team member emails for approval

class CreateScheduleRESTResponse(Model):
    message: str
    schedule_id: Optional[str] = None
    next_post_at: Optional[str] = None
    review_link: Optional[str] = None  # Link for team review/approval
    error: Optional[str] = None

class GetSchedulesRESTResponse(Model):
    schedules: List[Dict[str, Any]] = []
    error: Optional[str] = None

class ScheduleActionRESTRequest(Model):
    schedule_id: str
    action: str

class ScheduleActionRESTResponse(Model):
    message: str
    error: Optional[str] = None

class UpdateScheduleRESTRequest(Model):
    schedule_id: str
    topic: Optional[str] = None
    content: Optional[str] = None
    schedule: Optional[str] = None  # Cron expression
    scheduled_at: Optional[str] = None  # ISO datetime
    include_image: Optional[bool] = None
    image_url: Optional[str] = None

class GetScheduledDatesRESTResponse(Model):
    dates: List[str] = []  # List of dates in YYYY-MM-DD format
    error: Optional[str] = None

class GetOccurrencesForDateRESTResponse(Model):
    occurrences: List[Dict[str, Any]] = []  # List of occurrences with schedule and date
    error: Optional[str] = None

class GetApprovalStatusRESTResponse(Model):
    approved: Optional[bool] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    status: Optional[str] = None
    comments: List[Dict[str, Any]] = []
    approvals_count: Optional[int] = None
    total_required: Optional[int] = None
    error: Optional[str] = None

class ReviewPostRESTRequest(Model):
    token: Optional[str] = None  # Token from review link (optional if in URL path)
    review_token: Optional[str] = None  # Legacy field name
    action: str  # "approve" or "reject"
    comments: Optional[str] = None
    payment_completed: Optional[bool] = None  # Flag to indicate payment was completed
    check_payment_only: Optional[bool] = None  # Flag to only check payment status without processing approval

class ReviewPostRESTResponse(Model):
    success: bool
    message: str
    error: Optional[str] = None
    schedule_id: Optional[str] = None
    payment_required: Optional[bool] = None
    payment_request: Optional[Dict[str, Any]] = None
    scheduled_at: Optional[str] = None

class GetScheduleForReviewRESTRequest(Model):
    token: Optional[str] = None  # Optional, can be in URL path
    email: Optional[str] = None  # Team member email for verification

class VerifyReviewEmailRESTRequest(Model):
    token: Optional[str] = None  # Review token (can be in query param)
    email: str  # Team member email to verify

class VerifyReviewEmailRESTResponse(Model):
    verified: bool
    schedule_id: Optional[str] = None
    error: Optional[str] = None

class GetScheduleForReviewRESTResponse(Model):
    schedule_id: Optional[str] = None
    topic: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    scheduled_at: Optional[str] = None
    status: Optional[str] = None
    platform: Optional[str] = None
    team_emails: Optional[List[str]] = None  # List of team emails
    requires_email_verification: bool = False  # Whether email verification is required
    error: Optional[str] = None

class EmptyRequest(Model):
    pass

# ==================== URL TO POST REST MODELS ====================

class URLToPostRESTRequest(Model):
    url: str
    user_id: Optional[str] = None
    include_image: bool = False
    includeImage: Optional[bool] = None
    language: str = "en"
    auto_post: bool = False  # Automatically post to LinkedIn after generating
    autoPost: Optional[bool] = None  # CamelCase version

class URLToPostRESTResponse(Model):
    text: str
    hashtags: List[str] = []
    imageUrl: Optional[str] = None
    image_url: Optional[str] = None
    source_url: str
    source_title: Optional[str] = None
    postId: Optional[str] = None
    linkedin_post_url: Optional[str] = None
    linkedin_post_id: Optional[str] = None
    error: Optional[str] = None

# ==================== POST IDEAS REST MODELS ====================

class GenerateIdeasRESTRequest(Model):
    industry: Optional[str] = None
    topic: Optional[str] = None
    prompt: Optional[str] = None
    count: int = 5
    language: str = "en"

class GenerateIdeasRESTResponse(Model):
    ideas: List[str] = []
    error: Optional[str] = None

# ==================== TEMPLATES REST MODELS ====================

class CreateTemplateRESTRequest(Model):
    name: str
    content: str
    description: Optional[str] = None
    user_id: Optional[str] = None

class CreateTemplateRESTResponse(Model):
    message: str
    template_id: Optional[str] = None
    error: Optional[str] = None

class GetTemplatesRESTResponse(Model):
    templates: List[Dict[str, Any]] = []
    error: Optional[str] = None

class UseTemplateRESTRequest(Model):
    template_id: str
    variables: Optional[Dict[str, str]] = None
    user_id: Optional[str] = None

class UseTemplateRESTResponse(Model):
    content: str
    error: Optional[str] = None

class DeleteTemplateRESTRequest(Model):
    template_id: str
    user_id: Optional[str] = None

class DeleteTemplateRESTResponse(Model):
    message: str
    error: Optional[str] = None

# ==================== TASKS REST MODELS ====================

class CreateTaskRESTRequest(Model):
    user_id: str
    db_name: str
    title: str
    description: Optional[str] = None
    status: str = "draft"

class CreateTaskRESTResponse(Model):
    message: str
    task_id: Optional[str] = None
    error: Optional[str] = None

class GetTasksRESTResponse(Model):
    tasks: List[Dict[str, Any]] = []
    error: Optional[str] = None

class GetTaskRESTResponse(Model):
    task: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class UpdateTaskRESTRequest(Model):
    user_id: str
    db_name: str
    task_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class UpdateTaskRESTResponse(Model):
    message: str
    task: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DeleteTaskRESTRequest(Model):
    user_id: str
    db_name: str
    task_id: str

class DeleteTaskRESTResponse(Model):
    message: str
    error: Optional[str] = None

# ==================== HEALTH REST MODELS ====================

class HealthRESTResponse(Model):
    status: str
    agent_name: str
    timestamp: int

# FastAPI-compatible version for deployment
class FastAPIHealthResponse:
    def __init__(self, status: str, agent_name: str, timestamp: int):
        self.status = status
        self.agent_name = agent_name
        self.timestamp = timestamp

    def dict(self):
        return {
            "status": self.status,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp
        }

# ==================== GENERATED POSTS REST MODELS ====================

class GetGeneratedPostsRESTResponse(Model):
    posts: List[Dict[str, Any]] = []
    error: Optional[str] = None

class PostGeneratedPostRESTRequest(Model):
    post_id: str
    user_id: Optional[str] = None

class PostGeneratedPostRESTResponse(Model):
    success: bool
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

# ==================== PAYMENT REST MODELS ====================

class VerifyPaymentRESTRequest(Model):
    txHash: str
    service: str
    amount: str
    user_id: Optional[str] = None

class VerifyPaymentRESTResponse(Model):
    success: bool
    message: Optional[str] = None
    tx_hash: Optional[str] = None
    explorer_url: Optional[str] = None
    error: Optional[str] = None

class PaymentStatusRESTResponse(Model):
    has_paid: bool
    payment_date: Optional[str] = None
    tx_hash: Optional[str] = None
    amount: Optional[str] = None
    error: Optional[str] = None

class DashboardAccessRESTResponse(Model):
    has_access: bool
    has_paid: bool
    message: Optional[str] = None
    error: Optional[str] = None

class PaymentHistoryRESTResponse(Model):
    success: bool
    payments: List[Dict[str, Any]] = []
    total_count: int = 0
    total_spent: str = "0"
    error: Optional[str] = None

class PaymentAnalyticsRESTResponse(Model):
    success: bool
    total_spent: str = "0"
    total_transactions: int = 0
    service_breakdown: Dict[str, Any] = {}
    recent_payments: List[Dict[str, Any]] = []
    error: Optional[str] = None

class PaymentReceiptRESTRequest(Model):
    tx_hash: str

class PaymentReceiptRESTResponse(Model):
    success: bool
    receipt: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TxExplorerRESTRequest(Model):
    tx_id: str  # Transaction ID or hash

class TxExplorerRESTResponse(Model):
    success: bool
    tx_id: Optional[str] = None
    explorer_url: Optional[str] = None
    explorer_url_with_plugin: Optional[str] = None
    environment: Optional[str] = None
    error: Optional[str] = None

class UtxosRESTRequest(Model):
    addresses: List[str]  # List of addresses to get UTXOs for

class UtxosRESTResponse(Model):
    success: bool
    utxos: List[Dict[str, Any]] = []
    total_utxos: int = 0
    total_amount: str = "0"
    error: Optional[str] = None

class BalanceRESTResponse(Model):
    success: bool
    balance: float
    address: str
    error: Optional[str] = None

class TransferRESTRequest(Model):
    recipients: list  # List of {address: str, amount: float}
    wif: str  # Wallet Import Format private key
    broadcast: bool = True

class TransferRESTResponse(Model):
    success: bool
    ticketId: Optional[str] = None
    error: Optional[str] = None

class SubmitRawTxRESTRequest(Model):
    rawtx: str  # Base64 encoded raw transaction

class SubmitRawTxRESTResponse(Model):
    success: bool
    ticketId: Optional[str] = None
    error: Optional[str] = None

class TxStatusRESTResponse(Model):
    success: bool
    status: Optional[str] = None  # BROADCASTING, SUCCESS, MINED, FAILED
    tx_id: Optional[str] = None
    tx_hex: Optional[str] = None
    errors: Optional[str] = None
    action_requested: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    explorer_url: Optional[str] = None  # WOC explorer with MNEE plugin
    environment: Optional[str] = None

class ConfigRESTResponse(Model):
    success: bool
    config: Optional[Dict] = None
    error: Optional[str] = None

# ==================== WALLET REST MODELS ====================

class SaveWalletRESTRequest(Model):
    address: str
    wif: Optional[str] = None  # Optional WIF for payment capability

class SaveWalletRESTResponse(Model):
    success: bool
    message: Optional[str] = None
    address: Optional[str] = None
    has_payment_capability: Optional[bool] = None
    error: Optional[str] = None

class GetWalletRESTResponse(Model):
    success: bool
    address: Optional[str] = None
    wif: Optional[str] = None  # Decrypted WIF
    has_payment_capability: Optional[bool] = None
    error: Optional[str] = None

class DeleteWalletRESTResponse(Model):
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

class AnalyticsRESTResponse(Model):
    total_posts: Optional[int] = None
    total_spent: Optional[float] = None
    total_earned: Optional[float] = None
    engagement_rate: Optional[float] = None
    avg_engagement: Optional[int] = None
    posts_by_service: Optional[list] = None
    recent_payments: Optional[list] = None
    engagement_trends: Optional[list] = None
    error: Optional[str] = None

class TipPostRESTRequest(Model):
    post_id: str
    amount: float
    message: Optional[str] = None

class TipPostRESTResponse(Model):
    success: bool
    tx_hash: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

# ==================== SLACK REST MODELS ====================

class SlackAuthRESTRequest(Model):
    user_id: Optional[str] = None

class SlackAuthRESTResponse(Model):
    auth_url: Optional[str] = None
    error: Optional[str] = None

class SlackCallbackRESTRequest(Model):
    code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None

class SlackCallbackRESTResponse(Model):
    success: bool
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    error: Optional[str] = None

class SlackStatusRESTResponse(Model):
    is_connected: bool
    team_id: Optional[str] = None
    team_name: Optional[str] = None
    connected_at: Optional[str] = None
    error: Optional[str] = None

class SlackCommandRESTRequest(Model):
    token: str
    team_id: str
    team_domain: Optional[str] = None
    channel_id: str
    channel_name: Optional[str] = None
    user_id: str
    user_name: Optional[str] = None
    command: str
    text: Optional[str] = None
    response_url: Optional[str] = None
    trigger_id: Optional[str] = None

class GetScheduledDatesRESTResponse(Model):
    dates: Optional[List[str]] = None
    error: Optional[str] = None

class GetOccurrencesForDateRESTResponse(Model):
    occurrences: Optional[List[Dict]] = None
    error: Optional[str] = None

class SlackEventRESTRequest(Model):
    type: Optional[str] = None
    challenge: Optional[str] = None
    event: Optional[Dict[str, Any]] = None
    token: Optional[str] = None

class SlackEventRESTResponse(Model):
    challenge: Optional[str] = None
    ok: Optional[bool] = None
    error: Optional[str] = None

class SlackDisconnectRESTRequest(Model):
    pass  # No request body needed, just user auth

class SlackCommandRESTResponse(Model):
    response_type: Optional[str] = None
    text: Optional[str] = None
    blocks: Optional[List[Dict]] = None
    error: Optional[str] = None

