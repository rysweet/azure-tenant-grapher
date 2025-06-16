"""
HTML Template Builder - Main coordinator for visualization components.

This module provides the main HtmlTemplateBuilder class that coordinates
CSS styling, JavaScript functionality, and HTML structure generation
for the 3D graph visualization.
"""

import os
from typing import Any, Dict, Optional

from ..exceptions import AzureTenantGrapherError
from .css_style_builder import CssStyleBuilder
from .html_structure_builder import HtmlStructureBuilder
from .javascript_builder import JavaScriptBuilder


class VisualizationError(AzureTenantGrapherError):
    """Raised when visualization template generation fails."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("error_code", "VISUALIZATION_ERROR")
        kwargs.setdefault(
            "recovery_suggestion", "Check graph data structure and template parameters"
        )
        super().__init__(message, **kwargs)


class HtmlTemplateBuilder:
    """
    Main coordinator class for building HTML visualization templates.

    This class orchestrates the CSS, JavaScript, and HTML structure builders
    to create a complete interactive 3D visualization template from graph data.
    """

    def __init__(self, theme: Optional[str] = None) -> None:
        """
        Initialize the HTML template builder.

        Args:
            theme: Optional theme name for customization (default, dark, light)
        """
        self.theme = theme or "default"
        self.css_builder = CssStyleBuilder(theme=self.theme)
        self.js_builder = JavaScriptBuilder()
        self.html_builder = HtmlStructureBuilder()

    def build_template(
        self,
        graph_data: Dict[str, Any],
        specification_path: Optional[str] = None,
        title: str = "Azure Tenant Graph - 3D Visualization",
        custom_css: Optional[str] = None,
        custom_js: Optional[str] = None,
    ) -> str:
        """
        Build the complete HTML template with embedded CSS and JavaScript.

        Args:
            graph_data: Graph data containing nodes and links
            specification_path: Optional path to tenant specification file
            title: HTML page title
            custom_css: Optional additional CSS styles
            custom_js: Optional additional JavaScript code

        Returns:
            Complete HTML template as string

        Raises:
            VisualizationError: If template generation fails
        """
        try:
            # Validate graph data
            self._validate_graph_data(graph_data)

            # Build CSS styles
            css_content = self.css_builder.build_styles()
            if custom_css:
                css_content += "\n" + custom_css

            # Build JavaScript functionality
            js_content = self.js_builder.build_script(graph_data)
            if custom_js:
                js_content += "\n" + custom_js

            # Generate specification link HTML
            spec_link_html = self._generate_specification_link(specification_path)

            # Build complete HTML structure
            html_content = self.html_builder.build_structure(
                title=title,
                css_content=css_content,
                js_content=js_content,
                spec_link_html=spec_link_html,
            )

            return html_content

        except Exception as e:
            raise VisualizationError(
                f"Failed to build HTML template: {e!s}",
                context={"theme": self.theme, "has_custom_css": custom_css is not None},
                cause=e,
            ) from e

    def build_template_with_customization(
        self, graph_data: Dict[str, Any], customization: Dict[str, Any]
    ) -> str:
        """
        Build template with detailed customization options.

        Args:
            graph_data: Graph data containing nodes and links
            customization: Dictionary containing customization options:
                - title: Page title
                - theme_colors: Color overrides
                - layout_options: Layout configuration
                - feature_flags: Enable/disable features

        Returns:
            Complete HTML template as string
        """
        try:
            # Apply theme customizations to CSS builder
            if "theme_colors" in customization:
                self.css_builder.apply_color_overrides(customization["theme_colors"])

            # Apply layout options to HTML builder
            if "layout_options" in customization:
                self.html_builder.apply_layout_options(customization["layout_options"])

            # Apply feature flags to JavaScript builder
            if "feature_flags" in customization:
                self.js_builder.apply_feature_flags(customization["feature_flags"])

            # Build template with customizations
            return self.build_template(
                graph_data=graph_data,
                title=customization.get(
                    "title", "Azure Tenant Graph - 3D Visualization"
                ),
                specification_path=customization.get("specification_path"),
                custom_css=customization.get("custom_css"),
                custom_js=customization.get("custom_js"),
            )

        except Exception as e:
            raise VisualizationError(
                f"Failed to build customized template: {e!s}",
                context={"customization_keys": list(customization.keys())},
                cause=e,
            ) from e

    def _validate_graph_data(self, graph_data: Dict[str, Any]) -> None:
        """
        Validate that graph data has the required structure.

        Args:
            graph_data: Graph data to validate

        Raises:
            VisualizationError: If graph data is invalid
        """
        required_keys = ["nodes", "links", "node_types", "relationship_types"]
        missing_keys = [key for key in required_keys if key not in graph_data]

        if missing_keys:
            raise VisualizationError(
                f"Graph data missing required keys: {missing_keys}",
                context={
                    "available_keys": list(graph_data.keys()),
                    "missing_keys": missing_keys,
                },
            )

        # Validate nodes structure
        if not isinstance(graph_data["nodes"], list):
            raise VisualizationError(
                "Graph data 'nodes' must be a list",
                context={"nodes_type": type(graph_data["nodes"]).__name__},
            )

        # Validate links structure
        if not isinstance(graph_data["links"], list):
            raise VisualizationError(
                "Graph data 'links' must be a list",
                context={"links_type": type(graph_data["links"]).__name__},
            )

        # Validate that nodes have required fields
        if graph_data["nodes"]:
            required_node_fields = ["id", "name", "type"]
            sample_node = graph_data["nodes"][0]
            missing_node_fields = [
                field for field in required_node_fields if field not in sample_node
            ]

            if missing_node_fields:
                raise VisualizationError(
                    f"Node objects missing required fields: {missing_node_fields}",
                    context={
                        "sample_node_keys": list(sample_node.keys()),
                        "missing_fields": missing_node_fields,
                    },
                )

    def _generate_specification_link(self, specification_path: Optional[str]) -> str:
        """
        Generate HTML for the tenant specification link.

        Args:
            specification_path: Path to the specification file

        Returns:
            HTML string for the specification link section
        """
        import glob

        # If not provided or doesn't exist, look for latest in current directory or specs/ subdirectory
        if not specification_path or not os.path.exists(specification_path):
            current_dir = os.getcwd()
            # Search in current directory
            spec_files = sorted(
                glob.glob(os.path.join(current_dir, "*_tenant_spec.md")), reverse=True
            )
            # If not found, search in specs/ subdirectory
            if not spec_files:
                specs_dir = os.path.join(current_dir, "specs")
                spec_files = sorted(
                    glob.glob(os.path.join(specs_dir, "*_tenant_spec.md")), reverse=True
                )
            if spec_files:
                specification_path = spec_files[0]
            else:
                return ""

        spec_filename = os.path.basename(specification_path)
        return f"""
        <div class="filter-section">
            <h4>Documentation</h4>
            <a href="{spec_filename}" target="_blank" class="spec-link">
                📄 View Tenant Specification
            </a>
        </div>
        """

    def get_supported_themes(self) -> list[str]:
        """
        Get list of supported theme names.

        Returns:
            List of available theme names
        """
        return self.css_builder.get_supported_themes()

    def set_theme(self, theme: str) -> None:
        """
        Change the current theme.

        Args:
            theme: Theme name to apply

        Raises:
            VisualizationError: If theme is not supported
        """
        if theme not in self.get_supported_themes():
            raise VisualizationError(
                f"Unsupported theme: {theme}",
                context={
                    "requested_theme": theme,
                    "supported_themes": self.get_supported_themes(),
                },
            )

        self.theme = theme
        self.css_builder.set_theme(theme)

    def export_components(self) -> Dict[str, str]:
        """
        Export individual components (CSS, JS, HTML structure) for debugging.

        Returns:
            Dictionary with component contents
        """
        return {
            "css": self.css_builder.build_styles(),
            "js_template": self.js_builder.get_template(),
            "html_structure": self.html_builder.get_template(),
            "theme": self.theme,
        }
