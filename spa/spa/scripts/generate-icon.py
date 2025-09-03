#!/usr/bin/env python3
"""Generate app icons for Azure Tenant Grapher."""

import os

from PIL import Image, ImageDraw, ImageFont


def create_icon(size):
    """Create an icon with ATG text."""
    # Create a new image with a gradient background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw a gradient background (Azure blue theme)
    for i in range(size):
        color = (0, 120 - int(60 * (i / size)), 215 - int(50 * (i / size)), 255)
        draw.rectangle([(0, i), (size, i + 1)], fill=color)

    # Draw a circle border
    margin = size // 10
    draw.ellipse(
        [(margin, margin), (size - margin, size - margin)],
        outline=(255, 255, 255, 255),
        width=size // 30,
    )

    # Add text "ATG"
    text = "ATG"
    # Try to use a system font, fallback to default if not available
    try:
        # Use default font since we can't guarantee specific fonts exist
        font = ImageFont.load_default()
        # Calculate text size and position
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # For the default font, we'll draw larger text manually
        draw.text(
            ((size - text_width) // 2, (size - text_height) // 2),
            text,
            fill=(255, 255, 255, 255),
            font=font,
        )

        # Since default font is small, let's draw the text bigger manually
        # Draw each letter as a shape for better visibility
        letter_width = size // 5
        letter_height = size // 3
        start_x = (size - letter_width * 3) // 2
        start_y = (size - letter_height) // 2

        # Clear previous small text
        for i in range(size):
            color = (0, 120 - int(60 * (i / size)), 215 - int(50 * (i / size)), 255)
            if start_y <= i <= start_y + letter_height:
                draw.rectangle(
                    [(start_x, i), (start_x + letter_width * 3, i + 1)], fill=color
                )

        # Draw A
        a_points = [
            (start_x + letter_width // 2, start_y),
            (start_x, start_y + letter_height),
            (start_x + letter_width // 4, start_y + letter_height // 2),
            (start_x + 3 * letter_width // 4, start_y + letter_height // 2),
            (start_x + letter_width, start_y + letter_height),
        ]
        draw.line(
            [(a_points[0]), (a_points[1])], fill=(255, 255, 255, 255), width=size // 40
        )
        draw.line(
            [(a_points[0]), (a_points[4])], fill=(255, 255, 255, 255), width=size // 40
        )
        draw.line(
            [(a_points[2]), (a_points[3])], fill=(255, 255, 255, 255), width=size // 40
        )

        # Draw T
        t_x = start_x + letter_width
        draw.line(
            [(t_x, start_y), (t_x + letter_width, start_y)],
            fill=(255, 255, 255, 255),
            width=size // 40,
        )
        draw.line(
            [
                (t_x + letter_width // 2, start_y),
                (t_x + letter_width // 2, start_y + letter_height),
            ],
            fill=(255, 255, 255, 255),
            width=size // 40,
        )

        # Draw G
        g_x = start_x + 2 * letter_width
        draw.arc(
            [(g_x, start_y), (g_x + letter_width, start_y + letter_height)],
            start=315,
            end=270,
            fill=(255, 255, 255, 255),
            width=size // 40,
        )
        draw.line(
            [
                (g_x + letter_width // 2, start_y + letter_height // 2),
                (g_x + letter_width, start_y + letter_height // 2),
            ],
            fill=(255, 255, 255, 255),
            width=size // 40,
        )

    except Exception as e:
        print(f"Font error: {e}, using basic shapes")

    return img


def main():
    """Generate icons in various sizes."""
    assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    os.makedirs(assets_dir, exist_ok=True)

    # Icon sizes for different platforms
    sizes = {
        "icon.png": 512,  # Main icon
        "icon@2x.png": 1024,  # Retina display
        "icon.ico": 256,  # Windows
        "icon.icns": 512,  # macOS (we'll create PNG, needs conversion for real icns)
    }

    for filename, size in sizes.items():
        icon = create_icon(size)
        filepath = os.path.join(assets_dir, filename)

        if filename.endswith(".ico"):
            # For Windows .ico, save as PNG for now (would need special handling for real .ico)
            icon.save(filepath.replace(".ico", ".png"), "PNG")
            print(
                f"Created {filepath.replace('.ico', '.png')} (convert to .ico for Windows)"
            )
        else:
            icon.save(filepath, "PNG")
            print(f"Created {filepath}")

    print("\nIcons generated successfully!")
    print("Note: For production, you should:")
    print("1. Convert icon.png to icon.ico for Windows using a tool like ImageMagick")
    print("2. Convert icon.png to icon.icns for macOS using iconutil")


if __name__ == "__main__":
    main()
