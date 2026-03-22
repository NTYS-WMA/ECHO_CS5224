"""
Template Renderer — renders prompt templates with caller-supplied variables.

This replaces the old PromptBuilder. Instead of hard-coding prompt construction
logic for each operation, the renderer:
1. Looks up the template by ID from the TemplateManager.
2. Validates that all required variables are provided.
3. Substitutes {{variable}} placeholders with actual values.
4. Returns a provider-ready message list (system + user messages).

The renderer only handles system-level template rendering. Business-level
prompt assembly (e.g., formatting conversation context, building relationship
blocks) is the responsibility of the calling service.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.templates import PromptTemplate, TemplateDefaults

logger = logging.getLogger(__name__)

# Regex pattern for {{variable}} placeholders
_VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""

    def __init__(self, message: str, template_id: Optional[str] = None):
        super().__init__(message)
        self.template_id = template_id


class TemplateRenderer:
    """
    Renders prompt templates into provider-ready message lists.

    Works in conjunction with TemplateManager to resolve template IDs.
    """

    def __init__(self, template_manager):
        """
        Args:
            template_manager: A TemplateManager instance for template lookups.
        """
        self._manager = template_manager

    def render(
        self,
        template_id: str,
        variables: Dict[str, Any],
        system_prompt_override: Optional[str] = None,
    ) -> Tuple[List[dict], TemplateDefaults]:
        """
        Render a template into a provider-ready message list.

        Args:
            template_id: The template to render.
            variables: Variable values to substitute into the template.
            system_prompt_override: Optional override for the system prompt.
                If provided, replaces the template's system_prompt entirely.
                This is intended for rare cases where the AI service needs
                to inject safety or compliance wrappers.

        Returns:
            A tuple of (messages, defaults) where:
            - messages: List of dicts with 'role' and 'content' keys.
            - defaults: The template's default generation parameters.

        Raises:
            TemplateRenderError: If the template is not found, required
                variables are missing, or rendering fails.
        """
        template = self._manager.get_template(template_id)
        if template is None:
            raise TemplateRenderError(
                f"Template '{template_id}' not found.",
                template_id=template_id,
            )

        # Validate required variables
        self._validate_variables(template, variables)

        # Apply defaults for optional variables
        effective_vars = self._apply_defaults(template, variables)

        # Render user prompt
        rendered_user_prompt = self._substitute(
            template.user_prompt_template, effective_vars, template_id
        )

        # Build system prompt
        system_prompt = system_prompt_override or template.system_prompt

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": rendered_user_prompt},
        ]

        defaults = template.defaults or TemplateDefaults()

        return messages, defaults

    def render_with_messages(
        self,
        template_id: str,
        messages: List[dict],
    ) -> Tuple[List[dict], TemplateDefaults]:
        """
        Render a template for multi-turn chat where the caller provides
        the full message list.

        For chat-style templates, the caller already has the conversation
        messages assembled. This method prepends the template's system prompt
        (if the first message is not already a system message) and returns
        the combined list.

        Args:
            template_id: The template to use for the system prompt.
            messages: Caller-provided message list.

        Returns:
            A tuple of (messages, defaults).

        Raises:
            TemplateRenderError: If the template is not found.
        """
        template = self._manager.get_template(template_id)
        if template is None:
            raise TemplateRenderError(
                f"Template '{template_id}' not found.",
                template_id=template_id,
            )

        result_messages = []

        # If the caller's first message is a system message, keep it as-is
        # but prepend the template's system prompt as an additional system context
        if messages and messages[0].get("role") == "system":
            # Merge: template system prompt + caller system prompt
            merged_system = (
                template.system_prompt + "\n\n" + messages[0]["content"]
            )
            result_messages.append({"role": "system", "content": merged_system})
            result_messages.extend(messages[1:])
        else:
            # Prepend template system prompt
            result_messages.append(
                {"role": "system", "content": template.system_prompt}
            )
            result_messages.extend(messages)

        defaults = template.defaults or TemplateDefaults()
        return result_messages, defaults

    # ------------------------------------------------------------------ #
    # Validation and Substitution
    # ------------------------------------------------------------------ #

    def _validate_variables(
        self, template: PromptTemplate, variables: Dict[str, Any]
    ) -> None:
        """Check that all required variables are provided."""
        missing = []
        for var_name, var_schema in template.variables.items():
            if var_schema.required and var_name not in variables:
                # Check if there's a default
                if var_schema.default is None:
                    missing.append(var_name)

        if missing:
            raise TemplateRenderError(
                f"Missing required variables for template '{template.template_id}': "
                f"{', '.join(missing)}",
                template_id=template.template_id,
            )

    def _apply_defaults(
        self, template: PromptTemplate, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply default values for optional variables not provided."""
        effective = dict(variables)
        for var_name, var_schema in template.variables.items():
            if var_name not in effective and var_schema.default is not None:
                effective[var_name] = var_schema.default
        return effective

    @staticmethod
    def _substitute(
        template_str: str, variables: Dict[str, Any], template_id: str
    ) -> str:
        """
        Substitute {{variable}} placeholders with actual values.

        Args:
            template_str: The template string with placeholders.
            variables: Variable values to substitute.
            template_id: Template ID for error reporting.

        Returns:
            The rendered string.

        Raises:
            TemplateRenderError: If an unresolved placeholder remains.
        """

        def replacer(match):
            var_name = match.group(1)
            if var_name in variables:
                return str(variables[var_name])
            # This should not happen after validation, but be defensive
            raise TemplateRenderError(
                f"Unresolved variable '{{{{{var_name}}}}}' in template '{template_id}'.",
                template_id=template_id,
            )

        try:
            return _VARIABLE_PATTERN.sub(replacer, template_str)
        except TemplateRenderError:
            raise
        except Exception as e:
            raise TemplateRenderError(
                f"Failed to render template '{template_id}': {str(e)}",
                template_id=template_id,
            )
