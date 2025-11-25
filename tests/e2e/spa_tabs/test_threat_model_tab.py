"""
E2E tests for the Threat Model Tab component.
Tests threat model generation, STRIDE analysis, and export functionality.
"""

import json
import re
import tempfile

import pytest
from playwright.async_api import Page, expect


class TestThreatModelTab:
    """Test suite for Threat Model Tab functionality."""

    @pytest.mark.asyncio
    async def test_navigate_to_threat_model_tab(self, page: Page, spa_server_url: str):
        """Test navigation to Threat Model tab."""
        await page.goto(spa_server_url)

        # Wait for app to load
        await page.wait_for_selector("[data-testid='app-container']", state="visible")

        # Click on Threat Model tab
        await page.click("[data-testid='tab-threat-model']")

        # Verify Threat Model content is visible
        await expect(
            page.locator("[data-testid='threat-model-content']")
        ).to_be_visible()

        # Check for main components
        await expect(page.locator("[data-testid='threat-model-input']")).to_be_visible()
        await expect(
            page.locator("[data-testid='generate-threat-model-btn']")
        ).to_be_visible()

    @pytest.mark.asyncio
    async def test_threat_model_generation(self, page: Page, spa_server_url: str):
        """Test threat model generation workflow."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Select target system
        await page.select_option("[data-testid='target-system-select']", "azure-tenant")

        # Configure threat model parameters
        await page.click("[data-testid='include-stride-checkbox']")
        await page.click("[data-testid='include-mitre-checkbox']")

        # Set scope
        await page.fill("[data-testid='scope-input']", "Production Azure Environment")

        # Mock API response
        mock_threat_model = {
            "id": "tm-001",
            "system": "azure-tenant",
            "threats": [
                {
                    "id": "T001",
                    "category": "Spoofing",
                    "description": "Unauthorized access through compromised credentials",
                    "impact": "High",
                    "likelihood": "Medium",
                    "mitigation": "Implement MFA and conditional access",
                },
                {
                    "id": "T002",
                    "category": "Tampering",
                    "description": "Unauthorized modification of tenant configuration",
                    "impact": "High",
                    "likelihood": "Low",
                    "mitigation": "Enable audit logging and change management",
                },
            ],
            "generated_at": "2024-01-15T10:00:00Z",
        }

        await page.route(
            "**/api/threat-model/generate",
            lambda route: route.fulfill(status=200, json=mock_threat_model),
        )

        # Generate threat model
        await page.click("[data-testid='generate-threat-model-btn']")

        # Check for loading state
        await expect(
            page.locator("[data-testid='generating-indicator']")
        ).to_be_visible()

        # Wait for results
        await expect(
            page.locator("[data-testid='threat-model-results']")
        ).to_be_visible(timeout=10000)

        # Verify threats are displayed
        threat_cards = page.locator("[data-testid='threat-card']")
        assert await threat_cards.count() == 2

        # Check first threat details
        # await expect(first_threat).to_contain_text("Spoofing")
        # await expect(first_threat).to_contain_text("High")

    @pytest.mark.asyncio
    async def test_stride_analysis(self, page: Page, spa_server_url: str):
        """Test STRIDE methodology analysis."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Enable STRIDE analysis
        await page.click("[data-testid='stride-analysis-toggle']")

        # Check STRIDE categories are visible
        stride_categories = [
            "spoofing",
            "tampering",
            "repudiation",
            "information-disclosure",
            "denial-of-service",
            "elevation-of-privilege",
        ]

        for category in stride_categories:
            await expect(
                page.locator(f"[data-testid='stride-{category}']")
            ).to_be_visible()

        # Generate STRIDE-based threat model
        await page.click("[data-testid='generate-stride-model']")

        # Mock STRIDE API response
        await page.route(
            "**/api/threat-model/stride",
            lambda route: route.fulfill(
                status=200,
                json={
                    "stride_analysis": {
                        "spoofing": [{"threat": "Identity spoofing", "risk": "High"}],
                        "tampering": [{"threat": "Data tampering", "risk": "Medium"}],
                        "repudiation": [{"threat": "Action denial", "risk": "Low"}],
                        "information_disclosure": [
                            {"threat": "Data leak", "risk": "High"}
                        ],
                        "denial_of_service": [
                            {"threat": "Service disruption", "risk": "Medium"}
                        ],
                        "elevation_of_privilege": [
                            {"threat": "Privilege escalation", "risk": "High"}
                        ],
                    }
                },
            ),
        )

        # Wait for STRIDE results
        await expect(page.locator("[data-testid='stride-results']")).to_be_visible(
            timeout=10000
        )

        # Verify each category has threats
        for category in stride_categories:
            category_section = page.locator(
                f"[data-testid='stride-{category}-threats']"
            )
            # await expect(category_section).to_be_visible()
            threats = category_section.locator("[data-testid='threat-item']")
            assert await threats.count() > 0

    @pytest.mark.asyncio
    async def test_threat_filtering(self, page: Page, spa_server_url: str):
        """Test threat filtering and search functionality."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Generate a threat model first
        await page.click("[data-testid='load-sample-model']")

        # Wait for sample model to load
        await expect(
            page.locator("[data-testid='threat-model-results']")
        ).to_be_visible()

        # Test search functionality
        search_input = page.locator("[data-testid='threat-search-input']")
        await search_input.fill("authentication")

        # Verify filtered results
        await page.wait_for_timeout(500)  # Debounce delay
        visible_threats = page.locator("[data-testid='threat-card']:visible")
        count = await visible_threats.count()
        assert count > 0

        # Clear search
        await search_input.clear()

        # Test impact filter
        await page.select_option("[data-testid='impact-filter']", "high")
        high_impact_threats = page.locator(
            "[data-testid='threat-card'][data-impact='high']"
        )
        assert await high_impact_threats.count() > 0

        # Test category filter
        await page.select_option("[data-testid='category-filter']", "spoofing")
        spoofing_threats = page.locator(
            "[data-testid='threat-card'][data-category='spoofing']"
        )
        assert await spoofing_threats.count() > 0

    @pytest.mark.asyncio
    async def test_threat_details_view(self, page: Page, spa_server_url: str):
        """Test threat detail view and editing."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Load sample model
        await page.click("[data-testid='load-sample-model']")
        await expect(
            page.locator("[data-testid='threat-model-results']")
        ).to_be_visible()

        # Click on first threat to view details
        first_threat = page.locator("[data-testid='threat-card']").first
        await first_threat.click()

        # Detail modal should open
        await expect(
            page.locator("[data-testid='threat-detail-modal']")
        ).to_be_visible()

        # Check detail fields
        await expect(page.locator("[data-testid='threat-id']")).to_be_visible()
        await expect(page.locator("[data-testid='threat-description']")).to_be_visible()
        await expect(page.locator("[data-testid='threat-impact']")).to_be_visible()
        await expect(page.locator("[data-testid='threat-likelihood']")).to_be_visible()
        await expect(page.locator("[data-testid='threat-mitigation']")).to_be_visible()

        # Edit threat
        await page.click("[data-testid='edit-threat-btn']")

        # Modify mitigation
        mitigation_input = page.locator("[data-testid='mitigation-input']")
        await mitigation_input.clear()
        await mitigation_input.fill(
            "Updated mitigation strategy with additional controls"
        )

        # Save changes
        await page.click("[data-testid='save-threat-btn']")

        # Verify changes are reflected
        await expect(page.locator("[data-testid='threat-mitigation']")).to_contain_text(
            "Updated mitigation"
        )

    @pytest.mark.asyncio
    async def test_export_threat_model(self, page: Page, spa_server_url: str):
        """Test exporting threat model in various formats."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Generate or load a threat model
        await page.click("[data-testid='load-sample-model']")
        await expect(
            page.locator("[data-testid='threat-model-results']")
        ).to_be_visible()

        # Test JSON export
        download_promise = page.wait_for_event("download")
        await page.click("[data-testid='export-json-btn']")
        download = await download_promise

        assert download.suggested_filename.endswith(".json")

        # Verify JSON content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            await download.save_as(tmp.name)
            with open(tmp.name) as f:
                data = json.load(f)
                assert "threats" in data
                assert len(data["threats"]) > 0

        # Test CSV export
        download_promise = page.wait_for_event("download")
        await page.click("[data-testid='export-csv-btn']")
        download = await download_promise

        assert download.suggested_filename.endswith(".csv")

        # Test PDF export
        download_promise = page.wait_for_event("download")
        await page.click("[data-testid='export-pdf-btn']")
        download = await download_promise

        assert download.suggested_filename.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_mitre_attack_mapping(self, page: Page, spa_server_url: str):
        """Test MITRE ATT&CK framework mapping."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Enable MITRE ATT&CK mapping
        await page.click("[data-testid='enable-mitre-toggle']")

        # Generate threat model with MITRE mapping
        await page.click("[data-testid='generate-threat-model-btn']")

        # Mock API response with MITRE techniques
        await page.route(
            "**/api/threat-model/generate",
            lambda route: route.fulfill(
                status=200,
                json={
                    "threats": [
                        {
                            "id": "T001",
                            "description": "Credential stuffing attack",
                            "mitre_techniques": ["T1110.004", "T1078"],
                            "mitre_tactics": ["Initial Access", "Persistence"],
                        }
                    ]
                },
            ),
        )

        # Wait for results
        await expect(
            page.locator("[data-testid='threat-model-results']")
        ).to_be_visible(timeout=10000)

        # Check MITRE tags are displayed
        mitre_tags = page.locator("[data-testid='mitre-technique-tag']")
        assert await mitre_tags.count() > 0

        # Click on MITRE tag for details
        await mitre_tags.first.click()

        # MITRE detail popup should appear
        await expect(page.locator("[data-testid='mitre-detail-popup']")).to_be_visible()
        await expect(
            page.locator("[data-testid='mitre-detail-popup']")
        ).to_contain_text("T1110")

    @pytest.mark.asyncio
    async def test_threat_model_comparison(self, page: Page, spa_server_url: str):
        """Test comparing multiple threat models."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Load first model
        await page.click("[data-testid='load-sample-model']")
        await expect(
            page.locator("[data-testid='threat-model-results']")
        ).to_be_visible()

        # Save current model
        await page.click("[data-testid='save-model-btn']")
        await page.fill("[data-testid='model-name-input']", "Model A")
        await page.click("[data-testid='confirm-save-btn']")

        # Generate another model
        await page.click("[data-testid='new-model-btn']")
        await page.click("[data-testid='generate-threat-model-btn']")

        # Save second model
        await page.click("[data-testid='save-model-btn']")
        await page.fill("[data-testid='model-name-input']", "Model B")
        await page.click("[data-testid='confirm-save-btn']")

        # Open comparison view
        await page.click("[data-testid='compare-models-btn']")

        # Select models to compare
        await page.select_option("[data-testid='compare-model-1']", "Model A")
        await page.select_option("[data-testid='compare-model-2']", "Model B")

        # View comparison
        await page.click("[data-testid='show-comparison-btn']")

        # Check comparison view
        await expect(page.locator("[data-testid='comparison-view']")).to_be_visible()
        await expect(page.locator("[data-testid='model-a-threats']")).to_be_visible()
        await expect(page.locator("[data-testid='model-b-threats']")).to_be_visible()
        await expect(
            page.locator("[data-testid='threat-diff-summary']")
        ).to_be_visible()

    @pytest.mark.asyncio
    async def test_threat_model_templates(self, page: Page, spa_server_url: str):
        """Test using threat model templates."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Open templates
        await page.click("[data-testid='use-template-btn']")

        # Template modal should open
        await expect(page.locator("[data-testid='template-modal']")).to_be_visible()

        # Check available templates
        templates = [
            "cloud-infrastructure",
            "web-application",
            "mobile-app",
            "iot-system",
        ]
        for template in templates:
            await expect(
                page.locator(f"[data-testid='template-{template}']")
            ).to_be_visible()

        # Select cloud infrastructure template
        await page.click("[data-testid='template-cloud-infrastructure']")

        # Template should be loaded
        await expect(page.locator("[data-testid='scope-input']")).to_have_value(
            "Cloud Infrastructure"
        )

        # Verify template-specific options are enabled
        await expect(
            page.locator("[data-testid='include-cloud-threats-checkbox']")
        ).to_be_checked()

    @pytest.mark.asyncio
    async def test_collaborative_features(self, page: Page, spa_server_url: str):
        """Test collaborative threat modeling features."""
        await page.goto(spa_server_url)
        await page.click("[data-testid='tab-threat-model']")

        # Load a threat model
        await page.click("[data-testid='load-sample-model']")
        await expect(
            page.locator("[data-testid='threat-model-results']")
        ).to_be_visible()

        # Add comment to a threat
        first_threat = page.locator("[data-testid='threat-card']").first
        await first_threat.hover()
        await page.click("[data-testid='add-comment-btn']")

        # Comment dialog should open
        await expect(page.locator("[data-testid='comment-dialog']")).to_be_visible()

        # Add comment
        await page.fill(
            "[data-testid='comment-input']", "This threat needs immediate attention"
        )
        await page.click("[data-testid='submit-comment-btn']")

        # Comment should be added
        await expect(page.locator("[data-testid='comment-badge']")).to_be_visible()
        await expect(page.locator("[data-testid='comment-count']")).to_contain_text("1")

        # Share threat model
        await page.click("[data-testid='share-model-btn']")

        # Share dialog should open
        await expect(page.locator("[data-testid='share-dialog']")).to_be_visible()

        # Generate share link
        await page.click("[data-testid='generate-share-link-btn']")

        # Share link should be displayed
        await expect(page.locator("[data-testid='share-link-input']")).to_have_value(
            re.compile(r".+")
        )
