"""Screenshot management utilities for demo walkthrough."""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import json

from playwright.async_api import Page


class ScreenshotManager:
    """Manages screenshot capture and organization."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize screenshot manager with configuration."""
        self.config = config
        self.screenshot_dir = Path(config.get('path', './screenshots'))
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots: List[Dict[str, Any]] = []
        self.metadata_file = self.screenshot_dir / "metadata.json"
        self._load_metadata()

    def _load_metadata(self):
        """Load existing screenshot metadata if available."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.screenshots = json.load(f)

    def _save_metadata(self):
        """Save screenshot metadata to file."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.screenshots, f, indent=2, default=str)

    async def capture(self, page: Page, scenario: str, step: int, description: str) -> str:
        """
        Capture a screenshot with metadata.

        Args:
            page: Playwright page object
            scenario: Current scenario name
            step: Step number or identifier
            description: Description of the screenshot

        Returns:
            Path to the saved screenshot
        """
        if not self.config.get('enabled', True):
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate filename based on pattern
        pattern = self.config.get('naming_pattern', '{timestamp}_{scenario}_{step}_{description}')
        filename = pattern.format(
            timestamp=timestamp,
            scenario=scenario,
            step=step,
            description=description.replace(' ', '_').lower()
        )

        # Add extension
        format_ext = self.config.get('format', 'png')
        filename = f"{filename}.{format_ext}"
        filepath = self.screenshot_dir / filename

        # Capture screenshot with options
        screenshot_options = {
            'path': str(filepath),
            'full_page': self.config.get('fullPage', False),
            'animations': self.config.get('animations', 'disabled')
        }

        if format_ext == 'jpeg':
            screenshot_options['quality'] = self.config.get('quality', 90)

        await page.screenshot(**screenshot_options)

        # Store metadata
        metadata = {
            'filename': filename,
            'filepath': str(filepath),
            'timestamp': timestamp,
            'scenario': scenario,
            'step': step,
            'description': description,
            'url': page.url,
            'viewport': await page.evaluate('() => ({ width: window.innerWidth, height: window.innerHeight })')
        }

        self.screenshots.append(metadata)
        self._save_metadata()

        return str(filepath)

    async def annotate(self, page: Page, elements: List[Dict[str, Any]]):
        """
        Add visual annotations to the page before screenshot.

        Args:
            page: Playwright page object
            elements: List of elements to annotate with selectors and labels
        """
        if not self.config.get('annotations', {}).get('enabled', False):
            return

        highlight_color = self.config.get('annotations', {}).get('highlight_color', '#FF0000')

        # Inject annotation script
        await page.evaluate("""
            (elements, color) => {
                elements.forEach(({selector, label}) => {
                    const element = document.querySelector(selector);
                    if (element) {
                        // Add highlight
                        element.style.outline = `3px solid ${color}`;
                        element.style.outlineOffset = '2px';

                        // Add label if provided
                        if (label) {
                            const labelDiv = document.createElement('div');
                            labelDiv.textContent = label;
                            labelDiv.style.cssText = `
                                position: absolute;
                                background: ${color};
                                color: white;
                                padding: 4px 8px;
                                font-size: 12px;
                                border-radius: 4px;
                                z-index: 10000;
                            `;
                            const rect = element.getBoundingClientRect();
                            labelDiv.style.left = `${rect.left}px`;
                            labelDiv.style.top = `${rect.top - 30}px`;
                            document.body.appendChild(labelDiv);
                        }
                    }
                });
            }
        """, elements, highlight_color)

    def get_screenshots_by_scenario(self, scenario: str) -> List[Dict[str, Any]]:
        """Get all screenshots for a specific scenario."""
        return [s for s in self.screenshots if s['scenario'] == scenario]

    def get_screenshots_by_timestamp(self, start: str, end: str) -> List[Dict[str, Any]]:
        """Get screenshots within a timestamp range."""
        return [
            s for s in self.screenshots
            if start <= s['timestamp'] <= end
        ]

    async def generate_gallery(self, config: Dict[str, Any]) -> str:
        """
        Generate an HTML gallery from screenshots.

        Args:
            config: Gallery configuration

        Returns:
            Path to the generated gallery HTML file
        """
        gallery_path = self.screenshot_dir / "gallery.html"

        # Group screenshots based on configuration
        group_by = config.get('group_by', 'scenario')
        groups = {}

        for screenshot in self.screenshots:
            key = screenshot.get(group_by, 'ungrouped')
            if key not in groups:
                groups[key] = []
            groups[key].append(screenshot)

        # Generate HTML
        html_content = self._generate_gallery_html(groups, config)

        with open(gallery_path, 'w') as f:
            f.write(html_content)

        return str(gallery_path)

    def _generate_gallery_html(self, groups: Dict[str, List[Dict]], config: Dict[str, Any]) -> str:
        """Generate HTML content for the gallery."""
        title = config.get('title', 'Screenshot Gallery')
        description = config.get('description', '')
        template = config.get('template', 'default')

        if template == 'grid':
            return self._generate_grid_template(groups, title, description, config)
        elif template == 'carousel':
            return self._generate_carousel_template(groups, title, description, config)
        else:
            return self._generate_default_template(groups, title, description, config)

    def _generate_default_template(self, groups: Dict[str, List[Dict]], title: str,
                                    description: str, config: Dict[str, Any]) -> str:
        """Generate default gallery template."""
        thumbnail_width = config.get('thumbnail_size', {}).get('width', 400)
        thumbnail_height = config.get('thumbnail_size', {}).get('height', 300)

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 10px;
        }}
        .description {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
        }}
        .group {{
            margin-bottom: 40px;
        }}
        .group-title {{
            font-size: 1.5em;
            color: #0078d4;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #0078d4;
        }}
        .screenshots {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax({thumbnail_width}px, 1fr));
            gap: 20px;
        }}
        .screenshot-card {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }}
        .screenshot-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        }}
        .screenshot-image {{
            width: 100%;
            height: {thumbnail_height}px;
            object-fit: cover;
            border-bottom: 1px solid #eee;
        }}
        .screenshot-info {{
            padding: 15px;
        }}
        .screenshot-title {{
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
        }}
        .screenshot-meta {{
            font-size: 0.9em;
            color: #666;
        }}
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.9);
        }}
        .modal-content {{
            margin: auto;
            display: block;
            max-width: 90%;
            max-height: 90%;
            margin-top: 50px;
        }}
        .modal-caption {{
            margin: auto;
            display: block;
            width: 80%;
            max-width: 700px;
            text-align: center;
            color: #ccc;
            padding: 10px 0;
        }}
        .close {{
            position: absolute;
            top: 15px;
            right: 35px;
            color: #f1f1f1;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
        }}
        .close:hover {{
            color: #bbb;
        }}
        .filters {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .filter-button {{
            background: white;
            border: 2px solid #0078d4;
            color: #0078d4;
            padding: 8px 16px;
            margin: 0 5px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .filter-button:hover {{
            background: #0078d4;
            color: white;
        }}
        .filter-button.active {{
            background: #0078d4;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <p class="description">{description}</p>

        <div class="filters">
            <button class="filter-button active" onclick="filterScreenshots('all')">All</button>
"""

        # Add filter buttons for each group
        for group_name in groups.keys():
            html += f'            <button class="filter-button" onclick="filterScreenshots(\'{group_name}\')">{group_name}</button>\n'

        html += """        </div>

"""

        # Add screenshot groups
        for group_name, screenshots in groups.items():
            html += f"""        <div class="group" data-group="{group_name}">
            <h2 class="group-title">{group_name}</h2>
            <div class="screenshots">
"""
            for screenshot in screenshots:
                relative_path = Path(screenshot['filename']).name
                html += f"""                <div class="screenshot-card" onclick="openModal('{relative_path}', '{screenshot['description']}')">
                    <img src="{relative_path}" alt="{screenshot['description']}" class="screenshot-image">
                    <div class="screenshot-info">
                        <div class="screenshot-title">{screenshot['description']}</div>
                        <div class="screenshot-meta">Step {screenshot['step']} • {screenshot['timestamp']}</div>
                    </div>
                </div>
"""

            html += """            </div>
        </div>

"""

        # Add modal and JavaScript
        html += """    </div>

    <div id="modal" class="modal">
        <span class="close" onclick="closeModal()">&times;</span>
        <img class="modal-content" id="modal-image">
        <div class="modal-caption" id="modal-caption"></div>
    </div>

    <script>
        function openModal(imageSrc, caption) {
            const modal = document.getElementById('modal');
            const modalImg = document.getElementById('modal-image');
            const modalCaption = document.getElementById('modal-caption');

            modal.style.display = "block";
            modalImg.src = imageSrc;
            modalCaption.innerHTML = caption;
        }

        function closeModal() {
            document.getElementById('modal').style.display = "none";
        }

        function filterScreenshots(group) {
            const allGroups = document.querySelectorAll('.group');
            const allButtons = document.querySelectorAll('.filter-button');

            // Update button states
            allButtons.forEach(button => {
                if (button.textContent.toLowerCase() === group.toLowerCase() ||
                    (group === 'all' && button.textContent === 'All')) {
                    button.classList.add('active');
                } else {
                    button.classList.remove('active');
                }
            });

            // Show/hide groups
            if (group === 'all') {
                allGroups.forEach(g => g.style.display = 'block');
            } else {
                allGroups.forEach(g => {
                    if (g.dataset.group === group) {
                        g.style.display = 'block';
                    } else {
                        g.style.display = 'none';
                    }
                });
            }
        }

        // Close modal on escape key
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeModal();
            }
        });

        // Close modal on background click
        document.getElementById('modal').addEventListener('click', function(event) {
            if (event.target === this) {
                closeModal();
            }
        });
    </script>
</body>
</html>
"""

        return html

    def _generate_grid_template(self, groups: Dict[str, List[Dict]], title: str,
                                 description: str, config: Dict[str, Any]) -> str:
        """Generate grid-style gallery template."""
        # Similar to default but with different layout
        return self._generate_default_template(groups, title, description, config)

    def _generate_carousel_template(self, groups: Dict[str, List[Dict]], title: str,
                                     description: str, config: Dict[str, Any]) -> str:
        """Generate carousel-style gallery template."""
        # Implement carousel template with sliding images
        # For now, fallback to default
        return self._generate_default_template(groups, title, description, config)

    def cleanup_old_screenshots(self, days: int = 7):
        """Clean up screenshots older than specified days."""
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_timestamp = cutoff_date.strftime("%Y%m%d_%H%M%S")

        old_screenshots = [
            s for s in self.screenshots
            if s['timestamp'] < cutoff_timestamp
        ]

        for screenshot in old_screenshots:
            filepath = Path(screenshot['filepath'])
            if filepath.exists():
                filepath.unlink()

        # Update metadata
        self.screenshots = [
            s for s in self.screenshots
            if s['timestamp'] >= cutoff_timestamp
        ]
        self._save_metadata()

        return len(old_screenshots)