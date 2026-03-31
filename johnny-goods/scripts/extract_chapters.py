#!/usr/bin/env python3
"""
extract_chapters.py — Extract individual chapter .txt files from Johnny Goods ODT master.

Usage:
    python3 extract_chapters.py <input_odt_file> [output_directory]

If output_directory is not specified, files are written to the current directory.

Output:
    chapter_01.txt through chapter_11.txt (individual chapters)
    all_sections_combined.txt (entire book: front matter + all chapters + back matter)

Each chapter file contains:
    - Chapter title with number prefix (e.g., "Chapter 1: The Three Fingers")
    - Chapter epigraph/quote (if present)
    - Chapter body text

Notes:
    - Requires odfpy: pip install odfpy --break-system-packages
    - Input file path is a command line argument, never hardcoded
    - Chapters are identified by Heading Level 2 (no "Chapter" prefix required in ODT)
    - Chapter numbering is added automatically to output files
    - Part headers (Level 1) are included in the combined file but NOT in individual chapter files
    - Front matter and back matter are included in the combined file
"""

import sys
import os

try:
    from odf.opendocument import load
    from odf.text import H, P
    from odf import teletype
except ImportError:
    print("ERROR: odfpy is required. Install with:")
    print("  pip install odfpy --break-system-packages")
    sys.exit(1)


def get_text_content(element):
    """Extract plain text from an ODF element, handling spans and formatting."""
    return teletype.extractText(element)


def extract_chapters(odt_path, output_dir="."):
    """Extract chapters from ODT file and write to individual text files."""
    if not os.path.exists(odt_path):
        print(f"ERROR: File not found: {odt_path}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    doc = load(odt_path)
    body = doc.body

    # The ODT body has one child: office:text. All content is inside it.
    # We must walk that wrapper's children, not body's direct children.
    text_wrapper = body.childNodes[0]
    all_elements = text_wrapper.childNodes

    print(f"  Document has {len(all_elements)} elements")

    # Walk all elements in document order, collecting everything for the combined file
    # and tracking chapters for individual files.
    sections = []          # All content in order for combined file
    chapters = {}          # Individual chapter data
    current_section = "frontmatter"
    current_chapter_num = None
    chapter_count = 0

    for element in all_elements:
        tag = element.qname[1] if hasattr(element, 'qname') else ""

        if tag == "h":
            level = element.getAttribute("outlinelevel") or "1"
            heading_text = get_text_content(element).strip()

            if level == "2":
                # Level 2 = chapter heading. Add "Chapter N:" prefix.
                chapter_count += 1
                current_chapter_num = chapter_count
                titled = f"Chapter {chapter_count}: {heading_text}"
                chapters[current_chapter_num] = {
                    "title": titled,
                    "raw_title": heading_text,
                    "content": [titled]
                }
                current_section = "chapter"
                # Add separator and chapter title to combined output
                sections.append("")
                sections.append("")
                sections.append("=" * 72)
                sections.append("")
                sections.append(titled)
                continue
            elif level == "1":
                # Level 1 = Part headers, Prologue, Epilogue, back matter sections
                current_section = "other"
                current_chapter_num = None
                sections.append("")
                sections.append("")
                sections.append("=" * 72)
                sections.append("")
                sections.append(heading_text)
                continue
            elif level == "4":
                # Level 4 = sub-headings (Cast sections, Recipe title, etc.)
                sections.append(heading_text)
                if current_chapter_num is not None:
                    chapters[current_chapter_num]["content"].append(heading_text)
                continue

        if tag == "p":
            para_text = get_text_content(element).strip()
            if para_text:
                sections.append(para_text)
                if current_chapter_num is not None:
                    chapters[current_chapter_num]["content"].append(para_text)

    if not chapters:
        print("ERROR: No chapters found. Check that the ODT has Level 2 headings.")
        sys.exit(1)

    # Write individual chapter files with "Chapter N:" prefix in filename and content
    for num, data in chapters.items():
        filename = f"chapter_{num:02d}.txt"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(data["content"]))
            f.write("\n")
        word_count = sum(len(line.split()) for line in data["content"])
        print(f"  {filename}: {data['title']} ({word_count:,} words)")

    # Write combined file with ALL content (front matter + chapters + back matter)
    combined_path = os.path.join(output_dir, "all_sections_combined.txt")
    with open(combined_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections))
        f.write("\n")

    total_words = len("\n".join(sections).split())
    print(f"\n  all_sections_combined.txt: complete book ({total_words:,} words)")
    print(f"  {len(chapters)} chapters extracted as individual files")
    print(f"\nDone. Output written to {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_chapters.py <input_odt_file> [output_directory]")
        print("Example: python3 extract_chapters.py source/Johnny_Goods_MASTER.odt chapters/")
        sys.exit(1)

    input_file = sys.argv[1]
    output_directory = sys.argv[2] if len(sys.argv) > 2 else "."

    print(f"Extracting chapters from: {input_file}")
    print(f"Output directory: {output_directory}\n")
    extract_chapters(input_file, output_directory)
