#!/usr/bin/env python3
"""
Create placeholder image for lazy loading

Creates a simple gray placeholder image for book covers.
"""

from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

def create_placeholder():
    """Create placeholder image"""
    
    # Create directories if needed
    static_dir = Path('app/static/images')
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Create placeholder image
    width, height = 200, 300
    
    # Create image with light gray background
    img = Image.new('RGB', (width, height), color='#e0e0e0')
    draw = ImageDraw.Draw(img)
    
    # Try to add book emoji or icon
    try:
        # Try to use a font that supports emoji
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 60)
    except:
        try:
            font = ImageFont.truetype('/System/Library/Fonts/Apple Color Emoji.ttc', 60)
        except:
            font = ImageFont.load_default()
    
    # Add book icon/emoji
    text = "📚"
    
    try:
        # Get text size
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Center text
        position = ((width - text_width) // 2, (height - text_height) // 2)
        draw.text(position, text, fill='#999999', font=font)
    except:
        # Fallback: draw a simple rectangle
        margin = 20
        draw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline='#999999',
            width=2
        )
    
    # Save image
    output_path = static_dir / 'book-placeholder.png'
    img.save(output_path, 'PNG', optimize=True)
    
    print(f"✅ Placeholder image created: {output_path}")
    print(f"   Size: {width}x{height}px")
    print(f"   File size: {output_path.stat().st_size} bytes")
    
    return output_path

if __name__ == "__main__":
    create_placeholder()
