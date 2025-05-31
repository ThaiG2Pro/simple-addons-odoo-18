#!/usr/bin/env python3
"""
Test script to validate PDF generation works outside of Odoo
"""

def test_weasyprint():
    """Test WeasyPrint PDF generation"""
    try:
        from weasyprint import HTML
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #2c3e50; }
                h1 { color: #2c3e50; border-bottom: 2px solid #3498db; }
                .meta-info { background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }
            </style>
        </head>
        <body>
            <h1>Test AI Business Summary Report</h1>
            <div class="meta-info">
                <strong>Test Summary</strong><br>
                <strong>Generated:</strong> 2025-05-31<br>
                <strong>Status:</strong> Testing PDF generation
            </div>
            <h2>Test Content</h2>
            <p>This is a test of the PDF generation system.</p>
            <ul>
                <li>HTML to PDF conversion</li>
                <li>CSS styling support</li>
                <li>Base64 encoding</li>
            </ul>
        </body>
        </html>
        """
        
        # Generate PDF
        pdf_content = HTML(string=html_content).write_pdf()
        
        if pdf_content:
            print("✅ WeasyPrint PDF generation: SUCCESS")
            print(f"   PDF size: {len(pdf_content)} bytes")
            
            # Test base64 encoding
            import base64
            pdf_base64 = base64.b64encode(pdf_content).decode()
            print(f"   Base64 size: {len(pdf_base64)} characters")
            
            # Save test file
            with open('/tmp/test_summary.pdf', 'wb') as f:
                f.write(pdf_content)
            print("   Test PDF saved to: /tmp/test_summary.pdf")
            
            return True
        else:
            print("❌ WeasyPrint PDF generation: FAILED - No content returned")
            return False
            
    except ImportError:
        print("❌ WeasyPrint not installed")
        return False
    except Exception as e:
        print(f"❌ WeasyPrint error: {e}")
        return False

def test_reportlab():
    """Test ReportLab PDF generation"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        import io
        
        # Create PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []
        
        # Add content
        title = Paragraph("Test AI Summary Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        content = Paragraph("This is a test of ReportLab PDF generation.", styles['Normal'])
        story.append(content)
        
        # Build PDF
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        if pdf_content:
            print("✅ ReportLab PDF generation: SUCCESS")
            print(f"   PDF size: {len(pdf_content)} bytes")
            
            # Save test file
            with open('/tmp/test_summary_reportlab.pdf', 'wb') as f:
                f.write(pdf_content)
            print("   Test PDF saved to: /tmp/test_summary_reportlab.pdf")
            
            return True
        else:
            print("❌ ReportLab PDF generation: FAILED")
            return False
            
    except ImportError:
        print("❌ ReportLab not installed")
        return False
    except Exception as e:
        print(f"❌ ReportLab error: {e}")
        return False

if __name__ == "__main__":
    print("Testing PDF Generation Libraries...")
    print("=" * 50)
    
    weasyprint_ok = test_weasyprint()
    print()
    reportlab_ok = test_reportlab()
    
    print("\n" + "=" * 50)
    print("Summary:")
    print(f"WeasyPrint: {'✅ Available' if weasyprint_ok else '❌ Not available'}")
    print(f"ReportLab:  {'✅ Available' if reportlab_ok else '❌ Not available'}")
    
    if not weasyprint_ok and not reportlab_ok:
        print("\n⚠️  No PDF libraries available. Install with:")
        print("   pip install weasyprint")
        print("   pip install reportlab")
