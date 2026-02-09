# python-docx Library Tutorial

Generate .docx files with Python using `python-docx`.

**Important: Read this entire document before starting.** Critical formatting rules and common pitfalls are covered throughout - skipping sections may result in corrupted files or rendering issues.

## Setup
Assumes python-docx is already installed.
If not installed: `pip install python-docx`

```python
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_ORIENT
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

# Create & Save
doc = Document()
doc.add_paragraph("Hello World")
doc.save("output.docx")
```

## Text & Formatting
```python
# IMPORTANT: Never use \n for line breaks - always use separate paragraphs
# WRONG: p.add_run("Line 1\nLine 2")
# CORRECT: doc.add_paragraph("Line 1"); doc.add_paragraph("Line 2")

# Basic text with formatting
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
pf = p.paragraph_format
pf.space_before = Pt(10)
pf.space_after = Pt(10)
pf.left_indent = Inches(0.5)
pf.right_indent = Inches(0.5)

# Bold
run = p.add_run("Bold ")
run.bold = True

# Italic
run = p.add_run("Italic ")
run.italic = True

# Underline (True for single, or use WD_UNDERLINE enum for variants)
run = p.add_run("Underlined ")
run.underline = True
# For double underline: run.font.underline = WD_UNDERLINE.DOUBLE

# Font color, size, and name
run = p.add_run("Colored ")
run.font.color.rgb = RGBColor(0xFF, 0x00, 0x00)  # Red
run.font.size = Pt(14)
run.font.name = "Arial"

# Highlight
run = p.add_run("Highlighted ")
run.font.highlight_color = WD_COLOR_INDEX.YELLOW

# Strikethrough
run = p.add_run("Strikethrough ")
run.font.strike = True

# Superscript / Subscript
run = p.add_run("x")
sup = p.add_run("2")
sup.font.superscript = True

run = p.add_run(" H")
sub = p.add_run("2")
sub.font.subscript = True
p.add_run("O")

# Small caps
run = p.add_run("SMALL CAPS")
run.font.small_caps = True

# All caps
run = p.add_run("ALL CAPS")
run.font.all_caps = True
```

## Styles & Professional Formatting

```python
doc = Document()

# -- Set default font for entire document --
style = doc.styles["Normal"]
style.font.name = "Arial"
style.font.size = Pt(11)
style.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
style.paragraph_format.space_after = Pt(4)

# -- Customize heading styles --
for level, (size, color) in enumerate([
    (Pt(20), RGBColor(0x00, 0x00, 0x00)),  # Heading 1
    (Pt(16), RGBColor(0x33, 0x33, 0x33)),  # Heading 2
    (Pt(13), RGBColor(0x55, 0x55, 0x55)),  # Heading 3
], start=1):
    hstyle = doc.styles[f"Heading {level}"]
    hstyle.font.name = "Arial"
    hstyle.font.size = size
    hstyle.font.color.rgb = color
    hstyle.font.bold = True

# -- Use heading styles --
doc.add_heading("Document Title", level=0)   # Title style
doc.add_heading("Section Heading", level=1)  # Heading 1
doc.add_heading("Subsection", level=2)       # Heading 2

# -- Apply paragraph style by name --
p = doc.add_paragraph("Quoted text", style="Intense Quote")

# -- Page setup --
section = doc.sections[0]
section.page_width = Inches(8.27)    # A4 width
section.page_height = Inches(11.69)  # A4 height
section.top_margin = Inches(1)
section.bottom_margin = Inches(1)
section.left_margin = Inches(1)
section.right_margin = Inches(1)

doc.save("styled.docx")
```

**Professional Font Combinations:**
- **Arial (Headers) + Arial (Body)** - Most universally supported, clean and professional
- **Times New Roman (Headers) + Arial (Body)** - Classic serif headers with modern sans-serif body
- **Georgia (Headers) + Verdana (Body)** - Optimized for screen reading, elegant contrast

**Key Styling Principles:**
- **Set a default font** via `doc.styles["Normal"]` - Arial is universally supported
- **Customize built-in heading styles** (`Heading 1`, `Heading 2`, etc.) for consistency
- **Establish visual hierarchy** with different font sizes (titles > headers > body)
- **Add proper spacing** with `space_before` and `space_after` on paragraph format
- **Use colors sparingly**: Default to black and shades of gray for headings
- **Set consistent margins** (1 inch = `Inches(1)` is standard)


## Lists (ALWAYS USE BUILT-IN STYLES - NEVER USE UNICODE BULLETS)
```python
# Bullet list - use built-in "List Bullet" style
doc.add_paragraph("First bullet point", style="List Bullet")
doc.add_paragraph("Second bullet point", style="List Bullet")
doc.add_paragraph("Third bullet point", style="List Bullet")

# Numbered list - use built-in "List Number" style
doc.add_paragraph("First numbered item", style="List Number")
doc.add_paragraph("Second numbered item", style="List Number")
doc.add_paragraph("Third numbered item", style="List Number")

# Nested lists - use "List Bullet 2" / "List Number 2" for second level
doc.add_paragraph("Top level bullet", style="List Bullet")
doc.add_paragraph("Nested bullet", style="List Bullet 2")
doc.add_paragraph("Another nested", style="List Bullet 2")
doc.add_paragraph("Back to top level", style="List Bullet")

# CRITICAL: NEVER use unicode bullets like "* Item" or "\u2022 Item"
# WRONG:  p.add_run("\u2022 First item")
# CORRECT: doc.add_paragraph("First item", style="List Bullet")

# Bullet with mixed formatting (bold prefix + normal text)
p = doc.add_paragraph(style="List Bullet")
r1 = p.add_run("Bold prefix: ")
r1.bold = True
r1.font.name = "Arial"
r1.font.size = Pt(11)
r2 = p.add_run("rest of the bullet text")
r2.font.name = "Arial"
r2.font.size = Pt(11)

# IMPORTANT: "List Number" style creates a CONTINUOUS numbered list.
# To restart numbering, you need to manipulate the XML:
def restart_numbering(paragraph):
    """Reset numbering to 1 for this paragraph."""
    pPr = paragraph._p.get_or_add_pPr()
    numPr = pPr.find(qn("w:numPr"))
    if numPr is not None:
        # Add override to restart at 1
        ilvl = numPr.find(qn("w:ilvl"))
        num_id = numPr.find(qn("w:numId"))
        if ilvl is not None and num_id is not None:
            # Create a new abstract numbering to restart
            pass  # See XML manipulation section for advanced numbering
```

## Tables
```python
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

# -- Helper: set cell background color --
def set_cell_shading(cell, color_hex):
    """Set cell background. color_hex is like '00528A' (no #)."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shading = parse_xml(
        f'<w:shd {nsdecls("w")} w:fill="{color_hex}" w:val="clear"/>'
    )
    tcPr.append(shading)

# -- Helper: set cell borders --
def set_cell_border(cell, **kwargs):
    """Set cell borders. kwargs: top, bottom, left, right with dict of sz, color, val."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = tcPr.find(qn("w:tcBorders"))
    if tcBorders is None:
        tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}/>')
        tcPr.append(tcBorders)
    for edge, attrs in kwargs.items():
        el = parse_xml(
            f'<w:{edge} {nsdecls("w")} w:val="{attrs.get("val", "single")}" '
            f'w:sz="{attrs.get("sz", "4")}" w:space="0" '
            f'w:color="{attrs.get("color", "CCCCCC")}"/>'
        )
        tcBorders.append(el)

# -- Create a formatted table --
headers = ["Header 1", "Bullet Points"]
rows_data = [["Regular data", ["First bullet", "Second bullet"]]]

table = doc.add_table(rows=1 + len(rows_data), cols=len(headers))
table.alignment = WD_TABLE_ALIGNMENT.CENTER
table.style = "Table Grid"  # Adds visible borders

# Header row
hdr = table.rows[0]
for i, h in enumerate(headers):
    cell = hdr.cells[i]
    cell.text = ""  # Clear default paragraph
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(h)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    run.font.name = "Arial"
    set_cell_shading(cell, "00528A")  # Blue background

# Data rows
for r_idx, row_data in enumerate(rows_data):
    row = table.rows[r_idx + 1]
    bg = "F5F8FA" if r_idx % 2 == 0 else "FFFFFF"  # Alternating rows

    # Simple text cell
    cell = row.cells[0]
    cell.text = ""
    run = cell.paragraphs[0].add_run(row_data[0])
    run.font.size = Pt(10)
    run.font.name = "Arial"
    set_cell_shading(cell, bg)

    # Bullet list in cell
    cell = row.cells[1]
    cell.text = ""
    for j, bullet_text in enumerate(row_data[1]):
        if j == 0:
            p = cell.paragraphs[0]  # Reuse existing paragraph
        else:
            p = cell.add_paragraph()
        p.style = doc.styles["List Bullet"]
        p.add_run(bullet_text).font.size = Pt(10)
    set_cell_shading(cell, bg)

# Column widths
col_widths = [Inches(3), Inches(3)]
for row in table.rows:
    for i, w in enumerate(col_widths):
        row.cells[i].width = w

# Reduce cell padding
for row in table.rows:
    for cell in row.cells:
        for p in cell.paragraphs:
            pf = p.paragraph_format
            pf.space_before = Pt(2)
            pf.space_after = Pt(2)
```

**IMPORTANT: Table tips**
- Use `table.style = "Table Grid"` for visible borders on all cells
- Set column widths on EVERY row's cells (Word can override per-row)
- Use `set_cell_shading()` helper with `w:val="clear"` - never use `"solid"` (causes black background)
- Each cell always contains at least one paragraph; reuse `cell.paragraphs[0]` before calling `cell.add_paragraph()`
- Set `cell.text = ""` before formatting to clear the default empty run

**Precomputed Column Widths (Letter size with 1" margins = ~6.5" usable):**
- **2 columns:** `[Inches(3.25), Inches(3.25)]`
- **3 columns:** `[Inches(2.17), Inches(2.17), Inches(2.17)]`
- **A4 with 1" margins = ~6.27" usable**


## Images
```python
from docx.shared import Inches

# Basic image (sized by width, height auto-calculated)
doc.add_picture("image.png", width=Inches(4))

# Centered image
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(10)
p.paragraph_format.space_after = Pt(10)
run = p.add_run()
run.add_picture("image.png", width=Inches(4))

# Image with explicit width and height
doc.add_picture("image.png", width=Inches(4), height=Inches(3))

# Image from bytes (useful for generated charts)
from io import BytesIO
image_stream = BytesIO(image_bytes)
doc.add_picture(image_stream, width=Inches(5))
```


## Page Breaks
```python
# Simple page break
doc.add_page_break()

# Page break before a paragraph (keeps heading with content)
p = doc.add_paragraph("This starts on a new page")
p.paragraph_format.page_break_before = True

# Keep paragraph with next (prevents orphaned headings)
p = doc.add_heading("Section Title", level=1)
p.paragraph_format.keep_with_next = True
```


## Headers, Footers & Page Setup
```python
from docx.enum.section import WD_ORIENT

doc = Document()
section = doc.sections[0]

# -- Page size and orientation --
# A4 Portrait (default)
section.page_width = Inches(8.27)
section.page_height = Inches(11.69)
# Landscape: swap width/height and set orientation
# section.orientation = WD_ORIENT.LANDSCAPE
# section.page_width = Inches(11.69)
# section.page_height = Inches(8.27)

# -- Margins --
section.top_margin = Inches(1)
section.bottom_margin = Inches(1)
section.left_margin = Inches(1)
section.right_margin = Inches(1)

# -- Header --
header = section.header
header.is_linked_to_previous = False
hp = header.paragraphs[0]
hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
run = hp.add_run("Header Text")
run.font.size = Pt(9)
run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
run.font.name = "Arial"

# -- Footer with page numbers --
footer = section.footer
footer.is_linked_to_previous = False
fp = footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER

run = fp.add_run("Page ")
run.font.size = Pt(8)
run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
run.font.name = "Arial"

# Insert PAGE field (current page number)
run = fp.add_run()
fldChar1 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
run._r.append(fldChar1)
run = fp.add_run()
instrText = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> PAGE </w:instrText>')
run._r.append(instrText)
run = fp.add_run()
fldChar2 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
run._r.append(fldChar2)

run = fp.add_run(" of ")
run.font.size = Pt(8)
run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

# Insert NUMPAGES field (total pages)
run = fp.add_run()
fldChar1 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="begin"/>')
run._r.append(fldChar1)
run = fp.add_run()
instrText = parse_xml(f'<w:instrText {nsdecls("w")} xml:space="preserve"> NUMPAGES </w:instrText>')
run._r.append(instrText)
run = fp.add_run()
fldChar2 = parse_xml(f'<w:fldChar {nsdecls("w")} w:fldCharType="end"/>')
run._r.append(fldChar2)

# -- Different first page header/footer --
section.different_first_page_header_footer = True
first_header = section.first_page_header
fhp = first_header.paragraphs[0]
fhp.add_run("Title Page Header")

# -- Multiple sections (e.g., landscape section mid-document) --
new_section = doc.add_section()
new_section.orientation = WD_ORIENT.LANDSCAPE
new_section.page_width = Inches(11.69)
new_section.page_height = Inches(8.27)
```


## Tabs
```python
from docx.shared import Inches
from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER

p = doc.add_paragraph()
tab_stops = p.paragraph_format.tab_stops

# Left tab at 2 inches
tab_stops.add_tab_stop(Inches(2), WD_TAB_ALIGNMENT.LEFT)

# Center tab at 3.25 inches
tab_stops.add_tab_stop(Inches(3.25), WD_TAB_ALIGNMENT.CENTER)

# Right tab at 6.5 inches with dot leader
tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)

p.add_run("Left\tCenter\tRight")
```


## Hyperlinks (requires XML manipulation)
```python
# python-docx has no built-in hyperlink API - use XML workaround
def add_hyperlink(paragraph, url, text, color="0563C1", underline=True):
    """Add a hyperlink to a paragraph."""
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)

    hyperlink = parse_xml(f'<w:hyperlink {nsdecls("w")} r:id="{r_id}" {nsdecls("r")}/>')

    new_run = parse_xml(
        f'<w:r {nsdecls("w")}>'
        f'  <w:rPr>'
        f'    <w:color w:val="{color}"/>'
        f'    {"<w:u w:val=\"single\"/>" if underline else ""}'
        f'  </w:rPr>'
        f'  <w:t>{text}</w:t>'
        f'</w:r>'
    )
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink

# Usage
p = doc.add_paragraph("Visit ")
add_hyperlink(p, "https://www.example.com", "Example Site")
p.add_run(" for more info.")
```


## Constants & Quick Reference

**Units (all measurements via `docx.shared`):**
| Helper | Meaning | Example |
|--------|---------|---------|
| `Pt(12)` | Points (1/72 inch) | Font size, spacing |
| `Inches(1)` | Inches | Margins, widths |
| `Cm(2.54)` | Centimeters | Margins, widths |
| `Emu(914400)` | English Metric Units | Low-level (914400 EMU = 1 inch) |

**Alignment (`WD_ALIGN_PARAGRAPH`):**
`LEFT`, `CENTER`, `RIGHT`, `JUSTIFY`

**Highlight Colors (`WD_COLOR_INDEX`):**
`YELLOW`, `GREEN`, `PINK`, `BLUE`, `RED`, `DARK_BLUE`, `TEAL`, `TURQUOISE`, `VIOLET`, `DARK_YELLOW`, `GRAY_25`, `GRAY_50`, `BLACK`, `WHITE`

**Built-in Paragraph Styles:**
`"Normal"`, `"Heading 1"` through `"Heading 9"`, `"Title"`, `"Subtitle"`, `"List Bullet"`, `"List Bullet 2"`, `"List Number"`, `"List Number 2"`, `"Intense Quote"`, `"Quote"`, `"No Spacing"`

**Table Styles:**
`"Table Grid"` (visible borders), `"Light Shading"`, `"Light List"`, `"Light Grid"`, `"Medium Shading 1"`, etc.

**Page sizes:**
| Size | Width | Height |
|------|-------|--------|
| A4 | `Inches(8.27)` | `Inches(11.69)` |
| Letter | `Inches(8.5)` | `Inches(11)` |
| Legal | `Inches(8.5)` | `Inches(14)` |


## Critical Issues & Common Mistakes

- **NEVER use `\n` for line breaks** - always create separate paragraphs. `\n` in a run creates a line break XML element, not a proper paragraph break
- **NEVER use unicode bullet characters** (`\u2022`, `*`) for lists - always use `style="List Bullet"` for proper Word lists with correct indentation
- **Set `cell.text = ""` before formatting** - otherwise you get a leftover empty run before your styled content
- **Reuse `cell.paragraphs[0]`** - every cell starts with one paragraph; use it before calling `cell.add_paragraph()`
- **Use `w:val="clear"` in shading XML** - never `"solid"` (causes black background in some Word versions)
- **Set column widths on every row** - Word doesn't reliably inherit widths; set `row.cells[i].width` for each row
- **Font name must be set per-run** - setting `style.font.name` on "Normal" sets the default, but heading styles and explicit runs need their own `font.name`
- **`RGBColor` takes integers, not strings** - use `RGBColor(0xFF, 0x00, 0x00)` not `RGBColor("FF0000")`
- **Page numbers require XML field codes** - python-docx has no built-in page number API; use the `fldChar`/`instrText` pattern shown above
- **Hyperlinks require XML manipulation** - python-docx has no built-in hyperlink API; use the `add_hyperlink()` helper shown above
- **`doc.add_picture()` adds to body** - to center an image, create a paragraph first, then use `run.add_picture()` on a run within that paragraph
- **Heading level 0 is the Title style** - `doc.add_heading("Title", level=0)` uses the built-in Title style; levels 1-9 use Heading 1 through Heading 9
- **Always call `doc.save()` at the end** - unsaved documents are lost; there is no auto-save
- **Import `parse_xml` and `nsdecls` from `docx.oxml`** for any XML manipulation (shading, borders, page numbers, hyperlinks)
