"""Chat types, event models, and constants."""
import os

# Models by provider:
#   deepseek-v4-flash-free  → OpenCode Zen (primary — fast, free)
#   deepseek-ai/deepseek-v4-flash  → NVIDIA NIM (fallback)
#   deepseek-ai/deepseek-v4-pro    → NVIDIA NIM (fallback — higher quality)
AVAILABLE_MODELS = [
    "deepseek-v4-flash-free",       # OpenCode Zen (primary — fast, free)
    "deepseek-ai/deepseek-v4-pro",  # NVIDIA NIM (fallback 1)
    "deepseek-ai/deepseek-v4-flash", # NVIDIA NIM (fallback 2)
    "z-ai/glm-5.1",                # NVIDIA NIM (fallback 3)
]

# Provider endpoints
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
ZEN_BASE_URL = "https://opencode.ai/zen/v1"

# Environment variable names
ZEN_API_KEY_ENV = "OPENCODE_ZEN_API_KEY"

# Map each model to its provider
PROVIDER_FOR_MODEL = {
    "deepseek-v4-flash-free": "zen",
    "deepseek-ai/deepseek-v4-pro": "nvidia",
    "deepseek-ai/deepseek-v4-flash": "nvidia",
    "z-ai/glm-5.1": "nvidia",
}

MAX_HISTORY_MESSAGES = 20  # Context window limit
MAX_TOOL_ROUNDS = 100  # Effectively unlimited tool calls
MAX_BODY_SIZE = 10 * 1024 * 1024  # 10MB
SSE_TIMEOUT = 3600  # 1 hour
SKILL_DIR = os.path.expanduser("~/.hermes/skills/study")
VAULT_DIR = os.path.expanduser("~/study-vault")
CHATS_DIR = os.path.join(VAULT_DIR, "chats")
MANIM_DIR = os.path.join(VAULT_DIR, "..", "study", ".manim-tmp")

# Manim render quality: use "ql" (480p15 draft) for speed, "qm" (720p30 medium) for decent, "qh" (1080p60) for production
MANIM_RENDER_QUALITY = "ql"

os.makedirs(CHATS_DIR, exist_ok=True)
