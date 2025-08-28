#!/usr/bin/env python3
"""
Create a simple icon.png for the Azure Tenant Grapher app
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    # Create a 512x512 image with a blue gradient background
    size = 512
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a circle with Azure blue gradient effect
    center = size // 2
    radius = int(size * 0.45)
    
    # Outer circle (darker blue)
    draw.ellipse(
        [(center - radius - 10, center - radius - 10),
         (center + radius + 10, center + radius + 10)],
        fill=(0, 120, 212, 255)  # Azure blue
    )
    
    # Inner circle (lighter blue) 
    draw.ellipse(
        [(center - radius, center - radius),
         (center + radius, center + radius)],
        fill=(0, 150, 240, 255)  # Lighter Azure blue
    )
    
    # Add text "ATG" in the center
    try:
        # Try to use a system font
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=140)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    text = "ATG"
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center the text
    text_x = center - text_width // 2
    text_y = center - text_height // 2 - 20  # Slight offset up
    
    # Draw text shadow
    draw.text((text_x + 3, text_y + 3), text, font=font, fill=(0, 90, 170, 200))
    # Draw main text
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
    
    # Add a subtle graph/network pattern
    import random
    random.seed(42)
    
    # Draw some connection lines
    num_nodes = 8
    nodes = []
    for i in range(num_nodes):
        angle = (360 / num_nodes) * i
        import math
        x = center + int(radius * 0.6 * math.cos(math.radians(angle)))
        y = center + int(radius * 0.6 * math.sin(math.radians(angle)))
        nodes.append((x, y))
    
    # Draw lines between nodes
    for i, node1 in enumerate(nodes):
        for j, node2 in enumerate(nodes):
            if i < j and random.random() > 0.5:
                draw.line([node1, node2], fill=(255, 255, 255, 60), width=1)
    
    # Draw node dots
    for node in nodes:
        draw.ellipse(
            [(node[0] - 4, node[1] - 4), (node[0] + 4, node[1] + 4)],
            fill=(255, 255, 255, 180)
        )
    
    # Save the icon
    assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
    os.makedirs(assets_dir, exist_ok=True)
    
    icon_path = os.path.join(assets_dir, 'icon.png')
    img.save(icon_path, 'PNG')
    print(f"Icon created at: {icon_path}")
    
    # Also create smaller versions for different uses
    for size in [256, 128, 64, 32, 16]:
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(assets_dir, f'icon_{size}.png'), 'PNG')
        print(f"Created {size}x{size} icon")

if __name__ == "__main__":
    create_icon()