"""
AI API calling module for ai-commit-gen.

Uses urllib (stdlib) to call OpenAI-compatible chat completions API.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from . import config, git_util


def _get_lang_instruction() -> str:
    lang = config.cfg_get("language") or "en"
    return config.LANG_INSTRUCTIONS.get(lang, f"Write the commit message in {lang}.")


def _clean_commit_message(raw_text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL | re.IGNORECASE)
    if "</think>" in cleaned.lower():
        cleaned = re.split(r"</think>", cleaned, flags=re.IGNORECASE)[-1]
    cleaned = cleaned.strip()
    cleaned = re.sub(r"^```\w*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def call_ai_api(diff_content: str, file_summary: str) -> str:
    api_key = str(config.cfg_get("api_key") or "")
    api_base_url = str(config.cfg_get("api_base_url") or "")
    model = str(config.cfg_get("model") or "")
    max_output_tokens = config.cfg_get("max_output_tokens")
    thinking = bool(config.cfg_get("thinking"))

    branch_name = git_util.get_branch_name()
    lang_instruction = _get_lang_instruction()

    user_prompt_parts = [f"Branch: {branch_name}"]
    if file_summary:
        user_prompt_parts.append(f"\nChanged files:\n{file_summary}")
    user_prompt_parts.append(f"\nDiff:\n{diff_content}")
    user_prompt_parts.append(f"\n{lang_instruction}")
    user_prompt_parts.append(
        "\nGenerate a single commit message following Conventional Commits format. "
        "Output ONLY the commit message, nothing else."
    )
    user_prompt = "\n".join(user_prompt_parts)

    payload: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": "system", "content": config.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_output_tokens,
        "temperature": 0.3,
    }
    is_deepseek_api = "api.deepseek.com" in api_base_url.lower()
    is_deepseek_model = "deepseek" in model.lower()
    if is_deepseek_api:
        payload["thinking"] = {"type": "enabled" if thinking else "disabled"}
    elif thinking and is_deepseek_model:
        payload["thinking"] = {"type": "enabled"}

    request_body = json.dumps(payload)

    config._debug(f"API request body length: {len(request_body)}")
    config._debug(f"\n=== SYSTEM PROMPT ===\n{config.SYSTEM_PROMPT}\n=== END SYSTEM PROMPT ===")
    config._debug(f"\n=== USER PROMPT ===\n{user_prompt}\n=== END USER PROMPT ===")
    endpoint = f"{api_base_url.rstrip('/')}/chat/completions"
    config._debug(f"API endpoint: {endpoint}")

    req = urllib.request.Request(
        endpoint,
        data=request_body.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "ai-commit/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            config._debug(f"HTTP status: {resp.status}")
            config._debug(f"Response body: {body}")
    except urllib.error.HTTPError as exc:
        config._error(f"API request failed (HTTP {exc.code})")
        try:
            err_body = exc.read().decode("utf-8")
            err_data = json.loads(err_body)
            err_msg = err_data.get("error", {}).get("message", "")
            if err_msg:
                config._error(f"Error: {err_msg}")
        except Exception:
            pass
        raise
    except urllib.error.URLError as exc:
        config._error(f"API request failed: {exc.reason}")
        raise

    data = json.loads(body)
    message = (data.get("choices") or [{}])[0].get("message") or {}
    raw_content = message.get("content")
    commit_msg = _clean_commit_message(raw_content) if isinstance(raw_content, str) else ""

    if not commit_msg:
        raw_reasoning = message.get("reasoning_content")
        if isinstance(raw_reasoning, str):
            commit_msg = _clean_commit_message(raw_reasoning)

    if not commit_msg:
        config._error("Empty response from AI API")
        raise ValueError("Empty AI response")

    return commit_msg
