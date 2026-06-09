"""Chat types, event models, and constants."""
import os

AVAILABLE_MODELS = ["z-ai/glm-5.1", "deepseek-ai/deepseek-v4-flash"]
MAX_HISTORY_MESSAGES = 20  # Context window limit
MAX_TOOL_ROUNDS = 100  # Effectively unlimited tool calls
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB
SSE_TIMEOUT = 3600  # 1 hour
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
SKILL_DIR = os.path.expanduser("~/.hermes/skills/study")
VAULT_DIR = os.path.expanduser("~/study-vault")
CHATS_DIR = os.path.join(VAULT_DIR, "chats")

os.makedirs(CHATS_DIR, exist_ok=True)
