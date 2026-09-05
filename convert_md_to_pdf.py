"""
convert_md_to_pdf.py - High-Fidelity Markdown to PDF Converter using Microsoft Edge Headless.
Renders markdown documents into publication-quality A4 PDFs.
"""

import os
import re
import subprocess
import sys


def parse_markdown_to_html(md_content: str, title: str = "System Documentation") -> str:
    """Converts markdown content into clean, semantic HTML with CSS for print/PDF."""
    lines = md_content.splitlines()
    html_lines = []
    
    in_code_block = False
    code_lang = ""
    code_buffer = []
    
    in_table = False
    table_header_done = False
    table_rows = []
    
    in_list = False
    list_type = None

    def close_table():
        nonlocal in_table, table_header_done, table_rows
        if not in_table:
            return ""
        out = ['<div class="table-container"><table>']
        for idx, row in enumerate(table_rows):
            if idx == 0:
                out.append("<thead><tr>")
                for cell in row:
                    out.append(f"<th>{cell}</th>")
                out.append("</tr></thead><tbody>")
            else:
                out.append("<tr>")
                for cell in row:
                    out.append(f"<td>{cell}</td>")
                out.append("</tr>")
        out.append("</tbody></table></div>")
        in_table = False
        table_header_done = False
        table_rows = []
        return "\n".join(out)

    def close_list():
        nonlocal in_list, list_type
        if not in_list:
            return ""
        tag = "ul" if list_type == "ul" else "ol"
        in_list = False
        list_type = None
        return f"</{tag}>"

    def format_inline(text: str) -> str:
        # Escape HTML chars (except existing tags)
        t = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Inline code
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        # Bold
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        # Italic
        t = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", t)
        # Links: [text](url)
        t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
        return t

    for line in lines:
        stripped = line.strip()

        # Handle Code Blocks
        if stripped.startswith("```"):
            if in_code_block:
                code_text = "\n".join(code_buffer)
                # Escape code text
                code_text = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html_lines.append(f'<pre><code class="{code_lang}">{code_text}</code></pre>')
                code_buffer = []
                in_code_block = False
                code_lang = ""
            else:
                if in_table:
                    html_lines.append(close_table())
                if in_list:
                    html_lines.append(close_list())
                in_code_block = True
                code_lang = stripped[3:].strip()
                code_buffer = []
            continue

        if in_code_block:
            code_buffer.append(line)
            continue

        # Handle Tables (| col1 | col2 |)
        if stripped.startswith("|") and stripped.endswith("|"):
            if in_list:
                html_lines.append(close_list())
            # Check if separator row (| :--- | :--- |)
            if re.match(r"^\|(\s*:?-+:?\s*\|)+$", stripped):
                table_header_done = True
                continue
            
            cells = [format_inline(c.strip()) for c in stripped[1:-1].split("|")]
            if not in_table:
                in_table = True
                table_rows = [cells]
            else:
                table_rows.append(cells)
            continue
        else:
            if in_table:
                html_lines.append(close_table())

        # Handle Lists
        m_ul = re.match(r"^[-*]\s+(.*)", stripped)
        m_ol = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if m_ul:
            if not in_list or list_type != "ul":
                if in_list:
                    html_lines.append(close_list())
                in_list = True
                list_type = "ul"
                html_lines.append("<ul>")
            html_lines.append(f"<li>{format_inline(m_ul.group(1))}</li>")
            continue
        elif m_ol:
            if not in_list or list_type != "ol":
                if in_list:
                    html_lines.append(close_list())
                in_list = True
                list_type = "ol"
                html_lines.append("<ol>")
            html_lines.append(f"<li>{format_inline(m_ol.group(2))}</li>")
            continue
        else:
            if in_list:
                html_lines.append(close_list())

        # Empty line
        if not stripped:
            continue

        # Horizontal Rule
        if re.match(r"^---+$", stripped) or re.match(r"^\*\*\*+$", stripped):
            html_lines.append("<hr>")
            continue

        # Headings
        if stripped.startswith("# "):
            html_lines.append(f"<h1>{format_inline(stripped[2:])}</h1>")
            continue
        if stripped.startswith("## "):
            html_lines.append(f"<h2>{format_inline(stripped[3:])}</h2>")
            continue
        if stripped.startswith("### "):
            html_lines.append(f"<h3>{format_inline(stripped[4:])}</h3>")
            continue
        if stripped.startswith("#### "):
            html_lines.append(f"<h4>{format_inline(stripped[5:])}</h4>")
            continue

        # Blockquote
        if stripped.startswith("> "):
            html_lines.append(f"<blockquote><p>{format_inline(stripped[2:])}</p></blockquote>")
            continue

        # Standard Paragraph
        html_lines.append(f"<p>{format_inline(stripped)}</p>")

    if in_table:
        html_lines.append(close_table())
    if in_list:
        html_lines.append(close_list())
    if in_code_block:
        code_text = "\n".join(code_buffer)
        code_text = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_lines.append(f'<pre><code>{code_text}</code></pre>')

    body_html = "\n".join(html_lines)

    html_document = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    @page {{
      size: A4;
      margin: 16mm 14mm 16mm 14mm;
      @bottom-right {{
        content: counter(page);
      }}
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 10.5pt;
      line-height: 1.55;
      color: #1e293b;
      background-color: #ffffff;
    }}

    h1, h2, h3, h4 {{
      color: #0f172a;
      font-weight: 700;
      page-break-after: avoid;
    }}

    h1 {{
      font-size: 18pt;
      border-bottom: 2.5px solid #6366f1;
      padding-bottom: 6px;
      margin-top: 14pt;
      margin-bottom: 10pt;
      color: #312e81;
    }}

    h2 {{
      font-size: 14pt;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 4px;
      margin-top: 16pt;
      margin-bottom: 8pt;
      color: #1e1b4b;
    }}

    h3 {{
      font-size: 11.5pt;
      margin-top: 12pt;
      margin-bottom: 6pt;
      color: #3730a3;
    }}

    h4 {{
      font-size: 10.5pt;
      margin-top: 8pt;
      margin-bottom: 4pt;
      color: #475569;
    }}

    p {{
      margin-bottom: 7pt;
      text-align: justify;
    }}

    strong {{
      font-weight: 600;
      color: #0f172a;
    }}

    hr {{
      border: none;
      border-top: 1px solid #e2e8f0;
      margin: 14pt 0;
    }}

    ul, ol {{
      margin-left: 20pt;
      margin-bottom: 8pt;
    }}

    li {{
      margin-bottom: 3.5pt;
    }}

    pre {{
      background: #0f172a;
      color: #f8fafc;
      padding: 10pt 12pt;
      border-radius: 6px;
      font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
      font-size: 8pt;
      line-height: 1.4;
      overflow-x: auto;
      margin: 8pt 0 10pt 0;
      page-break-inside: avoid;
    }}

    code {{
      font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
      font-size: 9pt;
      background: #f1f5f9;
      color: #4338ca;
      padding: 1.5pt 4pt;
      border-radius: 3px;
    }}

    pre code {{
      background: transparent;
      color: inherit;
      padding: 0;
      border-radius: 0;
    }}

    .table-container {{
      width: 100%;
      margin: 10pt 0;
      page-break-inside: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 8.5pt;
      page-break-inside: auto;
    }}

    tr {{
      page-break-inside: avoid;
      page-break-after: auto;
    }}

    th {{
      background-color: #f1f5f9;
      color: #1e293b;
      font-weight: 600;
      text-align: left;
      padding: 5pt 6pt;
      border: 1px solid #cbd5e1;
    }}

    td {{
      padding: 4.5pt 6pt;
      border: 1px solid #e2e8f0;
      vertical-align: top;
    }}

    tbody tr:nth-child(even) {{
      background-color: #f8fafc;
    }}

    blockquote {{
      border-left: 3.5px solid #6366f1;
      background: #f8fafc;
      padding: 6pt 10pt;
      margin: 8pt 0;
      color: #475569;
      font-style: italic;
    }}

    a {{
      color: #4f46e5;
      text-decoration: none;
    }}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""
    return html_document


def convert_md_file_to_pdf(md_file: str, pdf_file: str) -> bool:
    """Reads md_file, converts to HTML, then invokes Microsoft Edge headless to generate PDF."""
    if not os.path.exists(md_file):
        print(f"Error: {md_file} not found!")
        return False

    with open(md_file, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_content = parse_markdown_to_html(md_text, title="Autonomous AI Interior Design Agent — System Documentation")
    
    html_file = md_file.replace(".md", ".temp.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    ]
    edge_path = None
    for cand in edge_candidates:
        if os.path.exists(cand):
            edge_path = cand
            break

    if not edge_path:
        print("Error: Microsoft Edge executable not found for PDF conversion!")
        return False

    abs_html = os.path.abspath(html_file)
    abs_pdf = os.path.abspath(pdf_file)

    cmd = [
        edge_path,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={abs_pdf}",
        abs_html
    ]

    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    # Clean up temp html
    if os.path.exists(html_file):
        os.remove(html_file)

    if os.path.exists(abs_pdf) and os.path.getsize(abs_pdf) > 0:
        print(f"Success! Generated {abs_pdf} (Size: {os.path.getsize(abs_pdf):,} bytes)")
        return True
    else:
        print(f"Failed to generate PDF. Edge output: {result.stderr}")
        return False


if __name__ == "__main__":
    src_md = sys.argv[1] if len(sys.argv) > 1 else "SYSTEM_DOCUMENTATION.md"
    dst_pdf = sys.argv[2] if len(sys.argv) > 2 else "SYSTEM_DOCUMENTATION.pdf"
    convert_md_file_to_pdf(src_md, dst_pdf)
