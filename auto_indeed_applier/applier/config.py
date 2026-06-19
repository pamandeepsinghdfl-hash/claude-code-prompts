"""Load and validate configuration from YAML."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised when the config file is missing or invalid."""


@dataclass
class Config:
    """Parsed configuration. Access the raw nested dict via `.raw`."""

    raw: dict[str, Any]
    path: str

    # --- convenience accessors ---------------------------------------------
    @property
    def search(self) -> dict[str, Any]:
        return self.raw.get("search", {})

    @property
    def filters(self) -> dict[str, Any]:
        return self.raw.get("filters", {})

    @property
    def limits(self) -> dict[str, Any]:
        return self.raw.get("limits", {})

    @property
    def behavior(self) -> dict[str, Any]:
        return self.raw.get("behavior", {})

    @property
    def profile(self) -> dict[str, Any]:
        return self.raw.get("profile", {})

    @property
    def screening_answers(self) -> dict[str, Any]:
        return self.raw.get("screening_answers", {})

    def get(self, *keys: str, default: Any = None) -> Any:
        """Nested get: config.get('limits', 'max_applications_per_run')."""
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node


_REQUIRED_PROFILE_FIELDS = ["first_name", "last_name", "email", "phone"]


def load_config(path: str) -> Config:
    """Load config.yaml, applying minimal validation and sane defaults."""
    if not os.path.exists(path):
        raise ConfigError(
            f"Config file not found: {path}\n"
            f"Copy config.example.yaml to {path} and edit it."
        )

    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a mapping/object.")

    cfg = Config(raw=raw, path=path)

    # Validate the bits we cannot run without.
    profile = cfg.profile
    missing = [f for f in _REQUIRED_PROFILE_FIELDS if not profile.get(f)]
    if missing:
        raise ConfigError(
            "Missing required profile fields: " + ", ".join(missing)
        )

    if not cfg.search.get("queries"):
        raise ConfigError("config.search.queries must contain at least one query.")

    resume = profile.get("resume_path")
    if resume and not os.path.isabs(resume):
        # Resolve relative to the config file's directory.
        base = os.path.dirname(os.path.abspath(path))
        resolved = os.path.join(base, resume)
        cfg.raw["profile"]["resume_path"] = resolved

    return cfg
