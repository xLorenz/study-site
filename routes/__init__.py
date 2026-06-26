"""Routes package - exports register function for route registration."""

from .admin import handle_create_subject, handle_delete_subject
from .ingest import handle_health, handle_status, handle_update_wiki
from .chat import (
    handle_model,
    handle_chat_start_route,
    handle_chat_stream_route,
    handle_chat_save_route,
    handle_chat_load_route,
    handle_chat_delete_route,
)
from .files import (
    handle_subjects,
    handle_files,
    handle_file_content,
    handle_objects,
    handle_object_content,
    handle_upload,
    handle_delete_file,
    handle_search,
    handle_original,
    handle_pending_state,
    handle_mark_file,
)
from .system import (
    handle_graph,
    handle_lint,
    handle_regenerate_index,
    handle_themes,
    handle_skill,
    handle_static,
    handle_root,
)
from ._base import set_config


def register(handler_class):
    """Attach route methods to a handler class."""

    # System routes
    handler_class._api_health = lambda self: handle_health(self)
    handler_class._api_status = lambda self: handle_status(self)
    handler_class._api_themes = lambda self: handle_themes(self)
    handler_class._api_skill = lambda self, skill_name: handle_skill(self, skill_name)
    handler_class._api_root = lambda self: handle_root(self)
    handler_class._api_static = lambda self, path: handle_static(self, path)

    # Chat routes
    handler_class._api_model = lambda self: handle_model(self)
    handler_class._api_chat_start = lambda self: handle_chat_start_route(self)
    handler_class._api_chat_stream = lambda self: handle_chat_stream_route(self)
    handler_class._api_chat_save = lambda self: handle_chat_save_route(self)
    handler_class._api_chat_load = lambda self, params: handle_chat_load_route(self, params)
    handler_class._api_chat_delete = lambda self: handle_chat_delete_route(self)

    # Files routes
    handler_class._api_subjects = lambda self: handle_subjects(self)
    handler_class._api_files = lambda self, params: handle_files(self, params)
    handler_class._api_file_content = lambda self, params: handle_file_content(self, params)
    handler_class._api_objects = lambda self, params: handle_objects(self, params)
    handler_class._api_object_content = lambda self, params: handle_object_content(self, params)
    handler_class._api_upload = lambda self: handle_upload(self)
    handler_class._api_delete_file = lambda self: handle_delete_file(self)
    handler_class._api_search = lambda self, params: handle_search(self, params)
    handler_class._api_original = lambda self, params: handle_original(self, params)
    handler_class._api_pending_state = lambda self, params: handle_pending_state(self, params)
    handler_class._api_mark_file = lambda self: handle_mark_file(self)

    # Admin routes
    handler_class._api_create_subject = lambda self: handle_create_subject(self)
    handler_class._api_delete_subject = lambda self: handle_delete_subject(self)

    # Ingest routes
    handler_class._api_update_wiki = lambda self: handle_update_wiki(self)

    # Graph/Lint/Index routes
    handler_class._api_graph = lambda self, params: handle_graph(self, params)
    handler_class._api_lint = lambda self, params: handle_lint(self, params)
    handler_class._api_regenerate_index = lambda self, params: handle_regenerate_index(self, params)


def setup_routes(handler_class, study_dir: str, vault: str, cache_dir: str, cfg: dict,
                 nim_api_key: str, opencode_zen_api_key: str, nim_base_url: str, host: str, port: int):
    """Initialize shared config in _base module and patch route modules with correct values."""
    from ._base import set_config
    set_config(study_dir, vault, cache_dir, cfg,
               nim_api_key, opencode_zen_api_key, nim_base_url, host, port)

    # Patch module-level imports in all route modules (they imported stale empty strings)
    from . import _base as _b, files, system, ingest, chat, admin
    for mod in [files, system, ingest, chat, admin]:
        mod.VAULT = _b.VAULT
        mod.STUDY_DIR = _b.STUDY_DIR

    handler_class.VAULT = _b.VAULT
    handler_class.STUDY_DIR = _b.STUDY_DIR
    handler_class.CACHE_DIR = _b.CACHE_DIR