"""
DEPRECATED: Prompt Builder — replaced by TemplateRenderer + TemplateManager.

This module is kept only for reference. All prompt construction logic has been
moved to the template-based system:
- System-level prompts are defined in prompt template JSON files.
- Business-level prompt assembly is the responsibility of the calling service.
- The TemplateRenderer handles variable substitution and message list construction.

See:
- services/template_manager.py  — Template CRUD and storage
- services/template_renderer.py — Template rendering engine
- prompt_templates/             — Preset template JSON files
"""

# This file is intentionally left as a deprecated placeholder.
# No code should import from this module in the new architecture.
