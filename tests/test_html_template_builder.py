"""
Tests for HTML Template Builder Components

This module tests the visualization components including HtmlTemplateBuilder,
CssStyleBuilder, JavaScriptBuilder, and HtmlStructureBuilder.
"""

from unittest.mock import patch

import pytest

from src.visualization.css_style_builder import CssStyleBuilder
from src.visualization.html_structure_builder import HtmlStructureBuilder
from src.visualization.html_template_builder import (
    HtmlTemplateBuilder,
    VisualizationError,
)
from src.visualization.javascript_builder import JavaScriptBuilder


class TestHtmlTemplateBuilder:
    """Tests for the main HtmlTemplateBuilder class."""

    @pytest.fixture
    def template_builder(self):
        """Create a template builder instance."""
        return HtmlTemplateBuilder()

    @pytest.fixture
    def sample_graph_data(self):
        """Create sample graph data for testing."""
        return {
            "nodes": [
                {
                    "id": "node1",
                    "name": "Test Node 1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "color": "#6c5ce7",
                    "size": 10,
                    "properties": {"location": "eastus"},
                },
                {
                    "id": "node2",
                    "name": "Test Node 2",
                    "type": "Microsoft.Storage/storageAccounts",
                    "color": "#f9ca24",
                    "size": 8,
                    "properties": {"location": "westus"},
                },
            ],
            "links": [
                {
                    "source": "node1",
                    "target": "node2",
                    "type": "CONNECTED_TO",
                    "color": "#fd79a8",
                    "width": 2,
                }
            ],
            "node_types": [
                "Microsoft.Compute/virtualMachines",
                "Microsoft.Storage/storageAccounts",
            ],
            "relationship_types": ["CONNECTED_TO"],
        }

    def test_initialization(self, template_builder):
        """Test template builder initialization."""
        assert template_builder.theme == "default"
        assert isinstance(template_builder.css_builder, CssStyleBuilder)
        assert isinstance(template_builder.js_builder, JavaScriptBuilder)
        assert isinstance(template_builder.html_builder, HtmlStructureBuilder)

    def test_build_template_basic(self, template_builder, sample_graph_data):
        """Test basic template building."""
        html_content = template_builder.build_template(sample_graph_data)

        assert "<!DOCTYPE html>" in html_content
        assert "Azure Tenant Graph - 3D Visualization" in html_content
        assert "3d-force-graph" in html_content
        assert "originalGraphData" in html_content

    def test_build_template_with_title(self, template_builder, sample_graph_data):
        """Test template building with custom title."""
        custom_title = "Custom Visualization Title"
        html_content = template_builder.build_template(
            sample_graph_data, title=custom_title
        )

        assert custom_title in html_content

    def test_build_template_with_custom_css(self, template_builder, sample_graph_data):
        """Test template building with custom CSS."""
        custom_css = ".custom-style { color: red; }"
        html_content = template_builder.build_template(
            sample_graph_data, custom_css=custom_css
        )

        assert custom_css in html_content

    def test_build_template_with_custom_js(self, template_builder, sample_graph_data):
        """Test template building with custom JavaScript."""
        custom_js = "console.log('Custom JavaScript');"
        html_content = template_builder.build_template(
            sample_graph_data, custom_js=custom_js
        )

        assert custom_js in html_content

    def test_build_template_with_spec_path(self, template_builder, sample_graph_data):
        """Test template building with specification path."""
        with patch("os.path.exists", return_value=True):
            html_content = template_builder.build_template(
                sample_graph_data, specification_path="test_spec.md"
            )

            assert "View Tenant Specification" in html_content

    def test_validate_graph_data_valid(self, template_builder, sample_graph_data):
        """Test graph data validation with valid data."""
        # Should not raise an exception
        template_builder._validate_graph_data(sample_graph_data)

    def test_validate_graph_data_missing_keys(self, template_builder):
        """Test graph data validation with missing keys."""
        invalid_data = {"nodes": []}

        with pytest.raises(VisualizationError) as exc_info:
            template_builder._validate_graph_data(invalid_data)

        assert "missing required keys" in str(exc_info.value)
        assert exc_info.value.error_code == "VISUALIZATION_ERROR"

    def test_validate_graph_data_invalid_nodes_type(self, template_builder):
        """Test graph data validation with invalid nodes type."""
        invalid_data = {
            "nodes": "not a list",
            "links": [],
            "node_types": [],
            "relationship_types": [],
        }

        with pytest.raises(VisualizationError) as exc_info:
            template_builder._validate_graph_data(invalid_data)

        assert "nodes' must be a list" in str(exc_info.value)

    def test_validate_graph_data_missing_node_fields(self, template_builder):
        """Test graph data validation with missing node fields."""
        invalid_data = {
            "nodes": [{"id": "1"}],  # Missing name and type
            "links": [],
            "node_types": [],
            "relationship_types": [],
        }

        with pytest.raises(VisualizationError) as exc_info:
            template_builder._validate_graph_data(invalid_data)

        assert "missing required fields" in str(exc_info.value)

    def test_set_theme_valid(self, template_builder):
        """Test setting a valid theme."""
        template_builder.set_theme("dark")
        assert template_builder.theme == "dark"

    def test_set_theme_invalid(self, template_builder):
        """Test setting an invalid theme."""
        with pytest.raises(VisualizationError) as exc_info:
            template_builder.set_theme("invalid_theme")

        assert "Unsupported theme" in str(exc_info.value)

    def test_get_supported_themes(self, template_builder):
        """Test getting supported themes."""
        themes = template_builder.get_supported_themes()
        assert isinstance(themes, list)
        assert "default" in themes
        assert "dark" in themes
        assert "light" in themes

    def test_export_components(self, template_builder):
        """Test exporting individual components."""
        components = template_builder.export_components()

        assert "css" in components
        assert "js_template" in components
        assert "html_structure" in components
        assert "theme" in components
        assert components["theme"] == "default"

    @patch("glob.glob")
    @patch("os.path.isdir")
    @patch("os.path.exists")
    def test_generate_specification_link_auto_find(
        self, mock_exists, mock_isdir, mock_glob, template_builder
    ):
        """Test specification link generation with auto-discovery."""
        mock_exists.return_value = False
        mock_isdir.return_value = True
        mock_glob.return_value = ["specs/latest_tenant_spec.md"]

        link_html = template_builder._generate_specification_link(None)

        assert "View Tenant Specification" in link_html
        assert "latest_tenant_spec.md" in link_html

    def test_build_template_with_customization(
        self, template_builder, sample_graph_data
    ):
        """Test building template with customization options."""
        customization = {
            "title": "Custom Title",
            "theme_colors": {"primary": "#ff0000"},
            "feature_flags": {"auto_rotate": True},
        }

        html_content = template_builder.build_template_with_customization(
            sample_graph_data, customization
        )

        assert "Custom Title" in html_content


class TestCssStyleBuilder:
    """Tests for the CssStyleBuilder class."""

    @pytest.fixture
    def css_builder(self):
        """Create a CSS builder instance."""
        return CssStyleBuilder()

    def test_initialization(self, css_builder):
        """Test CSS builder initialization."""
        assert css_builder.theme == "default"
        assert isinstance(css_builder.color_overrides, dict)

    def test_build_styles(self, css_builder):
        """Test CSS styles building."""
        styles = css_builder.build_styles()

        assert "body {" in styles
        assert "#visualization {" in styles
        assert ".controls {" in styles
        assert ".node-info {" in styles

    def test_theme_colors(self, css_builder):
        """Test theme color retrieval."""
        colors = css_builder.get_theme_colors()

        assert "background" in colors
        assert "text" in colors
        assert "primary" in colors

    def test_set_theme(self, css_builder):
        """Test theme setting."""
        css_builder.set_theme("dark")
        assert css_builder.theme == "dark"

        colors = css_builder.get_theme_colors()
        assert colors["background"] == "#0d1117"

    def test_apply_color_overrides(self, css_builder):
        """Test applying color overrides."""
        overrides = {"primary": "#ff0000", "background": "#000000"}
        css_builder.apply_color_overrides(overrides)

        colors = css_builder.get_theme_colors()
        assert colors["primary"] == "#ff0000"
        assert colors["background"] == "#000000"

    def test_get_supported_themes(self, css_builder):
        """Test getting supported themes."""
        themes = css_builder.get_supported_themes()
        expected_themes = ["default", "light", "dark"]

        for theme in expected_themes:
            assert theme in themes

    def test_add_custom_css(self, css_builder):
        """Test adding custom CSS."""
        custom_css = ".custom { color: red; }"
        result = css_builder.add_custom_css(custom_css)

        assert custom_css in result
        assert "body {" in result  # Original styles should be present


class TestJavaScriptBuilder:
    """Tests for the JavaScriptBuilder class."""

    @pytest.fixture
    def js_builder(self):
        """Create a JavaScript builder instance."""
        return JavaScriptBuilder()

    @pytest.fixture
    def sample_graph_data(self):
        """Create sample graph data."""
        return {
            "nodes": [{"id": "1", "name": "Node 1", "type": "Test"}],
            "links": [{"source": "1", "target": "2", "type": "TEST_LINK"}],
            "node_types": ["Test"],
            "relationship_types": ["TEST_LINK"],
        }

    def test_initialization(self, js_builder):
        """Test JavaScript builder initialization."""
        assert isinstance(js_builder.feature_flags, dict)
        assert js_builder.feature_flags["cluster_labels"] is True

    def test_build_script(self, js_builder, sample_graph_data):
        """Test JavaScript script building."""
        script = js_builder.build_script(sample_graph_data)

        assert "originalGraphData" in script
        assert "ForceGraph3D" in script
        assert "initializeFilters" in script

    def test_apply_feature_flags(self, js_builder):
        """Test applying feature flags."""
        flags = {"auto_rotate": True, "search": False}
        js_builder.apply_feature_flags(flags)

        assert js_builder.feature_flags["auto_rotate"] is True
        assert js_builder.feature_flags["search"] is False

    def test_get_feature_flags(self, js_builder):
        """Test getting feature flags."""
        flags = js_builder.get_feature_flags()

        assert isinstance(flags, dict)
        assert "cluster_labels" in flags
        assert "auto_rotate" in flags

    def test_build_script_with_disabled_features(self, js_builder, sample_graph_data):
        """Test script building with disabled features."""
        js_builder.apply_feature_flags(
            {"cluster_labels": False, "search": False, "filters": False}
        )

        script = js_builder.build_script(sample_graph_data)

        assert "getClusterKey" not in script
        assert "searchBox" not in script
        assert "initializeFilters" not in script


class TestHtmlStructureBuilder:
    """Tests for the HtmlStructureBuilder class."""

    @pytest.fixture
    def html_builder(self):
        """Create an HTML structure builder instance."""
        return HtmlStructureBuilder()

    def test_initialization(self, html_builder):
        """Test HTML builder initialization."""
        assert isinstance(html_builder.layout_options, dict)
        assert html_builder.layout_options["show_controls"] is True

    def test_build_structure(self, html_builder):
        """Test HTML structure building."""
        title = "Test Title"
        css_content = "body { margin: 0; }"
        js_content = "console.log('test');"

        html = html_builder.build_structure(title, css_content, js_content)

        assert "<!DOCTYPE html>" in html
        assert title in html
        assert css_content in html
        assert js_content in html

    def test_build_minimal_structure(self, html_builder):
        """Test minimal HTML structure building."""
        title = "Minimal Test"
        css_content = "body { margin: 0; }"
        js_content = "console.log('minimal');"

        html = html_builder.build_minimal_structure(title, css_content, js_content)

        assert "<!DOCTYPE html>" in html
        assert title in html
        assert 'id="visualization"' in html

    def test_apply_layout_options(self, html_builder):
        """Test applying layout options."""
        options = {"show_controls": False, "show_stats": False}
        html_builder.apply_layout_options(options)

        assert html_builder.layout_options["show_controls"] is False
        assert html_builder.layout_options["show_stats"] is False

    def test_enable_disable_sections(self, html_builder):
        """Test enabling and disabling sections."""
        html_builder.disable_section("show_controls")
        assert html_builder.layout_options["show_controls"] is False

        html_builder.enable_section("show_controls")
        assert html_builder.layout_options["show_controls"] is True

    def test_get_available_sections(self, html_builder):
        """Test getting available sections."""
        sections = html_builder.get_available_sections()

        expected_sections = [
            "show_controls",
            "show_stats",
            "show_node_info",
            "show_cluster_labels",
        ]
        for section in expected_sections:
            assert section in sections

    def test_build_custom_layout(self, html_builder):
        """Test building custom layout."""
        title = "Custom Layout"
        css_content = "body { margin: 0; }"
        js_content = "console.log('custom');"
        custom_sections = {
            "custom_panel": '<div class="custom">Custom Content</div>',
            "another_section": '<div class="another">Another Section</div>',
        }

        html = html_builder.build_custom_layout(
            title, css_content, js_content, custom_sections
        )

        assert "Custom Content" in html
        assert "Another Section" in html
        assert "<!-- custom_panel -->" in html

    def test_build_structure_with_layout_options(self, html_builder):
        """Test building structure with layout options applied."""
        html_builder.apply_layout_options(
            {
                "show_controls": False,
                "show_stats": False,
                "show_node_info": True,
                "show_cluster_labels": True,
            }
        )

        html = html_builder.build_structure(
            "Test", "body { margin: 0; }", "console.log('test');"
        )

        # Should not contain controls or stats
        assert 'class="controls"' not in html
        assert 'class="stats"' not in html

        # Should contain node info and cluster labels
        assert 'class="node-info"' in html
        assert 'id="cluster-labels"' in html


def test_visualization_error_chaining():
    import pytest

    from src.visualization.html_template_builder import (
        HtmlTemplateBuilder,
        VisualizationError,
    )

    builder = HtmlTemplateBuilder()
    # Patch _validate_graph_data to raise a ValueError
    builder._validate_graph_data = lambda data: (_ for _ in ()).throw(
        ValueError("bad data")
    )
    with pytest.raises(VisualizationError) as exc_info:
        builder.build_template(
            {"nodes": [], "links": [], "node_types": [], "relationship_types": []}
        )
    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, ValueError)
