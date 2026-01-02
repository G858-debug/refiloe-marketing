#!/usr/bin/env python3
"""Generate PWA icons from SVG using Refiloe brand colors."""

import os

# Create icons directory
os.makedirs('static/icons', exist_ok=True)

# Refiloe brand gradient SVG icon
svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#D4A574"/>
      <stop offset="100%" style="stop-color:#8B7355"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="100" fill="url(#grad)"/>
  <text x="256" y="340" font-family="Arial, sans-serif" font-size="280" font-weight="bold" fill="white" text-anchor="middle">R</text>
</svg>'''

# Save SVG
with open('static/icons/icon.svg', 'w') as f:
    f.write(svg_content)

print("✅ Created static/icons/icon.svg with Refiloe brand colors")
print("   Primary: #D4A574 (warm beige)")
print("   Dark: #8B7355 (brown)")
print("")
print("⚠️  To create PNG icons, either:")
print("   1. Use https://realfavicongenerator.net with the SVG")
print("   2. Install cairosvg: pip install cairosvg")
print("   3. Manually create 192x192 and 512x512 PNGs in Canva")

# Try to generate PNGs if cairosvg is available
try:
    import cairosvg

    cairosvg.svg2png(bytestring=svg_content.encode(), write_to='static/icons/icon-192.png', output_width=192, output_height=192)
    cairosvg.svg2png(bytestring=svg_content.encode(), write_to='static/icons/icon-512.png', output_width=512, output_height=512)
    print("")
    print("✅ Created icon-192.png and icon-512.png")
except ImportError:
    print("")
    print("ℹ️  Install cairosvg to auto-generate PNGs: pip install cairosvg")
