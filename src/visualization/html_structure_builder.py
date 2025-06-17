"""
HTML Structure Builder - Handles HTML structure generation for the visualization.

This module provides the HtmlStructureBuilder class that generates the HTML
structure and layout for the 3D graph visualization interface.
"""

from typing import Dict


class HtmlStructureBuilder:
    """
    Handles generation of HTML structure for the visualization interface.

    Provides modular HTML generation for different sections of the
    3D graph visualization layout.
    """

    def __init__(self) -> None:
        """Initialize the HTML structure builder."""
        self.layout_options: Dict[str, bool] = {
            "show_controls": True,
            "show_stats": True,
            "show_node_info": True,
            "show_cluster_labels": True,
        }

    def build_structure(
        self, title: str, css_content: str, js_content: str, spec_link_html: str = ""
    ) -> str:
        """
        Build complete HTML structure for the visualization.

        Args:
            title: Page title
            css_content: CSS stylesheet content
            js_content: JavaScript code content
            spec_link_html: Optional specification link HTML

        Returns:
            Complete HTML document as string
        """
        return f"""<!DOCTYPE html>
<html lang="en">
{self._build_head(title, css_content)}
{self._build_body(js_content, spec_link_html)}
</html>"""

    def _build_head(self, title: str, css_content: str) -> str:
        """Build HTML head section."""
        return f"""<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/3d-force-graph@1.72.2/dist/3d-force-graph.min.js"></script>
    <style>
{css_content}
    </style>
</head>"""

    def _build_body(self, js_content: str, spec_link_html: str = "") -> str:
        """Build HTML body section."""
        body_content = f"""<body>
    <div id="visualization"></div>
    {self._build_cluster_labels_overlay() if self.layout_options.get("show_cluster_labels") else ""}
    {self._build_controls_panel(spec_link_html) if self.layout_options.get("show_controls") else ""}
    {self._build_stats_panel() if self.layout_options.get("show_stats") else ""}
    {self._build_node_info_panel() if self.layout_options.get("show_node_info") else ""}

    <script>
{js_content}
    </script>
</body>"""
        return body_content

    def _build_cluster_labels_overlay(self) -> str:
        """Build cluster labels overlay container."""
        return """
    <div id="cluster-labels"></div>"""

    def _build_controls_panel(self, spec_link_html: str = "") -> str:
        """Build controls panel HTML."""
        return f"""
    <div class="controls">
        <h3>Azure Graph Controls</h3>

        <input type="text" id="searchBox" class="search-box" placeholder="Search nodes..." />

        <div class="filter-section">
            <h4>Node Types</h4>
            <div id="nodeFilters"></div>
        </div>

        <div class="filter-section">
            <h4>Relationship Types</h4>
            <div id="relationshipFilters"></div>
        </div>

        <button class="reset-btn" onclick="resetFilters()">Reset All Filters</button>

        <!-- auto-rotation is disabled by default -->
        <button id="toggleRotateBtn" class="control-btn">Enable Auto-Rotate</button>

        <div class="button-group">
            <button id="zoomInBtn" class="control-btn">+ Zoom</button>
            <button id="zoomOutBtn" class="control-btn">- Zoom</button>
        </div>

        {spec_link_html}
    </div>"""

    def _build_stats_panel(self) -> str:
        """Build statistics panel HTML."""
        return """
    <div class="stats">
        <div>Nodes: <span id="nodeCount">0</span></div>
        <div>Links: <span id="linkCount">0</span></div>
        <div>Visible Nodes: <span id="visibleNodeCount">0</span></div>
        <div>Visible Links: <span id="visibleLinkCount">0</span></div>
        <button id="resetCameraBtn" class="control-btn">Reset Camera</button>
    </div>"""

    def _build_node_info_panel(self) -> str:
        """Build node information panel HTML."""
        return """
    <div class="node-info" id="nodeInfo">
        <button class="close-btn" onclick="closeNodeInfo()">&times;</button>
        <h3 id="nodeInfoTitle">Node Information</h3>
        <div id="nodeInfoContent"></div>
    </div>"""

    def apply_layout_options(self, options: Dict[str, bool]) -> None:
        """
        Apply layout options to control which sections are shown.

        Args:
            options: Dictionary of layout option names to boolean values
        """
        self.layout_options.update(options)

    def get_template(self) -> str:
        """
        Get the HTML template structure.

        Returns:
            HTML template with placeholders
        """
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/3d-force-graph@1.72.2/dist/3d-force-graph.min.js"></script>
    <style>
{css_content}
    </style>
</head>
<body>
    <div id="visualization"></div>
    <!-- Dynamic content based on layout options -->

    <script>
{js_content}
    </script>
</body>
</html>"""

    def build_minimal_structure(
        self, title: str, css_content: str, js_content: str
    ) -> str:
        """
        Build minimal HTML structure with just the graph container.

        Args:
            title: Page title
            css_content: CSS stylesheet content
            js_content: JavaScript code content

        Returns:
            Minimal HTML document as string
        """
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/3d-force-graph@1.72.2/dist/3d-force-graph.min.js"></script>
    <style>
{css_content}
    </style>
</head>
<body>
    <div id="visualization"></div>

    <script>
{js_content}
    </script>
</body>
</html>"""

    def build_custom_layout(
        self,
        title: str,
        css_content: str,
        js_content: str,
        custom_sections: Dict[str, str],
    ) -> str:
        """
        Build HTML structure with custom sections.

        Args:
            title: Page title
            css_content: CSS stylesheet content
            js_content: JavaScript code content
            custom_sections: Dictionary of section names to HTML content

        Returns:
            HTML document with custom sections
        """
        sections_html = ""
        for section_name, section_html in custom_sections.items():
            sections_html += f"\n    <!-- {section_name} -->\n    {section_html}"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/3d-force-graph@1.72.2/dist/3d-force-graph.min.js"></script>
    <style>
{css_content}
    </style>
</head>
<body>
    <div id="visualization"></div>{sections_html}

    <script>
{js_content}
    </script>
</body>
</html>"""

    def get_layout_options(self) -> Dict[str, bool]:
        """
        Get current layout options.

        Returns:
            Dictionary of layout options and their states
        """
        return self.layout_options.copy()

    def enable_section(self, section: str) -> None:
        """
        Enable a specific layout section.

        Args:
            section: Section name to enable
        """
        if section in self.layout_options:
            self.layout_options[section] = True

    def disable_section(self, section: str) -> None:
        """
        Disable a specific layout section.

        Args:
            section: Section name to disable
        """
        if section in self.layout_options:
            self.layout_options[section] = False

    def get_available_sections(self) -> list[str]:
        """
        Get list of available layout sections.

        Returns:
            List of section names that can be controlled
        """
        return list(self.layout_options.keys())
