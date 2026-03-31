"""
extract_substack.py

Reads all Substack HTML post files, strips the HTML formatting,
and saves each post as a clean plain-text file in data/substack/text/

Think of this like taking a stack of beautifully designed magazines
and photocopying just the words — no ads, no layout, just content.
"""

import os
from bs4 import BeautifulSoup

# Where the HTML files live
INPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'substack', 'posts')

# Where we'll save the clean text files
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'substack', 'text')

os.makedirs(OUTPUT_DIR, exist_ok=True)

html_files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.html')]
html_files.sort()

print(f"Found {len(html_files)} posts. Extracting text...\n")

for filename in html_files:
    input_path = os.path.join(INPUT_DIR, filename)
    output_filename = filename.replace('.html', '.txt')
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    with open(input_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # BeautifulSoup parses the HTML and lets us extract just the text
    soup = BeautifulSoup(html, 'html.parser')

    # Get the title
    title = soup.find('title')
    title_text = title.get_text(strip=True) if title else filename

    # Get the body text
    body = soup.get_text(separator='\n', strip=True)

    # Write the clean text file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"TITLE: {title_text}\n")
        f.write("=" * 60 + "\n\n")
        f.write(body)

    print(f"  Extracted: {output_filename}")

print(f"\nDone! {len(html_files)} text files saved to data/substack/text/")
