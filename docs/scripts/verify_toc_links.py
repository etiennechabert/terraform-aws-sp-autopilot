#!/usr/bin/env python3
"""
Verify all Table of Contents links in README.md are functional.
"""

import re
import sys

def slugify(text):
    """Convert heading text to GitHub markdown anchor."""
    # Remove markdown links
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Convert to lowercase
    text = text.lower()
    # Replace spaces with hyphens
    text = text.replace(' ', '-')
    # Remove special characters except hyphens
    text = re.sub(r'[^a-z0-9\-]', '', text)
    # Remove multiple consecutive hyphens
    text = re.sub(r'-+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text

def extract_toc_links(content):
    """Extract all links from the Table of Contents section."""
    toc_links = []
    in_toc = False

    for line in content.split('\n'):
        if line.strip() == '## Table of Contents':
            in_toc = True
            continue
        elif in_toc and line.startswith('##'):
            break
        elif in_toc:
            # Match markdown links: [text](#anchor)
            matches = re.findall(r'\[([^\]]+)\]\(#([^\)]+)\)', line)
            for text, anchor in matches:
                toc_links.append((text, anchor))

    return toc_links

def extract_headings(content):
    """Extract all h2 headings and their anchors."""
    headings = {}

    for line in content.split('\n'):
        # Match h2 headings (## text)
        match = re.match(r'^##\s+(.+)$', line)
        if match:
            heading_text = match.group(1).strip()
            # Skip the ToC heading itself
            if heading_text != 'Table of Contents':
                anchor = slugify(heading_text)
                headings[anchor] = heading_text

    return headings

def main():
    # Read README.md
    with open('./README.md', 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract ToC links and headings
    toc_links = extract_toc_links(content)
    headings = extract_headings(content)

    print("Verifying Table of Contents links...")
    print("=" * 60)

    errors = []

    for text, anchor in toc_links:
        if anchor in headings:
            print(f"✓ [{text}](#{anchor}) -> ## {headings[anchor]}")
        else:
            print(f"✗ [{text}](#{anchor}) -> NOT FOUND")
            errors.append(f"Link #{anchor} does not match any heading")

    print("=" * 60)
    print(f"\nTotal ToC links: {len(toc_links)}")
    print(f"Total h2 headings: {len(headings)}")

    if errors:
        print(f"\n❌ FAILED: {len(errors)} broken link(s)")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("\n✅ SUCCESS: All ToC links are functional and point to correct sections!")
        sys.exit(0)

if __name__ == '__main__':
    main()
