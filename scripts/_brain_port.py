"""
Resolve the wicked-brain server port dynamically.

The brain server uses findFreePort() at startup and writes the actual port
back to _meta/config.json. Callers should use resolve_port() rather than
hardcoding a default, so multi-server setups (different projects on
different ports) work correctly.

Resolution order:
1. WICKED_BRAIN_PORT env var (explicit override)
2. Project brain config matching cwd (source_path match)
3. Root brain config (~/.wicked-brain/_meta/config.json)
4. Fallback: 4242
"""

import json
import os
from pathlib import Path

_DEFAULT_PORT = 4242


def resolve_port() -> int:
    """Return the brain server port for the current context."""
    # 1. Explicit env var override
    env_port = os.environ.get("WICKED_BRAIN_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass  # Invalid value — fall through to config discovery

    brain_root = Path.home() / ".wicked-brain"

    # 2. Project brain matching cwd
    projects_dir = brain_root / "projects"
    if projects_dir.is_dir():
        try:
            cwd = Path.cwd().resolve()
            for project_dir in projects_dir.iterdir():
                config_path = project_dir / "_meta" / "config.json"
                if config_path.is_file():
                    try:
                        with open(config_path) as f:
                            cfg = json.load(f)
                        source = cfg.get("source_path", "")
                        if source and cwd == Path(source).resolve():
                            return int(cfg.get("server_port", _DEFAULT_PORT))
                    except Exception:
                        pass
        except Exception:
            pass

    # 3. Root brain config
    root_config = brain_root / "_meta" / "config.json"
    if root_config.is_file():
        try:
            with open(root_config) as f:
                cfg = json.load(f)
            return int(cfg.get("server_port", _DEFAULT_PORT))
        except Exception:
            pass

    # 4. Fallback
    return _DEFAULT_PORT
