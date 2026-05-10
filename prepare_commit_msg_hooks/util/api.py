"""
AI API calling module for ai-commit-gen.

Uses urllib (stdlib) to call OpenAI-compatible chat completions API.
"""

import json
import re
import sys
import urllib.error
import urllib.request

from . import config
from . import git_util


def _get_lang_instruction() -> str:
    lang = config.cfg_get("language") or "en"
    return config.LANG_INSTRUCTIONS.get(lang, f"Write the commit message in {lang}.")


def call_ai_api(diff_content: str, file_summary: str) -> str:
    api_key = config.cfg_get("api_key")
    api_base_url = config.cfg_get("api_base_url")
    model = config.cfg_get("model")
    max_output_tokens = config.cfg_get("max_output_tokens")
    thinking = config.cfg_get("thinking")

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

    request_body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": config.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_output_tokens,
        "temperature": 0.3,
        "thinking": {"type": "enabled" if thinking else "disabled"},
    })

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
    commit_msg = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")

    if not commit_msg:
        config._error("Empty response from AI API")
        raise ValueError("Empty AI response")

    commit_msg = re.sub(r"^```\w*\n?", "", commit_msg)
    commit_msg = re.sub(r"\n?```$", "", commit_msg)
    commit_msg = commit_msg.strip()

    return commit_msg
