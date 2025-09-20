"""Create a simple test PDF file."""

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    # Create PDF
    pdf_path = "sample_files/sample.pdf"
    c = canvas.Canvas(pdf_path, pagesize=letter)

    # Add content to first page
    c.setFont("Helvetica", 16)
    c.drawString(100, 750, "Test PDF Document")
    c.setFont("Helvetica", 12)
    c.drawString(100, 700, "This is a test PDF for the content processor.")
    c.drawString(100, 680, "It contains sample text for extraction testing.")
    c.drawString(100, 640, "Date: January 15, 2024")
    c.drawString(100, 620, "Author: Test System")

    # Add second page
    c.showPage()
    c.setFont("Helvetica", 14)
    c.drawString(100, 750, "Page 2 - Additional Content")
    c.setFont("Helvetica", 12)
    c.drawString(100, 700, "This page tests multi-page PDF processing.")

    c.save()
    print(f"Created {pdf_path}")

except ImportError:
    # Fallback: create a simple text file that looks like PDF
    print("reportlab not installed, creating placeholder PDF")
    with open("sample_files/sample.pdf", "wb") as f:
        # PDF header
        f.write(b"%PDF-1.4\n")
        f.write(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
        f.write(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
        f.write(b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n")
        f.write(b"%%EOF\n")
    print("Created minimal PDF placeholder")