"""PDF export for ResumeDocument, sharing the canonical Word layout."""
from html import escape
import base64
from io import BytesIO
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import time
from typing import Any, Dict, Iterable, List

import fitz
from docx.enum.text import WD_ALIGN_PARAGRAPH
from loguru import logger

from .export_docx import TEMPLATE_THEMES, build_docx
from .layout import get_resume_layout
from .mapping import contact_line_parts
from .photo import photo_bytes


def _text(value: Any) -> str:
    return escape(str(value or "").strip())


def _nonempty(values: Iterable[Any]) -> List[str]:
    return [_text(value) for value in values if str(value or "").strip()]


def _bullets(values: Any, bold: bool = False) -> str:
    if not isinstance(values, list):
        return ""
    items = "".join(f"<li>{_text(value)}</li>" for value in values if str(value or "").strip())
    return f'<ul class="{"bold" if bold else ""}">{items}</ul>' if items else ""


def _two_column_table(entries: List[str], cards: bool = False) -> str:
    if not entries:
        return ""
    rows = []
    spacer = "&nbsp;" * 96
    for index in range(0, len(entries), 2):
        left = entries[index]
        right = entries[index + 1] if index + 1 < len(entries) else ""
        rows.append(
            f'<tr><td><div class="column-box"><div class="column-spacer">{spacer}</div>{left}</div></td>'
            f'<td><div class="column-box"><div class="column-spacer">{spacer}</div>{right}</div></td></tr>'
        )
    class_name = "two-column cards" if cards else "two-column"
    return f'<table class="{class_name}" width="100%">{"".join(rows)}</table>'


def _build_pdf_with_story(resume_document: Dict[str, Any]) -> bytes:
    """Fallback PDF renderer used when a DOCX-compatible office engine is unavailable."""
    template_id = resume_document.get("templateId")
    if template_id not in TEMPLATE_THEMES:
        template_id = "tech-elegant-v1"
    theme = TEMPLATE_THEMES[template_id]
    primary = "#" + "".join(f"{value:02X}" for value in theme["primary"])
    secondary = "#" + "".join(f"{value:02X}" for value in theme["secondary"])
    body_color = "#" + "".join(f"{value:02X}" for value in theme["body"])
    section_rule = f"#{theme['section_rule']}"

    formatting = resume_document.get("formatting") or {}
    entry_formatting = formatting.get("entries") if isinstance(formatting, dict) else {}
    raw_line_spacing = formatting.get("lineSpacing") if isinstance(formatting, dict) else None
    try:
        line_spacing = min(1.8, max(1.15, float(raw_line_spacing)))
    except (TypeError, ValueError):
        line_spacing = 1.45
    if not isinstance(entry_formatting, dict):
        entry_formatting = {}

    def is_bold(item: Dict[str, Any]) -> bool:
        item_style = entry_formatting.get(item.get("id"), {})
        return isinstance(item_style, dict) and item_style.get("bold") is True

    basics = resume_document.get("basics") or {}
    name = _text(basics.get("name") or resume_document.get("title") or "简历")
    headline = _text(basics.get("headline"))
    goal = resume_document.get("goal")
    if isinstance(goal, dict):
        target_role = _text(goal.get("target_role"))
        target_context = " · ".join(
            _text(value) for value in (goal.get("target_organization"), goal.get("research_direction"))
            if str(value or "").strip()
        )
    else:
        target_role = _text(resume_document.get("targetRole"))
        target_context = ""
    target_direction_html = (
        f'<p class="target-role">{target_role}</p>' if target_role else ""
    ) + (
        f'<p class="target-context">{target_context}</p>' if target_context else ""
    )
    contacts = [
        text
        for text, _path in contact_line_parts(basics, include_github=template_id == "campus-sidebar-v1")
    ]

    sections: Dict[str, str] = {}

    education_html = []
    for item in resume_document.get("education") or []:
        bold = is_bold(item)
        detail = " · ".join(_nonempty([item.get("major"), item.get("degree"), item.get("gpa")]))
        dates = " - ".join(_nonempty([item.get("startDate"), item.get("endDate")]))
        coursework = _text(item.get("coursework"))
        education_html.append(
            f'<div class="entry {"bold" if bold else ""}"><div class="entry-head"><strong>{_text(item.get("school"))}</strong><span>{dates}</span></div>'
            f'<p>{detail}</p>{f"<p>{coursework}</p>" if coursework else ""}{_bullets(item.get("highlights"), bold)}</div>'
        )
    sections["education"] = "".join(education_html)

    for key in ("experiences", "projects", "research", "volunteering"):
        entries = []
        for item in resume_document.get(key) or []:
            bold = is_bold(item)
            title = item.get("company") or item.get("organization") or item.get("name") or item.get("title")
            subtitle = item.get("role") or ""
            dates = " - ".join(_nonempty([item.get("startDate"), item.get("endDate")]))
            tech = " / ".join(_nonempty(item.get("techStack") or []))
            entries.append(
                f'<div class="entry {"bold" if bold else ""}"><div class="entry-head"><strong>{_text(title)}</strong><span>{dates}</span></div>'
                f'<p>{_text(subtitle)}</p>{f"<p>技术栈：{tech}</p>" if tech else ""}{_bullets(item.get("bullets"), bold)}</div>'
            )
        sections[key] = "".join(entries)

    skill_entries = []
    for item in resume_document.get("skills") or []:
        values = " / ".join(_nonempty(item.get("skills") or []))
        skill_entries.append(f'<p class="{"bold" if is_bold(item) else ""}"><strong>{_text(item.get("label"))}：</strong>{values}</p>')
    sections["skills"] = "".join(skill_entries)

    award_entries = []
    for item in resume_document.get("awards") or []:
        award_entries.append(
            f'<div class="entry {"bold" if is_bold(item) else ""}"><div class="entry-head"><strong>{_text(item.get("title"))}</strong><span>{_text(item.get("date"))}</span></div></div>'
        )
    sections["awards"] = "".join(award_entries)

    sections["selfEvaluation"] = f'<p>{_text(resume_document.get("selfEvaluation"))}</p>' if resume_document.get("selfEvaluation") else ""

    language_entries = []
    for item in resume_document.get("languages") or []:
        language_entries.append(
            f'<div class="compact {"bold" if is_bold(item) else ""}"><strong>{_text(item.get("name"))}</strong><span>{_text(item.get("level"))}</span></div>'
        )
    sections["languages"] = _two_column_table(language_entries)

    for key in ("courses", "strengths", "interests", "industryExpertise", "custom"):
        entries = []
        for item in resume_document.get(key) or []:
            title = item.get("title") or item.get("label") or item.get("name")
            subtitle = item.get("provider") or item.get("level") or ""
            description = item.get("description") or ""
            entries.append(
                f'<div class="entry {"bold" if is_bold(item) else ""}"><div class="entry-head"><strong>{_text(title)}</strong><span>{_text(subtitle)}</span></div>'
                f'{f"<p>{_text(description)}</p>" if description else ""}</div>'
            )
        sections[key] = (
            _two_column_table(entries, cards=key in {"courses", "strengths", "interests"})
            if key in {"courses", "strengths", "interests", "industryExpertise"}
            else "".join(entries)
        )

    raw_order = resume_document.get("sectionOrder")
    order: List[str] = []
    if isinstance(raw_order, list):
        order.extend(key for key in raw_order if key in theme["default_order"] and key not in order)
    order.extend(key for key in theme["default_order"] if key not in order)

    section_html = []
    for key in order:
        if template_id == "campus-sidebar-v1" and key in {"languages", "skills", "interests"}:
            continue
        content = sections.get(key, "")
        if not content:
            continue
        label = theme["labels"][key]
        if key == "custom":
            custom_items = resume_document.get("custom") or []
            if custom_items and custom_items[0].get("label"):
                label = _text(custom_items[0]["label"])
        section_html.append(f'<section><h2>{label}</h2>{content}</section>')

    contact_text = "&nbsp;&nbsp;&nbsp;".join(contacts)
    header_alignment = "center" if theme["header_alignment"] == WD_ALIGN_PARAGRAPH.CENTER else "left"
    is_academic = template_id == "postgraduate-interview-v1"
    body_size = 10 if is_academic else 9
    text_size = 9.3 if is_academic else 7.65
    entry_size = 9.6 if is_academic else 8.1
    meta_size = 8.4 if is_academic else 7.1
    section_size = 10.8 if is_academic else 9
    section_spacing = 7.2 if is_academic else 5.85
    entry_spacing = 3.5 if is_academic else 3.15
    heading_family = '"PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", Arial, sans-serif'

    if template_id == "campus-sidebar-v1":
        sidebar_items = "".join(f"<div class='side-item'>{item}</div>" for item in contacts)
        html = f"""
        <html><body>
          <table class="layout"><tr>
            <td class="sidebar"><div class="avatar">{name[:1] if name else ''}</div>{sidebar_items}</td>
            <td class="main"><h1>{name}</h1>{target_direction_html}{f'<p class="headline">{headline}</p>' if headline else ''}{''.join(section_html)}</td>
          </tr></table>
        </body></html>
        """
        css = f"""
          body {{ margin: 0; font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", Arial, sans-serif; color: {body_color}; font-size: 9pt; line-height: {line_spacing}; }}
          table.layout {{ width: 100%; border-collapse: collapse; }}
          td.sidebar {{ width: 32%; background: #{theme['accent']}; color: #FFFFFF; vertical-align: top; padding: 14pt 10pt; }}
          td.main {{ vertical-align: top; padding: 12pt 12pt 12pt 11pt; }}
          .avatar {{ width: 46pt; height: 46pt; margin: 0 auto 10pt; border: 1pt solid #FFFFFF; border-radius: 50%; text-align: center; line-height: 46pt; font-size: 18pt; }}
          .side-item {{ color: #FFFFFF; font-size: 7.5pt; margin: 0 0 4pt; }}
          h1 {{ color: {primary}; font-size: 16pt; margin: 0 0 4pt; }}
          .headline {{ color: {secondary}; font-size: 8pt; margin: 0 0 8pt; }}
          .target-role {{ color: {primary}; font-size: 9pt; font-weight: 700; margin: 0 0 2pt; }}
          .target-context {{ color: {secondary}; font-size: 7.5pt; margin: 0 0 4pt; }}
          section {{ margin-top: 8pt; }}
          h2 {{ color: {primary}; font-size: 9pt; margin: 0 0 3pt; padding-bottom: 1pt; border-bottom: 1px solid {section_rule}; }}
          p {{ margin: 0.7pt 0; font-size: 7.65pt; line-height: {line_spacing}; }}
          ul {{ margin: 1pt 0 0 9pt; padding: 0; }}
          li {{ margin: 0.35pt 0; font-size: 7.65pt; line-height: {line_spacing}; }}
        """
    else:
        html = f"""
    <html><body>
      <header><h1>{name}</h1>{target_direction_html}{f'<p class="headline">{headline}</p>' if headline else ''}
      {f'<p class="contacts">{contact_text}</p>' if contacts else ''}</header>
      {''.join(section_html)}
    </body></html>
    """
        css = f"""
      body {{ margin: 0; font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", "Microsoft YaHei", Arial, sans-serif; color: {body_color}; font-size: {body_size}pt; line-height: {line_spacing}; overflow-wrap: anywhere; }}
      header {{ border-bottom: {max(1, theme.get('header_rule_size', 8) / 4):g}px solid #{theme['accent']}; padding-bottom: 3.6pt; margin-bottom: 4.5pt; text-align: {header_alignment}; }}
      h1 {{ color: {primary}; font-family: {heading_family}; font-size: {20.5 if is_academic else 16.65}pt; line-height: 1.2; margin: 0 0 1.8pt; }}
      .headline {{ color: {secondary}; font-size: {9 if is_academic else 7.4}pt; margin: 0 0 1.35pt; }}
      .target-role {{ color: {primary}; font-size: {9.5 if is_academic else 8.6}pt; font-weight: 700; margin: 0 0 1.35pt; }}
      .target-context {{ color: {secondary}; font-size: {8 if is_academic else 7}pt; margin: 0 0 1.35pt; }}
      .contacts {{ color: {secondary}; font-size: {8 if is_academic else 7}pt; margin: 0; }}
      section {{ margin-top: {section_spacing}pt; }}
      h2 {{ color: {primary}; font-family: {heading_family}; font-size: {section_size}pt; line-height: 1.35; margin: 0 0 2.5pt; padding-bottom: 1.4pt; border-bottom: 1px solid {section_rule}; }}
      p {{ margin: 0.9pt 0; font-size: {text_size}pt; line-height: {line_spacing}; }}
      .entry {{ margin: {entry_spacing}pt 0 0; break-inside: avoid; }}
      .entry-head, .compact {{ display: flex; justify-content: space-between; gap: 12px; }}
      .entry-head strong {{ color: {primary}; font-size: {entry_size}pt; line-height: {line_spacing}; }}
      .entry-head span, .compact span {{ color: {secondary}; font-size: {meta_size}pt; white-space: nowrap; }}
      table.two-column {{ width: 100%; border-collapse: separate; border-spacing: 5pt 2.5pt; margin: 0 -5pt; }}
      table.two-column td {{ width: 258pt; min-width: 258pt; vertical-align: top; padding: 0 3pt; }}
      .column-box {{ width: 250pt; min-width: 250pt; }}
      .column-spacer {{ color: #FFFFFF; font-size: 7pt; line-height: 0.1pt; height: 0.1pt; white-space: nowrap; overflow: hidden; }}
      table.cards td {{ border: 1px solid #E2E8F0; padding: 3pt 4pt; }}
      table.two-column .entry, table.two-column .compact {{ margin-top: 0; }}
      ul {{ margin: 1pt 0 0 9pt; padding: 0; }}
      li {{ margin: {0.65 if is_academic else 0.35}pt 0; font-size: {text_size}pt; line-height: {line_spacing}; }}
      .bold, .bold * {{ font-weight: 700; }}
    """

    photo = photo_bytes(basics.get('photo'))
    archive = fitz.Archive()
    if photo:
        archive.add((photo, 'portrait.jpg'))
        html = html.replace('<h1>', '<img src="portrait.jpg" width="72" height="72"><h1>', 1)
    story = fitz.Story(html=html, user_css=css, archive=archive)
    output = BytesIO()
    writer = fitz.DocumentWriter(output)
    page_rect = fitz.paper_rect("a4")
    content_rect = fitz.Rect(30, 34, page_rect.width - 30, page_rect.height - 34)
    while True:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
        if not more:
            break
    writer.close()
    return output.getvalue()


def _office_binary() -> str | None:
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    return next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)


def _browser_binary() -> str | None:
    candidates = [
        os.environ.get("RESUME_PDF_BROWSER"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    return next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)


def _safe_print_payload(html: str, css: str) -> tuple[str, str]:
    lowered_html = html.lower()
    if any(marker in lowered_html for marker in ("<script", "<iframe", "<object", "<embed", "<link")):
        raise ValueError("Unsupported element in resume print payload")
    if "</style" in css.lower():
        raise ValueError("Unsupported CSS in resume print payload")

    # The snapshot is produced by our own UI. Strip resource-loading syntax so a
    # modified client cannot turn the renderer into a network/file fetcher.
    def clean_resource(match):
        value = match.group(0).split('=', 1)[1].strip().strip('\"\'')
        photo = photo_bytes(value) if match.group(0).lstrip().lower().startswith('src') else None
        if photo:
            return ' src="data:image/jpeg;base64,' + base64.b64encode(photo).decode('ascii') + '"'
        return ''

    clean_html = re.sub(
        r"\s(?:src|href)\s*=\s*(?:\"[^\"]*\"|'[^']*')",
        clean_resource,
        html,
        flags=re.IGNORECASE,
    )
    clean_css = re.sub(r"@import[^;]+;", "", css, flags=re.IGNORECASE)
    clean_css = re.sub(r"url\([^)]*\)", "none", clean_css, flags=re.IGNORECASE)
    return clean_html, clean_css


def _build_pdf_from_html(html: str, css: str, browser_binary: str) -> bytes:
    """Print the same fixed-A4 HTML shown in the editor using Chromium."""
    html, css = _safe_print_payload(html, css)
    layout = get_resume_layout()
    page = layout["page"]
    print_css = f"""
      @page {{ size: A4; margin: 0; }}
      html, body {{ margin: 0 !important; padding: 0 !important; background: #FFFFFF !important; }}
      body {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
      /* Keep the stylesheet captured from the preview authoritative. The
         preview and exported PDF must use the same template font stack. */
      [data-resume-print-root="true"],
      [data-resume-print-root="true"] * {{ font-synthesis: none !important; }}
      [data-resume-print-root="true"] {{
        box-sizing: border-box !important;
        position: static !important;
        width: {page['widthMm']}mm !important;
        min-width: {page['widthMm']}mm !important;
        min-height: {page['heightMm']}mm !important;
        height: auto !important;
        margin: 0 !important;
        box-shadow: none !important;
        overflow: visible !important;
      }}
      [data-resume-print-root="true"]::after,
      .rendered-resume-overflow-banner,
      .rendered-resume-page-sheet,
      .resume-entry-toolbar,
      .resume-entry-add-line,
      .resume-entry-draft,
      .resume-new-section-divider,
      .resume-add-row,
      .resume-row-action,
      .resume-new-bullet-input {{ display: none !important; }}
      .resume-page-break {{
        display: block !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        break-before: page !important;
        page-break-before: always !important;
      }}
      .resume-entry {{ break-inside: avoid; }}
      .resume-editable-text {{ cursor: default !important; background: transparent !important; box-shadow: none !important; }}
    """
    document_html = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
        + css
        + print_css
        + "</style></head><body>"
        + html
        + "</body></html>"
    )

    with TemporaryDirectory(prefix="resume-html-pdf-") as temp_dir:
        temp_path = Path(temp_dir)
        source_path = temp_path / "resume.html"
        output_path = temp_path / "resume.pdf"
        profile_path = temp_path / "chrome-profile"
        source_path.write_text(document_html, encoding="utf-8")
        process = subprocess.Popen(
            [
                browser_binary,
                "--headless=new",
                "--disable-gpu",
                "--disable-background-networking",
                "--disable-component-update",
                "--no-sandbox",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-pdf-header-footer",
                f"--user-data-dir={profile_path}",
                f"--print-to-pdf={output_path}",
                source_path.as_uri(),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 15
        stable_size = -1
        stable_checks = 0
        try:
            while time.monotonic() < deadline:
                if output_path.exists() and output_path.stat().st_size > 0:
                    current_size = output_path.stat().st_size
                    if current_size == stable_size:
                        stable_checks += 1
                    else:
                        stable_size = current_size
                        stable_checks = 0
                    if stable_checks >= 3:
                        break
                if process.poll() is not None:
                    break
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Browser engine did not create a PDF")
        return output_path.read_bytes()


def _pdf_pages_are_a4(content: bytes) -> bool:
    """Return whether every page uses the A4 media box.

    Chromium can silently fall back to the user's default paper size when the
    print payload contains an invalid rule or when its headless print profile
    is reused.  Validate the result before returning it so a Letter document
    cannot escape through the export endpoint.
    """
    try:
        document = fitz.open(stream=content, filetype="pdf")
        if not document.page_count:
            return False
        a4_width, a4_height = fitz.paper_size("a4")
        return all(
            abs(page.rect.width - a4_width) <= 1.5
            and abs(page.rect.height - a4_height) <= 1.5
            for page in document
        )
    except (TypeError, ValueError, RuntimeError):
        return False


def _build_pdf_from_docx(resume_document: Dict[str, Any], office_binary: str) -> bytes:
    """Convert the canonical Word layout so PDF and DOCX stay visually identical."""
    with TemporaryDirectory(prefix="resume-pdf-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "resume.docx"
        output_path = temp_path / "resume.pdf"
        profile_path = temp_path / "office-profile"
        profile_path.mkdir()
        input_path.write_bytes(build_docx(resume_document))

        environment = os.environ.copy()
        environment["HOME"] = str(temp_path)
        for fontconfig_path in (
            "/opt/homebrew/etc/fonts/fonts.conf",
            "/etc/fonts/fonts.conf",
        ):
            if Path(fontconfig_path).exists():
                environment.setdefault("FONTCONFIG_FILE", fontconfig_path)
                break

        subprocess.run(
            [
                office_binary,
                "--headless",
                f"-env:UserInstallation={profile_path.as_uri()}",
                "--convert-to",
                "pdf:writer_pdf_Export",
                "--outdir",
                str(temp_path),
                str(input_path),
            ],
            check=True,
            capture_output=True,
            timeout=45,
            env=environment,
        )
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Office engine did not create a PDF")
        return output_path.read_bytes()


def build_pdf(
    resume_document: Dict[str, Any],
    html: str | None = None,
    css: str | None = None,
) -> bytes:
    """Build a selectable-text PDF matching the canonical Word/canvas layout."""
    browser_binary = _browser_binary()
    if browser_binary and html and css:
        try:
            content = _build_pdf_from_html(html, css, browser_binary)
            if _pdf_pages_are_a4(content):
                return content
            logger.warning("Resume HTML PDF renderer returned non-A4 pages; falling back to the A4 office/story renderer")
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as error:
            logger.warning("Resume HTML PDF renderer failed; falling back to office/story renderer: {}", error)
    elif html and css:
        logger.warning("Resume HTML PDF renderer unavailable; falling back to office/story renderer")
    office_binary = _office_binary()
    if office_binary:
        try:
            return _build_pdf_from_docx(resume_document, office_binary)
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            logger.warning("Resume DOCX PDF renderer failed; falling back to Story renderer: {}", error)
    logger.warning("Resume PDF export using Story fallback renderer")
    return _build_pdf_with_story(resume_document)
