"""Chat types, event models, and constants."""
import os

AVAILABLE_MODELS = ["deepseek-ai/deepseek-v4-flash", "z-ai/glm-5.1"]
MAX_HISTORY_MESSAGES = 20
MAX_TOOL_ROUNDS = 5
MAX_BODY_SIZE = 500 * 1024
SSE_TIMEOUT = 300
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
SKILL_DIR = os.path.expanduser("~/.hermes/skills/study")
VAULT_DIR = os.path.expanduser("~/study-vault")
CHATS_DIR = os.path.join(VAULT_DIR, "chats")

os.makedirs(CHATS_DIR, exist_ok=True)
