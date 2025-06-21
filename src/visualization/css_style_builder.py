"""
CSS Style Builder - Handles all CSS generation for the visualization.

This module provides the CssStyleBuilder class that generates all CSS styles
for the 3D graph visualization interface, including theming support.
"""

from typing import Dict


class CssStyleBuilder:
    """
    Handles generation of all CSS styles for the visualization interface.

    Provides theming support and modular CSS generation for different
    UI components of the 3D graph visualization.
    """

    def __init__(self, theme: str = "default") -> None:
        """
        Initialize the CSS style builder.

        Args:
            theme: Theme name (default, dark, light)
        """
        self.theme = theme
        self.color_overrides: Dict[str, str] = {}
        self._themes = self._initialize_themes()

    def _initialize_themes(self) -> Dict[str, Dict[str, str]]:
        """Initialize theme color schemes."""
        return {
            "default": {
                "background": "#1a1a1a",
                "text": "#ffffff",
                "primary": "#4ecdc4",
                "accent": "#fd79a8",
                "secondary": "#45b7d1",
                "surface": "rgba(0, 0, 0, 0.8)",
                "surface_light": "rgba(0, 0, 0, 0.9)",
                "border": "rgba(255, 255, 255, 0.15)",
                "hover": "rgba(78, 205, 196, 0.2)",
            },
            "light": {
                "background": "#f8f9fa",
                "text": "#2c3e50",
                "primary": "#007bff",
                "accent": "#e91e63",
                "secondary": "#6c757d",
                "surface": "rgba(255, 255, 255, 0.9)",
                "surface_light": "rgba(255, 255, 255, 0.95)",
                "border": "rgba(0, 0, 0, 0.15)",
                "hover": "rgba(0, 123, 255, 0.1)",
            },
            "dark": {
                "background": "#0d1117",
                "text": "#c9d1d9",
                "primary": "#58a6ff",
                "accent": "#f85149",
                "secondary": "#8b949e",
                "surface": "rgba(13, 17, 23, 0.8)",
                "surface_light": "rgba(13, 17, 23, 0.9)",
                "border": "rgba(240, 246, 252, 0.1)",
                "hover": "rgba(88, 166, 255, 0.15)",
            },
        }

    def build_styles(self) -> str:
        """
        Build complete CSS styles for the visualization.

        Returns:
            Complete CSS stylesheet as string
        """
        colors = self._get_theme_colors()

        return f"""
        {self._build_base_styles(colors)}
        {self._build_layout_styles(colors)}
        {self._build_control_styles(colors)}
        {self._build_info_panel_styles(colors)}
        {self._build_cluster_label_styles(colors)}
        {self._build_button_styles(colors)}
        {self._build_responsive_styles()}
        """

    def _get_theme_colors(self) -> Dict[str, str]:
        """Get colors for current theme with any overrides applied."""
        colors = self._themes.get(self.theme, self._themes["default"]).copy()
        colors.update(self.color_overrides)
        return colors

    def _build_base_styles(self, colors: Dict[str, str]) -> str:
        """Build base body and fundamental styles."""
        return f"""
        body {{
            margin: 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: {colors["background"]};
            color: {colors["text"]};
            overflow: hidden;
        }}

        #visualization {{
            width: 100vw;
            height: 100vh;
        }}

        * {{
            box-sizing: border-box;
        }}

        /* Always show Region node labels */
        .node.region text {{
            display: block !important;
        }}
        """

    def _build_layout_styles(self, colors: Dict[str, str]) -> str:
        """Build layout and positioning styles."""
        return f"""
        .controls {{
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 1000;
            background: {colors["surface"]};
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            max-width: 300px;
            max-height: 80vh;
            overflow-y: auto;
            border: 1px solid {colors["border"]};
        }}

        .stats {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            z-index: 1000;
            background: {colors["surface"]};
            padding: 15px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            font-size: 14px;
            border: 1px solid {colors["border"]};
        }}

        .node-info {{
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background: {colors["surface_light"]};
            padding: 20px;
            border-radius: 10px;
            backdrop-filter: blur(10px);
            max-width: 400px;
            max-height: 80vh;
            overflow-y: auto;
            display: none;
            border: 1px solid {colors["border"]};
        }}
        """

    def _build_control_styles(self, colors: Dict[str, str]) -> str:
        """Build control panel styles."""
        return f"""
        .controls h3 {{
            margin-top: 0;
            color: {colors["primary"]};
            border-bottom: 2px solid {colors["primary"]};
            padding-bottom: 5px;
        }}

        .search-box {{
            width: 100%;
            padding: 8px;
            margin-bottom: 15px;
            border: 1px solid {colors["primary"]};
            border-radius: 5px;
            background: {colors["surface"]};
            color: {colors["text"]};
            box-sizing: border-box;
        }}

        .search-box:focus {{
            outline: none;
            border-color: {colors["accent"]};
            box-shadow: 0 0 0 2px {colors["hover"]};
        }}

        .filter-section {{
            margin-bottom: 20px;
        }}

        .filter-section h4 {{
            margin: 0 0 10px 0;
            color: {colors["secondary"]};
            font-size: 14px;
            font-weight: 600;
        }}

        .filter-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
            cursor: pointer;
            padding: 3px;
            border-radius: 3px;
            transition: background-color 0.2s;
        }}

        .filter-item:hover {{
            background-color: {colors["hover"]};
        }}

        .filter-checkbox {{
            margin-right: 8px;
            accent-color: {colors["primary"]};
        }}

        .filter-color {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
            border: 1px solid {colors["border"]};
        }}

        .filter-label {{
            font-size: 14px;
            user-select: none;
            color: {colors["text"]};
        }}
        """

    def _build_info_panel_styles(self, colors: Dict[str, str]) -> str:
        """Build information panel styles."""
        return f"""
        .node-info h3 {{
            margin-top: 0;
            color: {colors["primary"]};
            border-bottom: 2px solid {colors["primary"]};
            padding-bottom: 5px;
        }}

        .property-row {{
            margin: 8px 0;
            display: flex;
            flex-wrap: wrap;
        }}

        .property-key {{
            font-weight: bold;
            color: {colors["accent"]};
            margin-right: 10px;
            min-width: 100px;
        }}

        .property-value {{
            color: {colors["text"]};
            word-break: break-all;
        }}

        .close-btn {{
            position: absolute;
            top: 10px;
            right: 15px;
            background: none;
            border: none;
            color: {colors["text"]};
            font-size: 20px;
            cursor: pointer;
            padding: 5px;
            border-radius: 3px;
            transition: background-color 0.2s;
        }}

        .close-btn:hover {{
            background-color: {colors["hover"]};
        }}

        .spec-link {{
            display: block;
            color: {colors["primary"]};
            text-decoration: none;
            padding: 8px 12px;
            border: 1px solid {colors["primary"]};
            border-radius: 5px;
            margin-top: 5px;
            transition: all 0.3s ease;
            text-align: center;
        }}

        .spec-link:hover {{
            background: {colors["primary"]};
            color: {colors["background"]};
        }}
        """

    def _build_cluster_label_styles(self, colors: Dict[str, str]) -> str:
        """Build cluster label overlay styles."""
        return f"""
        #cluster-labels {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            pointer-events: none;
            z-index: 1100;
        }}

        .cluster-label {{
            position: absolute;
            min-width: 40px;
            max-width: 200px;
            padding: 2px 8px;
            font-size: 13px;
            color: {colors["text"]};
            background: {colors["surface"]};
            border-radius: 6px;
            border: 1px solid {colors["border"]};
            text-align: center;
            white-space: nowrap;
            pointer-events: none;
            user-select: none;
            box-shadow: 0 2px 8px rgba(0,0,0,0.18);
            opacity: 0.85;
            transition: opacity 0.2s;
        }}
        """

    def _build_button_styles(self, colors: Dict[str, str]) -> str:
        """Build button and interactive element styles."""
        return f"""
        .reset-btn, .control-btn {{
            background: {colors["primary"]};
            color: {colors["background"]};
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 10px;
            width: 100%;
            font-family: inherit;
            font-size: 14px;
            transition: background-color 0.2s;
        }}

        .reset-btn:hover, .control-btn:hover {{
            background: {colors["secondary"]};
        }}

        .control-btn.active {{
            background: {colors["accent"]};
        }}

        .button-group {{
            display: flex;
            gap: 8px;
            margin-top: 10px;
        }}

        .button-group .control-btn {{
            flex: 1;
            margin-top: 0;
        }}
        """

    def _build_responsive_styles(self) -> str:
        """Build responsive design styles."""
        return """
        @media (max-width: 768px) {
            .controls {
                max-width: calc(100vw - 40px);
                max-height: 60vh;
            }

            .node-info {
                max-width: calc(100vw - 40px);
                max-height: 60vh;
            }

            .stats {
                font-size: 12px;
                padding: 10px;
            }
        }

        @media (max-width: 480px) {
            .controls {
                left: 10px;
                top: 10px;
                padding: 15px;
            }

            .stats {
                left: 10px;
                bottom: 10px;
            }

            .node-info {
                right: 10px;
                top: 10px;
            }
        }
        """

    def apply_color_overrides(self, overrides: Dict[str, str]) -> None:
        """
        Apply color overrides to the current theme.

        Args:
            overrides: Dictionary of color names to hex values
        """
        self.color_overrides.update(overrides)

    def get_supported_themes(self) -> list[str]:
        """
        Get list of supported theme names.

        Returns:
            List of available theme names
        """
        return list(self._themes.keys())

    def set_theme(self, theme: str) -> None:
        """
        Set the current theme.

        Args:
            theme: Theme name to set
        """
        if theme in self._themes:
            self.theme = theme
            self.color_overrides.clear()  # Clear overrides when switching themes

    def get_theme_colors(self) -> Dict[str, str]:
        """
        Get the current theme colors with any overrides.

        Returns:
            Dictionary of color names to values
        """
        return self._get_theme_colors()

    def add_custom_css(self, css: str) -> str:
        """
        Add custom CSS to the existing styles.

        Args:
            css: Custom CSS to append

        Returns:
            Complete CSS with custom styles appended
        """
        return self.build_styles() + "\n" + css
