#!/usr/bin/env python3
"""
PDF Text Extractor
Extracts text from PDF files for searching and reference
"""

import sys
import os

try:
    import PyPDF2
except ImportError:
    print("ERROR: PyPDF2 not installed")
    print("Install with: pip install PyPDF2")
    sys.exit(1)

def extract_pdf(pdf_path, output_path=None, search_term=None):
    """Extract text from PDF file"""
    
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    print(f"📖 Extracting: {os.path.basename(pdf_path)}")
    
    text_content = []
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            total_pages = len(reader.pages)
            
            print(f"📄 Total pages: {total_pages}")
            
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                text_content.append(f"\n{'='*80}\n")
                text_content.append(f"PAGE {i+1} of {total_pages}\n")
                text_content.append(f"{'='*80}\n\n")
                text_content.append(page_text)
                
                # Show progress
                if (i + 1) % 10 == 0:
                    print(f"  Processed {i+1}/{total_pages} pages...")
            
            full_text = ''.join(text_content)
            
            # Search for term if provided
            if search_term:
                print(f"\n🔍 Searching for: '{search_term}'")
                lines = full_text.split('\n')
                matches = []
                
                for line_num, line in enumerate(lines, 1):
                    if search_term.lower() in line.lower():
                        matches.append((line_num, line.strip()))
                
                if matches:
                    print(f"✅ Found {len(matches)} matches:")
                    for line_num, line in matches[:10]:  # Show first 10
                        print(f"  Line {line_num}: {line[:100]}...")
                    
                    if len(matches) > 10:
                        print(f"  ... and {len(matches) - 10} more")
                else:
                    print(f"❌ Term '{search_term}' not found")
            
            # Save to file if output path provided
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as out:
                    out.write(full_text)
                print(f"\n✅ Saved to: {output_path}")
            
            return full_text
            
    except Exception as e:
        print(f"❌ Error extracting PDF: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python extract_pdf.py <pdf_file> [output_file] [search_term]")
        print("\nExamples:")
        print('  python extract_pdf.py security.pdf')
        print('  python extract_pdf.py security.pdf security.txt')
        print('  python extract_pdf.py security.pdf security.txt "firewall"')
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    search_term = sys.argv[3] if len(sys.argv) > 3 else None
    
    extract_pdf(pdf_file, output_file, search_term)
    print("\n✅ Done!")

if __name__ == "__main__":
    main()
