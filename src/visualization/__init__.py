"""
Visualization Components Module

This module provides a component-based approach to generating HTML visualizations
for the Azure Tenant Grapher. It breaks down the massive HTML template generation
into focused, testable components.
"""

from .html_template_builder import HtmlTemplateBuilder

__all__ = ["HtmlTemplateBuilder"]
