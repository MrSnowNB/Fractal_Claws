#!/usr/bin/env python3
"""
context_budget.py — 64K context window budget manager for Luffy

Problem: Luffy re-reads docs every sequence, burning context tokens.
Solution: SHA256 content-addressed cache + token budget tracking.

Ported from graphify's cache.py pattern (SHA256 content-addressed file cache)
and adapted for context window management on ZBook Strix Halo.

Usage:
    budget = ContextBudget(ctx_limit=65536)
    should, reason = budget.should_read("AI-FIRST/STEP-08-LINT-CHAIN.md")
    if should:
        content = Path(path).read_text()
        budget.mark_read(path)
    else:
        summary = budget.get_read_summary(path)
        # Use summary instead of full content
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

# Default 64K context for Qwen3.5-35B-A3B
DEFAULT_CTX_LIMIT = 65536

# Approximate tokens-per-char ratio for code/markdown
CHARS_PER_TOKEN = 3.5

# Budget zones — how the 64K window is allocated
DEFAULT_ZONES = {
    "system_prompt":  4096,
    "docs_cache":     20480,
    "ticket_context": 20480,
    "scratch_pad":    12288,
    "response":       8192,
}


class ContextBudget:
    """Tracks what Luffy has already read this session.

    Core idea from graphify: SHA256 hash each file's content.
    If hash hasn't changed since last read, skip it — the knowledge
    is already in context from a prior turn.

    Budget zones (for 64K ctx):
        system_prompt:  ~4K tokens (reserved, not tracked here)
        docs_cache:     ~20K tokens (AI-FIRST specs, AGENT-PERSONA, etc.)
        ticket_context: ~20K tokens (active ticket + context_files)
        scratch_pad:    ~12K tokens (reasoning, tool output)
        response:       ~8K tokens (model output buffer)
    """

    def __init__(
        self,
        ctx_limit: int = DEFAULT_CTX_LIMIT,
        cache_path: str = "logs/ctx-cache.json",
        zones: Optional[dict] = None,
    ):
        self.ctx_limit = ctx_limit
        self.cache_path = Path(cache_path)
        self.zones = dict(zones or DEFAULT_ZONES)
        self._file_hashes: dict[str, str] = {}   # resolved path -> sha256
        self._file_tokens: dict[str, int] = {}   # resolved path -> approx token count
        self._zone_usage: dict[str, int] = {z: 0 for z in self.zones}
        self._session_reads: set[str] = set()     # resolved paths read this session
        self._load_cache()

    # ── persistence ───────────────────────────────────────────────────────

    def _load_cache(self) -> None:
        """Load persistent file hash cache from disk."""
        if self.cache_path.exists():
            try:
                data = json.loads(self.cache_path.read_text())
                self._file_hashes = data.get("hashes", {})
                self._file_tokens = data.get("tokens", {})
            except (json.JSONDecodeError, OSError):
                pass

    def _save_cache(self) -> None:
        """Persist file hash cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "hashes": self._file_hashes,
            "tokens": self._file_tokens,
            "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        tmp = self.cache_path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(self.cache_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    # ── hashing (graphify pattern) ────────────────────────────────────────

    @staticmethod
    def file_hash(path: str) -> str:
        """SHA256 of file content (same pattern as graphify.cache.file_hash)."""
        h = hashlib.sha256()
        h.update(Path(path).read_bytes())
        return h.hexdigest()

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Approximate token count from character length."""
        return max(1, int(len(text) / CHARS_PER_TOKEN))

    # ── read gating ──────────────────────────────────────────────────────

    def should_read(self, path: str, zone: str = "docs_cache") -> tuple[bool, str]:
        """Check if a file needs to be read or is already in context.

        Returns:
            (should_read, reason)
            - (True, "new")              — never seen
            - (True, "changed")          — content changed since last read
            - (False, "cached")          — already in context, unchanged
            - (False, "budget_exceeded") — reading would blow the zone budget
            - (False, "missing")         — file does not exist
        """
        resolved = str(Path(path).resolve())

        if not Path(path).exists():
            return (False, "missing")

        current_hash = self.file_hash(path)

        # Already read this session AND content unchanged
        if resolved in self._session_reads and self._file_hashes.get(resolved) == current_hash:
            return (False, "cached")

        # Estimate tokens
        try:
            content = Path(path).read_text(errors="replace")
        except OSError:
            return (False, "missing")
        tokens_needed = self.estimate_tokens(content)

        # Check zone budget
        zone_budget = self.zones.get(zone, 20480)
        if self._zone_usage.get(zone, 0) + tokens_needed > zone_budget:
            return (False, "budget_exceeded")

        if resolved in self._file_hashes:
            return (True, "changed")
        return (True, "new")

    def mark_read(self, path: str, zone: str = "docs_cache") -> int:
        """Mark a file as read, update hash and budget tracking.

        Returns approximate token count consumed.
        """
        resolved = str(Path(path).resolve())
        current_hash = self.file_hash(path)
        content = Path(path).read_text(errors="replace")
        tokens = self.estimate_tokens(content)

        self._file_hashes[resolved] = current_hash
        self._file_tokens[resolved] = tokens
        self._session_reads.add(resolved)
        self._zone_usage[zone] = self._zone_usage.get(zone, 0) + tokens
        self._save_cache()

        return tokens

    # ── reporting ─────────────────────────────────────────────────────────

    def budget_report(self) -> dict:
        """Return current budget allocation status."""
        report = {}
        for zone, limit in self.zones.items():
            used = self._zone_usage.get(zone, 0)
            report[zone] = {
                "used": used,
                "limit": limit,
                "remaining": limit - used,
                "pct": round(used / limit * 100, 1) if limit > 0 else 0,
            }
        total_used = sum(self._zone_usage.values())
        report["total"] = {
            "used": total_used,
            "limit": self.ctx_limit,
            "remaining": self.ctx_limit - total_used,
            "pct": round(total_used / self.ctx_limit * 100, 1),
        }
        return report

    def get_read_summary(self, path: str) -> Optional[str]:
        """If a file is cached, return a one-line summary instead of full content.

        This is the key optimization: instead of re-reading a 500-line spec,
        Luffy gets: "AI-FIRST/STEP-08-LINT-CHAIN.md [cached, ~1842 tokens, unchanged]"
        """
        resolved = str(Path(path).resolve())
        if resolved in self._session_reads and resolved in self._file_hashes:
            tokens = self._file_tokens.get(resolved, 0)
            return f"[cached, ~{tokens} tokens, hash={self._file_hashes[resolved][:8]}]"
        return None

    def reset_session(self) -> None:
        """Reset per-session tracking (call at SESSION_START)."""
        self._session_reads.clear()
        self._zone_usage = {z: 0 for z in self.zones}

    # ── zone detection ──────────────────────────────────────────────────────

    def _detect_zone(self, path: str) -> str:
        """Detect the budget zone for a file based on path components.

        Rules match on individual path PARTS only — never substring of the
        full path string — so pytest tmp_path directories (which may contain
        words like 'ticket' or 'log' in temp dir names) do not pollute results.

        Priority order:
          system_prompt  — any part is 'system' or 'persona'
          ticket_context — any part is 'tickets' (exact directory name)
          scratch_pad    — any part is 'logs' or 'scratch' or 'temp'
          docs_cache     — everything else (AI-FIRST/, src/, agent/, etc.)
        """
        parts_lower = [p.lower() for p in Path(path).parts]

        if any(p in ("system", "persona") for p in parts_lower):
            return "system_prompt"
        # Match the DIRECTORY named 'tickets' — not any path containing 'ticket'
        if "tickets" in parts_lower:
            return "ticket_context"
        # logs/ scratch/ temp/ directories
        if any(p in ("logs", "scratch", "temp") for p in parts_lower):
            return "scratch_pad"
        return "docs_cache"

    # ── graphify_repo() ──────────────────────────────────────────────────────

    def graphify_repo(self, repo_path: str = "tickets/closed") -> dict:
        """Scan a directory, populate the SHA256 content cache, and return a
        lightweight knowledge graph.

        All internal keys use **resolved absolute paths** so that results are
        consistent with should_read() / mark_read() which also resolve paths.

        Args:
            repo_path: Directory to scan (default: tickets/closed)

        Returns:
            {
              "nodes":    [{id, label, type, file, content_hash, tokens, zone}, ...],
              "edges":    [{from, to, type}, ...],
              "metadata": {source_dir, generated_at, file_count, files_scanned,
                           tokens_estimated, zone_summary},
            }

        Note: ``metadata`` includes ``files_scanned``, ``tokens_estimated``, and
        ``zone_summary`` so callers can inspect budget impact without reading every
        node individually.
        """
        graph: dict = {
            "nodes": [],
            "edges": [],
            "metadata": {
                "source_dir": repo_path,
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "file_count": 0,
                "files_scanned": 0,
                "tokens_estimated": 0,
                "zone_summary": {z: 0 for z in self.zones},
            },
        }

        repo_dir = Path(repo_path)
        if not repo_dir.exists():
            graph["metadata"]["error"] = f"Directory not found: {repo_path}"
            return graph

        all_files = [
            f for f in repo_dir.rglob("*")
            if f.is_file() and not f.name.startswith(".")
        ]
        graph["metadata"]["file_count"] = len(all_files)

        total_tokens = 0

        for file_path in all_files:
            # Always use resolved absolute path — must match should_read() behaviour
            resolved = str(file_path.resolve())
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                content_hash = self.file_hash(str(file_path))
                tokens = self.estimate_tokens(content)
                zone = self._detect_zone(str(file_path))

                node = {
                    "id": file_path.stem,
                    "label": file_path.name,
                    "type": file_path.suffix.lstrip(".") or "unknown",
                    "file": resolved,
                    "content_hash": content_hash,
                    "tokens": tokens,
                    "zone": zone,
                }
                graph["nodes"].append(node)

                # Populate cache using resolved path — consistent with should_read()
                self._file_hashes[resolved] = content_hash
                self._session_reads.add(resolved)
                total_tokens += tokens
                graph["metadata"]["zone_summary"][zone] = (
                    graph["metadata"]["zone_summary"].get(zone, 0) + 1
                )

            except Exception as e:
                graph["metadata"].setdefault("errors", []).append(
                    f"{file_path.name}: {str(e)}"
                )

        # Parent–child edges from naming convention (STEP-10-B → parent STEP-10)
        seen: set[tuple] = set()
        for node in graph["nodes"]:
            stem = node["id"]
            if stem.count("-") > 1:
                parent_id = "-".join(stem.split("-")[:-1])
                key = (parent_id, stem, "depends_on")
                if key not in seen:
                    seen.add(key)
                    graph["edges"].append({"from": parent_id, "to": stem, "type": "depends_on"})

        graph["metadata"]["files_scanned"] = len(graph["nodes"])
        graph["metadata"]["tokens_estimated"] = total_tokens

        return graph
