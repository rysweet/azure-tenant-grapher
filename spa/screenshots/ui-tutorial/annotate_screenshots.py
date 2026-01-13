#!/usr/bin/env python3
"""
Professional screenshot annotation script for Scale Operations UI Tutorial.
Creates annotated versions of screenshots with arrows, boxes, and labels.
"""

import os
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont


class AnnotationStyle:
    """Professional annotation styling constants."""

    # Colors
    HIGHLIGHT_BOX = (255, 215, 0, 180)  # Gold with transparency
    ARROW_COLOR = (255, 69, 0, 255)  # Orange-red
    TEXT_BG = (41, 128, 185, 230)  # Professional blue
    TEXT_COLOR = (255, 255, 255, 255)  # White
    CALLOUT_BOX = (52, 152, 219, 200)  # Lighter blue

    # Dimensions
    BOX_WIDTH = 4
    ARROW_WIDTH = 3
    TEXT_PADDING = 10
    FONT_SIZE = 16
    CALLOUT_FONT_SIZE = 14


class Annotation:
    """Represents a single annotation on an image."""

    def __init__(self, type: str, coords: Tuple, text: str = "", **kwargs):
        self.type = type  # 'box', 'arrow', 'label', 'callout'
        self.coords = coords
        self.text = text
        self.kwargs = kwargs


class ScreenshotAnnotator:
    """Annotates screenshots with professional overlays."""

    def __init__(self, source_dir: Path, output_dir: Path):
        self.source_dir = source_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Try to load a good font
        self.font = self._load_font(AnnotationStyle.FONT_SIZE)
        self.callout_font = self._load_font(AnnotationStyle.CALLOUT_FONT_SIZE)

    def _load_font(self, size: int):
        """Load the best available font."""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]

        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except:
                    pass

        # Fallback to default
        return ImageFont.load_default()

    def annotate(self, filename: str, annotations: List[Annotation], output_name: str):
        """Annotate a screenshot with given annotations."""

        source_path = self.source_dir / filename
        output_path = self.output_dir / output_name

        # Open image and create RGBA version for transparency
        img = Image.open(source_path).convert("RGBA")

        # Create overlay layer
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw each annotation
        for ann in annotations:
            if ann.type == "box":
                self._draw_box(draw, ann)
            elif ann.type == "arrow":
                self._draw_arrow(draw, ann)
            elif ann.type == "label":
                self._draw_label(draw, ann)
            elif ann.type == "callout":
                self._draw_callout(draw, ann)

        # Composite overlay onto image
        result = Image.alpha_composite(img, overlay)
        result = result.convert("RGB")
        result.save(output_path, "PNG", quality=95)

        print(f"Created: {output_name}")

    def _draw_box(self, draw: ImageDraw, ann: Annotation):
        """Draw a highlight box."""
        x1, y1, x2, y2 = ann.coords

        # Draw semi-transparent fill
        fill_color = ann.kwargs.get("fill", AnnotationStyle.HIGHLIGHT_BOX)
        draw.rectangle([x1, y1, x2, y2], fill=fill_color)

        # Draw border
        border_color = ann.kwargs.get("border", AnnotationStyle.ARROW_COLOR)
        for i in range(AnnotationStyle.BOX_WIDTH):
            draw.rectangle(
                [x1 + i, y1 + i, x2 - i, y2 - i], outline=border_color, width=1
            )

    def _draw_arrow(self, draw: ImageDraw, ann: Annotation):
        """Draw an arrow from point A to point B."""
        x1, y1, x2, y2 = ann.coords
        color = ann.kwargs.get("color", AnnotationStyle.ARROW_COLOR)

        # Draw line
        draw.line([x1, y1, x2, y2], fill=color, width=AnnotationStyle.ARROW_WIDTH)

        # Draw arrowhead
        import math

        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_length = 15
        arrow_width = 8

        # Calculate arrowhead points
        left_angle = angle + math.pi * 5 / 6
        right_angle = angle - math.pi * 5 / 6

        left_x = x2 + arrow_length * math.cos(left_angle)
        left_y = y2 + arrow_length * math.sin(left_angle)
        right_x = x2 + arrow_length * math.cos(right_angle)
        right_y = y2 + arrow_length * math.sin(right_angle)

        draw.polygon([(x2, y2), (left_x, left_y), (right_x, right_y)], fill=color)

    def _draw_label(self, draw: ImageDraw, ann: Annotation):
        """Draw a label with background."""
        x, y = ann.coords[:2]
        text = ann.text

        # Calculate text size
        bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Draw background
        padding = AnnotationStyle.TEXT_PADDING
        bg_x1 = x - padding
        bg_y1 = y - padding
        bg_x2 = x + text_width + padding
        bg_y2 = y + text_height + padding

        draw.rectangle(
            [bg_x1, bg_y1, bg_x2, bg_y2],
            fill=AnnotationStyle.TEXT_BG,
            outline=AnnotationStyle.ARROW_COLOR,
            width=2,
        )

        # Draw text
        draw.text((x, y), text, fill=AnnotationStyle.TEXT_COLOR, font=self.font)

    def _draw_callout(self, draw: ImageDraw, ann: Annotation):
        """Draw a callout box with multi-line text."""
        x, y, max_width = ann.coords[:3]
        text = ann.text

        # Split text into lines
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join([*current_line, word])
            bbox = draw.textbbox((0, 0), test_line, font=self.callout_font)
            if bbox[2] - bbox[0] <= max_width - 2 * AnnotationStyle.TEXT_PADDING:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        # Calculate box size
        line_height = 20
        padding = AnnotationStyle.TEXT_PADDING
        box_height = len(lines) * line_height + 2 * padding
        box_width = max_width

        # Draw background
        draw.rectangle(
            [x, y, x + box_width, y + box_height],
            fill=AnnotationStyle.CALLOUT_BOX,
            outline=AnnotationStyle.TEXT_COLOR,
            width=2,
        )

        # Draw text lines
        text_y = y + padding
        for line in lines:
            draw.text(
                (x + padding, text_y),
                line,
                fill=AnnotationStyle.TEXT_COLOR,
                font=self.callout_font,
            )
            text_y += line_height


def create_tutorial_screenshots():
    """Create all annotated tutorial screenshots."""

    source_dir = Path(
        "/home/azureuser/src/atg/worktrees/feat-issue-427-scale-operations/spa/screenshots/scale-operations"
    )
    output_dir = Path(
        "/home/azureuser/src/atg/worktrees/feat-issue-427-scale-operations/spa/screenshots/ui-tutorial"
    )

    annotator = ScreenshotAnnotator(source_dir, output_dir)

    # Tutorial 1: Getting Started
    print("\n=== Creating Tutorial 1: Getting Started ===")
    annotator.annotate(
        "01-initial-scale-up.png",
        [
            Annotation("box", (1010, 45, 1140, 75)),  # Scale Operations tab
            Annotation("arrow", (1075, 85, 1075, 120)),
            Annotation("label", (950, 130), "1. Click Scale Operations tab"),
            Annotation("box", (40, 255, 730, 295)),  # Scale Up button
            Annotation("arrow", (300, 305, 300, 340)),
            Annotation("label", (150, 350), "2. Select SCALE UP (Add Nodes)"),
            Annotation("box", (730, 255, 1420, 295)),  # Scale Down button
            Annotation("arrow", (1100, 305, 1100, 340)),
            Annotation("label", (950, 350), "Or SCALE DOWN (Sample)"),
            Annotation(
                "callout",
                (1450, 200, 400),
                "Start here: Choose whether to add test resources (Scale-Up) or remove them (Scale-Down)",
            ),
        ],
        "tutorial-01-getting-started.png",
    )

    # Tutorial 2: Scale-Up with Template Strategy
    print("\n=== Creating Tutorial 2: Template Strategy ===")
    annotator.annotate(
        "03-template-strategy-form.png",
        [
            Annotation("box", (740, 400, 1410, 445)),  # Strategy dropdown
            Annotation("arrow", (700, 422, 650, 422)),
            Annotation("label", (450, 407), "3. Strategy: Template-Based"),
            Annotation("box", (48, 555, 1410, 595)),  # Template file selector
            Annotation("arrow", (700, 575, 650, 575)),
            Annotation("label", (350, 560), "4. Template File (predefined patterns)"),
            Annotation("box", (48, 615, 1410, 680)),  # Scale factor slider
            Annotation("arrow", (200, 647, 150, 647)),
            Annotation("label", (50, 690), "5. Scale Factor: 2x (double resources)"),
            Annotation(
                "callout",
                (1450, 400, 400),
                "Template strategy: Generate nodes based on predefined YAML template patterns. Multiplies template by scale factor.",
            ),
        ],
        "tutorial-02-template-strategy.png",
    )

    # Tutorial 3: Scale-Up with Scenario
    print("\n=== Creating Tutorial 3: Scenario Selection ===")
    annotator.annotate(
        "04-scenario-hub-spoke.png",
        [
            Annotation("box", (740, 400, 1410, 445)),  # Strategy dropdown
            Annotation("arrow", (700, 422, 650, 422)),
            Annotation("label", (450, 407), "3. Strategy: Scenario-Based"),
            Annotation("box", (740, 470, 1410, 515)),  # Scenario dropdown
            Annotation("arrow", (700, 492, 650, 492)),
            Annotation("label", (400, 477), "4. Scenario: Hub-Spoke Network"),
            Annotation("box", (740, 535, 1410, 580)),  # Spokes parameter
            Annotation("arrow", (700, 557, 650, 557)),
            Annotation("label", (450, 542), "5. Number of Spokes: 3"),
            Annotation(
                "callout",
                (1450, 400, 400),
                "Scenario strategy: Generate realistic Azure architectures. Hub-Spoke creates central hub with multiple spoke VNets.",
            ),
        ],
        "tutorial-03-scenario-selection.png",
    )

    # Tutorial 4: Scale Factor Configuration
    print("\n=== Creating Tutorial 4: Scale Factor ===")
    annotator.annotate(
        "11-scale-factor-slider.png",
        [
            Annotation("box", (48, 615, 1410, 680)),  # Scale factor slider
            Annotation("arrow", (200, 647, 150, 647)),
            Annotation("label", (50, 690), "6. Drag slider to adjust scale"),
            Annotation(
                "callout",
                (1450, 600, 400),
                "Scale Factor controls operation intensity. For Template: multiplies resources (2x = double). For Random: controls count.",
            ),
            Annotation("box", (48, 760, 295, 785)),  # Validation checkbox
            Annotation("arrow", (320, 772, 370, 772)),
            Annotation("label", (380, 757), "7. Enable validation (recommended)"),
        ],
        "tutorial-04-scale-factor.png",
    )

    # Tutorial 5: Preview & Execute
    print("\n=== Creating Tutorial 5: Preview & Execute ===")
    annotator.annotate(
        "08-ready-for-execution.png",
        [
            Annotation("box", (48, 900, 340, 945)),  # Preview button
            Annotation("arrow", (194, 955, 194, 990)),
            Annotation("label", (100, 1000), "8. PREVIEW first"),
            Annotation("box", (360, 900, 652, 945)),  # Execute button
            Annotation("arrow", (506, 955, 506, 990)),
            Annotation("label", (390, 1000), "9. Then EXECUTE"),
            Annotation(
                "callout",
                (700, 900, 500),
                "IMPORTANT: Always preview before executing! Preview shows exactly what will be created or removed without making changes.",
            ),
        ],
        "tutorial-05-preview-execute.png",
    )

    # Tutorial 6: Quick Actions
    print("\n=== Creating Tutorial 6: Quick Actions ===")
    annotator.annotate(
        "09-quick-actions.png",
        [
            Annotation("box", (672, 900, 888, 945)),  # Clean button
            Annotation("arrow", (780, 955, 780, 990)),
            Annotation("label", (650, 1000), "CLEAN: Remove scaled nodes"),
            Annotation("box", (908, 900, 1124, 945)),  # Validate button
            Annotation("arrow", (1016, 955, 1016, 990)),
            Annotation("label", (880, 1000), "VALIDATE: Check integrity"),
            Annotation("box", (1144, 900, 1360, 945)),  # Stats button
            Annotation("arrow", (1252, 955, 1252, 990)),
            Annotation("label", (1120, 1000), "STATS: View metrics"),
            Annotation(
                "callout",
                (1400, 900, 450),
                "Quick Actions: Post-operation tools. CLEAN removes test data, VALIDATE checks graph integrity, STATS shows detailed metrics.",
            ),
        ],
        "tutorial-06-quick-actions.png",
    )

    # Tutorial 7: Validation Options
    print("\n=== Creating Tutorial 7: Validation Options ===")
    annotator.annotate(
        "10-validation-options.png",
        [
            Annotation("box", (48, 715, 1410, 880)),  # Validation section
            Annotation("arrow", (200, 797, 150, 797)),
            Annotation("label", (50, 890), "Validation Options"),
            Annotation(
                "callout",
                (1450, 750, 400),
                "Validation runs before and after operations to verify: graph integrity, relationship consistency, constraint compliance, and data correctness.",
            ),
        ],
        "tutorial-07-validation-options.png",
    )

    # Tutorial 8: Scale-Down Mode
    print("\n=== Creating Tutorial 8: Scale-Down Mode ===")
    annotator.annotate(
        "06-scale-down-forest-fire.png",
        [
            Annotation("box", (730, 255, 1420, 295)),  # Scale Down button
            Annotation("arrow", (1075, 305, 1075, 340)),
            Annotation("label", (920, 350), "Switch to SCALE DOWN mode"),
            Annotation("box", (740, 400, 1410, 445)),  # Strategy
            Annotation("arrow", (700, 422, 650, 422)),
            Annotation("label", (400, 407), "Strategy: Forest Fire (cascading)"),
            Annotation("box", (740, 470, 1410, 515)),  # Start node
            Annotation("arrow", (700, 492, 650, 492)),
            Annotation("label", (380, 477), "Start Node: Where to begin removal"),
            Annotation(
                "callout",
                (1450, 400, 400),
                "Scale-Down: Remove resources for testing cleanup or reduction. Forest Fire removes nodes in cascading pattern from start node.",
            ),
        ],
        "tutorial-08-scale-down.png",
    )

    print("\n=== Tutorial screenshots created successfully! ===")


if __name__ == "__main__":
    create_tutorial_screenshots()
