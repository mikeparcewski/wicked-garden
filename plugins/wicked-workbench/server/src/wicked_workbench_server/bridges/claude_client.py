"""
Claude Client

Generates A2UI documents using the Anthropic API.
"""

import json
import os
import re
from typing import Any

from anthropic import Anthropic


class ClaudeClient:
    """
    Client for generating A2UI documents via Claude.
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key. Uses ANTHROPIC_API_KEY env var if not provided.
            model: Model to use. Defaults to claude-sonnet-4-20250514.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.model = model or self.DEFAULT_MODEL
        self.client = Anthropic(api_key=self.api_key)

    async def generate_a2ui(
        self,
        system_prompt: str,
        user_intent: str,
        max_tokens: int = 4096
    ) -> list[dict[str, Any]]:
        """
        Generate an A2UI document from user intent.

        Args:
            system_prompt: System prompt with catalog definitions
            user_intent: User's request (e.g., "Show blocked tasks with context")
            max_tokens: Maximum tokens in response

        Returns:
            A2UI document as list of messages
        """
        # Add JSON output instruction
        full_intent = f"""{user_intent}

Output only the A2UI JSON array, no explanation or markdown code blocks."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": full_intent}
            ]
        )

        # Extract JSON from response
        content = response.content[0].text
        return self._parse_a2ui_response(content)

    def _parse_a2ui_response(self, content: str) -> list[dict[str, Any]]:
        """
        Parse A2UI JSON from Claude's response.

        Handles responses with or without markdown code blocks.

        Args:
            content: Raw response text

        Returns:
            Parsed A2UI document
        """
        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", content)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON array directly
            json_str = content.strip()

        # Find the array bounds
        start = json_str.find("[")
        end = json_str.rfind("]") + 1

        if start == -1 or end == 0:
            raise ValueError(f"No JSON array found in response: {content[:200]}")

        json_str = json_str[start:end]

        try:
            document = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {e}")

        if not isinstance(document, list):
            raise ValueError("A2UI document must be a JSON array")

        return document

    def validate_a2ui_document(self, document: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Validate an A2UI document structure.

        Args:
            document: A2UI document to validate

        Returns:
            Validation result with 'valid' bool and 'errors' list
        """
        errors = []

        if not isinstance(document, list):
            errors.append("Document must be an array of messages")
            return {"valid": False, "errors": errors}

        has_surface = False
        has_root = False
        component_ids = set()
        referenced_ids = set()

        for msg in document:
            if "createSurface" in msg:
                has_surface = True
                surface = msg["createSurface"]
                if not surface.get("surfaceId"):
                    errors.append("createSurface missing surfaceId")
                if not surface.get("catalogId"):
                    errors.append("createSurface missing catalogId")

            if "updateComponents" in msg:
                update = msg["updateComponents"]
                if not update.get("surfaceId"):
                    errors.append("updateComponents missing surfaceId")

                for comp in update.get("components", []):
                    comp_id = comp.get("id")
                    if not comp_id:
                        errors.append("Component missing id")
                    else:
                        component_ids.add(comp_id)
                        if comp_id == "root":
                            has_root = True

                    if not comp.get("component"):
                        errors.append(f"Component {comp_id} missing component type")

                    # Track child references
                    for child_id in comp.get("children", []):
                        if isinstance(child_id, str):
                            referenced_ids.add(child_id)

        if not has_surface:
            errors.append("Document must have createSurface message")
        if not has_root:
            errors.append("Components must include a 'root' component")

        # Check for dangling references
        for ref_id in referenced_ids:
            if ref_id not in component_ids:
                errors.append(f"Referenced component '{ref_id}' not defined")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "stats": {
                "components": len(component_ids),
                "references": len(referenced_ids)
            }
        }
