"""Professional DOCX export for ResumeDocument."""
from io import BytesIO
from typing import Any, Dict, List, Optional

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement

from .layout import get_resume_layout
from .mapping import contact_line_parts
from .patching import DEFAULT_SECTION_ORDERS
from .photo import photo_bytes


RESUME_LAYOUT = get_resume_layout()
PAGE = RESUME_LAYOUT["page"]
TYPE = RESUME_LAYOUT["type"]
SPACE = RESUME_LAYOUT["space"]


def _iter_docx_paragraphs(container):
    """Yield paragraphs from the document, including paragraphs inside tables."""
    yield from container.paragraphs
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _iter_docx_paragraphs(cell)


def _apply_resume_line_spacing(document, resume_document: Dict[str, Any]) -> None:
    """Apply the user's global line-spacing preference to every exported paragraph."""
    formatting = resume_document.get("formatting") or {}
    raw_spacing = formatting.get("lineSpacing") if isinstance(formatting, dict) else None
    try:
        spacing = float(raw_spacing)
    except (TypeError, ValueError):
        spacing = float(TYPE["bodyLineHeight"])
    spacing = min(1.8, max(1.15, spacing))
    for paragraph in _iter_docx_paragraphs(document):
        paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        paragraph.paragraph_format.line_spacing = spacing


TEMPLATE_THEMES = {
    "postgraduate-interview-v1": {
        "font": "PingFang SC",
        "primary": (0x17, 0x3B, 0x59),
        "secondary": (0x53, 0x68, 0x79),
        "body": (0x2F, 0x3E, 0x49),
        "accent": "4F7C82",
        "section_rule": "AFC2CC",
        "header_alignment": WD_ALIGN_PARAGRAPH.CENTER,
        "header_rule_size": 8,
        "labels": {
            "education": "教育背景",
            "research": "科研经历",
            "experiences": "实践经历",
            "projects": "项目经历",
            "skills": "专业技能",
            "awards": "荣誉奖项",
            "selfEvaluation": "个人陈述",
            "languages": "语言能力",
            "courses": "培训与课程",
            "strengths": "个人优势",
            "volunteering": "志愿经历",
            "interests": "兴趣爱好",
            "industryExpertise": "专业领域",
            "custom": "自定义模块",
        },
    },
    "campus-recruiting-v1": {
        "font": "PingFang SC",
        "primary": (0x14, 0x3B, 0x6B),
        "secondary": (0x4A, 0x55, 0x68),
        "body": (0x37, 0x41, 0x51),
        "accent": "2563EB",
        "section_rule": "BFDBFE",
        "header_alignment": WD_ALIGN_PARAGRAPH.LEFT,
        "labels": {
            "education": "教育背景",
            "research": "科研经历",
            "experiences": "实习经历",
            "projects": "项目经历",
            "skills": "专业技能",
            "awards": "荣誉奖项",
            "selfEvaluation": "个人评价",
            "languages": "语言能力",
            "courses": "培训与课程",
            "strengths": "个人优势",
            "volunteering": "志愿经历",
            "interests": "兴趣爱好",
            "industryExpertise": "专业领域",
            "custom": "自定义模块",
        },
    },
    "campus-sidebar-v1": {
        "font": "PingFang SC",
        "primary": (0x1E, 0x4B, 0x8C),
        "secondary": (0xE8, 0xEE, 0xF7),
        "body": (0x1F, 0x2A, 0x44),
        "accent": "1E4B8C",
        "section_rule": "C5D4EA",
        "header_alignment": WD_ALIGN_PARAGRAPH.LEFT,
        "sidebar_fill": "1E4B8C",
        "sidebar_text": (0xFF, 0xFF, 0xFF),
        "labels": {
            "education": "学业情况",
            "research": "科研经历",
            "experiences": "实习经历",
            "projects": "专业实践",
            "skills": "专业技能",
            "awards": "荣誉证书",
            "selfEvaluation": "个人评价",
            "languages": "语言能力",
            "courses": "培训与课程",
            "strengths": "个人优势",
            "volunteering": "工作实践",
            "interests": "兴趣爱好",
            "industryExpertise": "专业领域",
            "custom": "自定义模块",
        },
    },
    "ats-classic-v1": {
        "font": "PingFang SC",
        "primary": (0x11, 0x18, 0x27),
        "secondary": (0x4B, 0x55, 0x63),
        "body": (0x1F, 0x29, 0x37),
        "accent": "111827",
        "section_rule": "374151",
        "header_alignment": WD_ALIGN_PARAGRAPH.CENTER,
        "header_rule_size": 4,
        "labels": {
            "education": "教育背景", "research": "科研经历", "experiences": "工作经历",
            "projects": "项目经历", "skills": "专业技能", "awards": "荣誉奖项",
            "selfEvaluation": "个人总结", "languages": "语言能力", "courses": "培训与课程",
            "strengths": "个人优势", "volunteering": "志愿经历", "interests": "兴趣爱好",
            "industryExpertise": "专业领域", "custom": "自定义模块",
        },
        "default_order": [
            "education", "experiences", "projects", "research", "skills", "awards",
            "selfEvaluation", "languages", "courses", "strengths", "volunteering",
            "industryExpertise", "interests", "custom",
        ],
    },
    "tech-elegant-v1": {
        "font": "PingFang SC",
        "primary": (0x12, 0x2A, 0x46),
        "secondary": (0x52, 0x60, 0x72),
        "body": (0x2B, 0x36, 0x45),
        "accent": "2878B5",
        "section_rule": "B9D9EC",
        "header_alignment": WD_ALIGN_PARAGRAPH.LEFT,
        "header_rule_size": 10,
        "labels": {
            "education": "教育背景", "research": "科研经历", "experiences": "工作经历",
            "projects": "项目经历", "skills": "技术能力", "awards": "荣誉奖项",
            "selfEvaluation": "个人简介", "languages": "语言能力", "courses": "培训与课程",
            "strengths": "个人优势", "volunteering": "志愿经历", "interests": "兴趣爱好",
            "industryExpertise": "专业领域", "custom": "自定义模块",
        },
        "default_order": [
            "experiences", "projects", "skills", "education", "research", "awards",
            "selfEvaluation", "languages", "courses", "strengths", "volunteering",
            "industryExpertise", "interests", "custom",
        ],
    },
    "modern-sidebar-v1": {
        "font": "PingFang SC",
        "primary": (0x18, 0x2E, 0x46),
        "secondary": (0x47, 0x5F, 0x6E),
        "body": (0x28, 0x36, 0x42),
        "accent": "1D9A8A",
        "section_rule": "A7D8D0",
        "header_alignment": WD_ALIGN_PARAGRAPH.LEFT,
        "header_rule_size": 12,
        "labels": {
            "education": "教育背景", "research": "研究经历", "experiences": "工作经历",
            "projects": "代表项目", "skills": "核心技能", "awards": "荣誉奖项",
            "selfEvaluation": "关于我", "languages": "语言能力", "courses": "培训与课程",
            "strengths": "个人优势", "volunteering": "社会经历", "interests": "兴趣爱好",
            "industryExpertise": "行业专长", "custom": "自定义模块",
        },
        "default_order": [
            "experiences", "projects", "education", "research", "selfEvaluation",
            "volunteering", "skills", "strengths", "languages", "awards", "courses",
            "industryExpertise", "interests", "custom",
        ],
    },
    "senior-dense-v1": {
        "font": "PingFang SC",
        "primary": (0x18, 0x25, 0x33),
        "secondary": (0x4B, 0x55, 0x63),
        "body": (0x26, 0x31, 0x3D),
        "accent": "2E5F7A",
        "section_rule": "7895A5",
        "header_alignment": WD_ALIGN_PARAGRAPH.LEFT,
        "header_rule_size": 6,
        "labels": {
            "education": "教育背景", "research": "研究与技术影响", "experiences": "职业经历",
            "projects": "关键项目", "skills": "技术栈", "awards": "荣誉与认证",
            "selfEvaluation": "职业概述", "languages": "语言能力", "courses": "专业课程",
            "strengths": "领导力与优势", "volunteering": "社会经历", "interests": "兴趣爱好",
            "industryExpertise": "领域专长", "custom": "补充经历",
        },
        "default_order": [
            "experiences", "projects", "research", "skills", "education", "awards",
            "industryExpertise", "selfEvaluation", "languages", "courses", "strengths",
            "volunteering", "interests", "custom",
        ],
    },
}


for _template_id, _theme in TEMPLATE_THEMES.items():
    _theme["default_order"] = list(DEFAULT_SECTION_ORDERS[_template_id])


def _entry_has_content(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    for key, value in item.items():
        if key == "id" or value is None:
            continue
        if isinstance(value, list):
            if any(str(part).strip() for part in value):
                return True
        elif str(value).strip():
            return True
    return False


def _set_cell_border(cell, **kwargs):
    """Set cell border. Usage: _set_cell_border(cell, top={"sz": 4, "color": "000000"})"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("start", "top", "end", "bottom", "insideH", "insideV"):
        if edge in kwargs:
            element = OxmlElement(f"w:{edge}")
            element.set(qn("w:val"), "single")
            element.set(qn("w:sz"), str(kwargs[edge].get("sz", 4)))
            element.set(qn("w:color"), kwargs[edge].get("color", "000000"))
            element.set(qn("w:space"), "0")
            tcBorders.append(element)
    tcPr.append(tcBorders)


def _set_cell_margins(cell, top: int = 55, start: int = 65, bottom: int = 55, end: int = 65):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _remove_table_borders(table):
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "start", "bottom", "end", "insideH", "insideV"):
        node = OxmlElement(f"w:{edge}")
        node.set(qn("w:val"), "nil")
        borders.append(node)


def _set_cell_shading(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), fill)
    tc_pr.append(shading)


def _set_cell_width(cell, dxa: int):
    tc_pr = cell._tc.get_or_add_tcPr()
    width = tc_pr.find(qn("w:tcW"))
    if width is None:
        width = OxmlElement("w:tcW")
        tc_pr.append(width)
    width.set(qn("w:w"), str(dxa))
    width.set(qn("w:type"), "dxa")


def _add_cell_text(
    cell,
    text: str,
    *,
    size: float,
    color: RGBColor,
    bold: bool = False,
    space_before: float = 0,
    space_after: float = 2,
):
    if not str(text or "").strip():
        return
    paragraph = cell.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(space_before)
    paragraph.paragraph_format.space_after = Pt(space_after)
    run = paragraph.add_run(str(text).strip())
    run.bold = bold
    run.font.size = Pt(size)
    run.font.color.rgb = color


def _add_paragraph_bottom_border(p, color: str, size: int = 8):
    """Add the canvas header rule without creating an extra blank paragraph."""
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "3")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_section_heading(doc, text: str, theme: Dict[str, Any]):
    """Add a styled section heading with bottom border."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(SPACE["sectionBeforePt"])
    p.paragraph_format.space_after = Pt(SPACE["sectionAfterPt"])
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(TYPE["sectionPt"])
    run.font.color.rgb = RGBColor(*theme["primary"])
    # Bottom border for section heading
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), theme["section_rule"])
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_formatted_runs(
    paragraph,
    text: str,
    bold_ranges: Optional[List[Dict[str, Any]]] = None,
    *,
    default_bold: bool = False,
    size: float,
    color: RGBColor,
):
    """Add text runs while preserving character-level bold ranges."""
    text = str(text or "")
    ranges = []
    for mark in bold_ranges or []:
        if not isinstance(mark, dict) or mark.get("bold") is not True:
            continue
        try:
            start = max(0, min(int(mark.get("start", 0)), len(text)))
            end = max(0, min(int(mark.get("end", 0)), len(text)))
        except (TypeError, ValueError):
            continue
        if end > start:
            ranges.append((start, end))
    boundaries = {0, len(text)}
    for start, end in ranges:
        boundaries.update((start, end))
    points = sorted(boundaries)
    for index, start in enumerate(points[:-1]):
        end = points[index + 1]
        run = paragraph.add_run(text[start:end])
        run.bold = default_bold or any(left <= start and right >= end for left, right in ranges)
        run.font.size = Pt(size)
        run.font.color.rgb = color


def _add_entry_header(
    doc,
    title: str,
    subtitle: str = "",
    right_text: str = "",
    theme: Optional[Dict[str, Any]] = None,
    bold_all: bool = False,
    title_ranges: Optional[List[Dict[str, Any]]] = None,
    subtitle_ranges: Optional[List[Dict[str, Any]]] = None,
    right_ranges: Optional[List[Dict[str, Any]]] = None,
):
    """Add an entry with bold title, optional subtitle, and right-aligned date."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(SPACE["entryBeforePt"])
    p.paragraph_format.space_after = Pt(SPACE["paragraphPt"])
    p.paragraph_format.keep_together = True
    p.paragraph_format.tab_stops.add_tab_stop(Cm(18.9), WD_TAB_ALIGNMENT.RIGHT)
    theme = theme or TEMPLATE_THEMES["tech-elegant-v1"]
    _add_formatted_runs(
        p, title, title_ranges, default_bold=True,
        size=TYPE["entryTitlePt"], color=RGBColor(*theme["primary"]),
    )
    if subtitle:
        p.add_run("  ")
        _add_formatted_runs(
            p, subtitle, subtitle_ranges, default_bold=bold_all,
            size=TYPE["bodyTextPt"], color=RGBColor(*theme["secondary"]),
        )
    if right_text:
        p.add_run("\t")
        _add_formatted_runs(
            p, right_text, right_ranges, default_bold=bold_all,
            size=TYPE["metaPt"], color=RGBColor(0x71, 0x80, 0x96),
        )


def _add_bullet(
    doc,
    text: str,
    theme: Optional[Dict[str, Any]] = None,
    bold: bool = False,
    bold_ranges: Optional[List[Dict[str, Any]]] = None,
):
    """Add a bullet point with proper formatting."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.32)
    p.paragraph_format.first_line_indent = Cm(-0.24)
    p.paragraph_format.space_before = Pt(SPACE["bulletPt"])
    p.paragraph_format.space_after = Pt(SPACE["bulletPt"])
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(TYPE["bodyTextPt"] * TYPE["contentLineHeight"])
    theme = theme or TEMPLATE_THEMES["tech-elegant-v1"]
    bullet_run = p.add_run("•  ")
    bullet_run.bold = bold
    bullet_run.font.size = Pt(TYPE["bodyTextPt"])
    bullet_run.font.color.rgb = RGBColor(*theme["body"])
    _add_formatted_runs(
        p, text, bold_ranges, default_bold=bold,
        size=TYPE["bodyTextPt"], color=RGBColor(*theme["body"]),
    )


def _add_body_line(
    doc,
    text: str,
    theme: Optional[Dict[str, Any]] = None,
    bold: bool = False,
    bold_ranges: Optional[List[Dict[str, Any]]] = None,
):
    """Add a non-bullet resume line such as coursework."""
    if not str(text or "").strip():
        return
    theme = theme or TEMPLATE_THEMES["campus-recruiting-v1"]
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0)
    p.paragraph_format.space_before = Pt(SPACE["paragraphPt"])
    p.paragraph_format.space_after = Pt(SPACE["paragraphPt"])
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.line_spacing = Pt(TYPE["bodyTextPt"] * TYPE["contentLineHeight"])
    _add_formatted_runs(
        p, text, bold_ranges, default_bold=bold,
        size=TYPE["bodyTextPt"], color=RGBColor(*theme["body"]),
    )


def _add_tech_stack(
    doc,
    tech: List[str],
    theme: Optional[Dict[str, Any]] = None,
    bold: bool = False,
    bold_ranges: Optional[List[Dict[str, Any]]] = None,
):
    """Add a tech stack line."""
    if not tech:
        return
    theme = theme or TEMPLATE_THEMES["tech-elegant-v1"]
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0)
    p.paragraph_format.space_before = Pt(SPACE["paragraphPt"])
    p.paragraph_format.space_after = Pt(SPACE["paragraphPt"])
    run = p.add_run("技术栈：")
    run.bold = bold
    run.font.size = Pt(TYPE["compactPt"])
    run.font.color.rgb = RGBColor(0x6B, 0x72, 0x80)
    _add_formatted_runs(
        p, " / ".join(map(str, tech)), bold_ranges, default_bold=bold,
        size=TYPE["compactPt"], color=RGBColor(*theme["body"]),
    )


SIDEBAR_SECTION_KEYS = ("languages", "skills", "interests")


def _build_sidebar_docx(resume_document: Dict[str, Any], theme: Dict[str, Any]) -> bytes:
    document = Document()
    for section in document.sections:
        section.page_width = Cm(PAGE["widthMm"] / 10)
        section.page_height = Cm(PAGE["heightMm"] / 10)
        section.top_margin = Cm(0)
        section.bottom_margin = Cm(0)
        section.left_margin = Cm(0)
        section.right_margin = Cm(0)

    style = document.styles["Normal"]
    style.font.name = theme["font"]
    style.font.size = Pt(TYPE["bodyTextPt"])
    style._element.rPr.rFonts.set(qn("w:eastAsia"), theme["font"])

    basics = resume_document.get("basics") or {}
    name = basics.get("name") or resume_document.get("title") or "简历"
    goal = resume_document.get("goal")
    if isinstance(goal, dict):
        target_role = str(goal.get("target_role") or "").strip()
        target_context = " · ".join(
            str(value).strip()
            for value in (goal.get("target_organization"), goal.get("research_direction"))
            if str(value or "").strip()
        )
    else:
        target_role = str(resume_document.get("targetRole") or "").strip()
        target_context = ""
    sidebar_color = RGBColor(*theme.get("sidebar_text", (255, 255, 255)))
    page_dxa = int(PAGE["widthMm"] * 1440 / 25.4)
    sidebar_width = int(page_dxa * 0.32)
    main_width = page_dxa - sidebar_width

    table = document.add_table(rows=1, cols=2)
    table.autofit = False
    _remove_table_borders(table)
    sidebar_cell, main_cell = table.rows[0].cells
    _set_cell_width(sidebar_cell, sidebar_width)
    _set_cell_width(main_cell, main_width)
    _set_cell_shading(sidebar_cell, theme.get("sidebar_fill", "1E4B8C"))
    _set_cell_margins(sidebar_cell, 220, 160, 220, 140)
    _set_cell_margins(main_cell, 200, 160, 200, 180)

    sidebar_cell.text = ""
    main_cell.text = ""

    photo = photo_bytes(basics.get('photo'))
    if photo:
        sidebar_cell.add_paragraph().add_run().add_picture(BytesIO(photo), width=Cm(3), height=Cm(3))
    else:
        avatar = str(name or "简")[:1]
        _add_cell_text(sidebar_cell, avatar, size=18, color=sidebar_color, bold=True, space_after=8)
    for text, _path in contact_line_parts(basics, include_github=True):
        _add_cell_text(sidebar_cell, text, size=8, color=sidebar_color, space_after=2)

    def write_sidebar_section(key: str) -> None:
        label = theme["labels"][key]
        if key == "languages":
            items = [item for item in (resume_document.get("languages") or []) if _entry_has_content(item)]
            if not items:
                return
            _add_cell_text(sidebar_cell, label, size=10, color=sidebar_color, bold=True, space_before=10, space_after=4)
            for item in items:
                line = "  ".join(part for part in (item.get("name"), item.get("level")) if str(part or "").strip())
                _add_cell_text(sidebar_cell, line, size=8, color=sidebar_color)
            return
        if key == "skills":
            groups = [item for item in (resume_document.get("skills") or []) if _entry_has_content(item)]
            if not groups:
                return
            _add_cell_text(sidebar_cell, label, size=10, color=sidebar_color, bold=True, space_before=10, space_after=4)
            for group in groups:
                values = " / ".join(str(skill).strip() for skill in (group.get("skills") or []) if str(skill).strip())
                heading = str(group.get("label") or "").strip()
                _add_cell_text(sidebar_cell, f"{heading}：{values}" if heading else values, size=8, color=sidebar_color)
            return
        items = [item for item in (resume_document.get("interests") or []) if _entry_has_content(item)]
        if not items:
            return
        _add_cell_text(sidebar_cell, label, size=10, color=sidebar_color, bold=True, space_before=10, space_after=4)
        tags = "  ".join(str(item.get("title") or item.get("name") or "").strip() for item in items if _entry_has_content(item))
        _add_cell_text(sidebar_cell, tags, size=8, color=sidebar_color)

    for key in SIDEBAR_SECTION_KEYS:
        write_sidebar_section(key)

    _add_cell_text(main_cell, name, size=TYPE["namePt"], color=RGBColor(*theme["primary"]), bold=True, space_after=6)
    if target_role:
        _add_cell_text(main_cell, target_role, size=TYPE["headlinePt"], color=RGBColor(*theme["secondary"]), bold=True, space_after=2)
    if target_context:
        _add_cell_text(main_cell, target_context, size=TYPE["contactPt"], color=RGBColor(*theme["secondary"]), space_after=4)
    headline = str(basics.get("headline") or "").strip()
    if headline:
        _add_cell_text(main_cell, headline, size=TYPE["headlinePt"], color=RGBColor(*theme["secondary"]), space_after=8)

    def write_main_heading(text: str) -> None:
        _add_cell_text(main_cell, text, size=TYPE["sectionPt"], color=RGBColor(*theme["primary"]), bold=True, space_before=8, space_after=3)

    def write_main_entry(title: str, right: str = "", body_lines: Optional[List[str]] = None) -> None:
        head = title if not right else f"{title}    {right}"
        _add_cell_text(main_cell, head, size=TYPE["entryTitlePt"], color=RGBColor(*theme["primary"]), bold=True, space_before=3, space_after=1)
        for line in body_lines or []:
            if str(line).strip():
                _add_cell_text(main_cell, str(line).strip(), size=TYPE["bodyTextPt"], color=RGBColor(*theme["body"]), space_after=1)

    allowed = set(theme["default_order"])
    raw_order = resume_document.get("sectionOrder")
    section_order: List[str] = []
    if isinstance(raw_order, list):
        for key in raw_order:
            if key in allowed and key not in section_order and key not in SIDEBAR_SECTION_KEYS:
                section_order.append(key)
    section_order.extend(
        key for key in theme["default_order"]
        if key not in section_order and key not in SIDEBAR_SECTION_KEYS
    )

    for key in section_order:
        if key == "education":
            items = [item for item in (resume_document.get("education") or []) if _entry_has_content(item)]
            if not items:
                continue
            write_main_heading(theme["labels"]["education"])
            for item in items:
                dates = " - ".join(part for part in (item.get("startDate"), item.get("endDate")) if str(part or "").strip())
                write_main_entry(str(item.get("school") or ""), dates, [
                    " · ".join(part for part in (item.get("major"), item.get("degree"), item.get("gpa")) if str(part or "").strip()),
                    item.get("coursework"),
                    *[str(highlight) for highlight in (item.get("highlights") or [])],
                ])
            continue
        if key in {"experiences", "projects", "research"}:
            items = [item for item in (resume_document.get(key) or []) if _entry_has_content(item)]
            if not items:
                continue
            write_main_heading(theme["labels"][key])
            for item in items:
                heading = item.get("company") or item.get("name") or item.get("title") or "经历"
                dates = " - ".join(part for part in (item.get("startDate"), item.get("endDate")) if str(part or "").strip())
                lines = [item.get("role")]
                if item.get("techStack"):
                    lines.append("技术栈：" + " / ".join(str(part) for part in item.get("techStack") if str(part).strip()))
                lines.extend(str(bullet) for bullet in (item.get("bullets") or []))
                write_main_entry(str(heading), dates, lines)
            continue
        if key == "awards":
            items = [item for item in (resume_document.get("awards") or []) if _entry_has_content(item)]
            if not items:
                continue
            write_main_heading(theme["labels"]["awards"])
            for item in items:
                title = " · ".join(part for part in (item.get("title"), item.get("issuer")) if str(part or "").strip())
                write_main_entry(title, str(item.get("date") or ""))
            continue
        if key == "selfEvaluation":
            value = str(resume_document.get("selfEvaluation") or "").strip()
            if not value:
                continue
            write_main_heading(theme["labels"]["selfEvaluation"])
            _add_cell_text(main_cell, value, size=TYPE["bodyTextPt"], color=RGBColor(*theme["body"]))
            continue
        items = [item for item in (resume_document.get(key) or []) if isinstance(item, dict) and _entry_has_content(item)]
        if not items:
            continue
        write_main_heading(theme["labels"].get(key, key))
        for item in items:
            title = item.get("title") or item.get("name") or item.get("organization") or item.get("label") or ""
            dates = " - ".join(part for part in (item.get("startDate"), item.get("endDate")) if str(part or "").strip())
            lines = [item.get("role"), item.get("description"), *[str(bullet) for bullet in (item.get("bullets") or [])]]
            write_main_entry(str(title), dates, lines)

    _apply_resume_line_spacing(document, resume_document)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_docx(resume_document: Dict[str, Any]) -> bytes:
    """Build a professionally formatted DOCX resume."""
    doc = Document()

    template_id = resume_document.get("templateId")
    if template_id not in TEMPLATE_THEMES:
        template_id = (
            "postgraduate-interview-v1"
            if resume_document.get("audience") == "graduate_examiner"
            else "tech-elegant-v1"
        )
    theme = TEMPLATE_THEMES[template_id]
    if template_id == "campus-sidebar-v1":
        return _build_sidebar_docx(resume_document, theme)

    formatting = resume_document.get("formatting") or {}
    entry_formatting = formatting.get("entries") if isinstance(formatting, dict) else {}
    inline_formatting = formatting.get("inline") if isinstance(formatting, dict) else {}
    if not isinstance(entry_formatting, dict):
        entry_formatting = {}
    if not isinstance(inline_formatting, dict):
        inline_formatting = {}

    def inline_marks(path: str) -> List[Dict[str, Any]]:
        value = inline_formatting.get(path)
        return value if isinstance(value, list) else []

    def composed_text(parts, separator: str = ""):
        text_parts: List[str] = []
        ranges: List[Dict[str, Any]] = []
        offset = 0
        for raw_text, path in parts:
            value = str(raw_text or "").strip()
            if not value:
                continue
            if text_parts:
                text_parts.append(separator)
                offset += len(separator)
            text_parts.append(value)
            for mark in inline_marks(path):
                if not isinstance(mark, dict):
                    continue
                try:
                    start = int(mark.get("start", 0))
                    end = int(mark.get("end", 0))
                except (TypeError, ValueError):
                    continue
                ranges.append({
                    "start": offset + start,
                    "end": offset + end,
                    "bold": mark.get("bold") is True,
                })
            offset += len(value)
        return "".join(text_parts), ranges

    def entry_is_bold(item: Dict[str, Any]) -> bool:
        item_format = entry_formatting.get(item.get("id"), {})
        return isinstance(item_format, dict) and item_format.get("bold") is True

    # Match the A4 canvas geometry: 5% horizontal and 4% vertical padding.
    for section in doc.sections:
        section.page_width = Cm(PAGE["widthMm"] / 10)
        section.page_height = Cm(PAGE["heightMm"] / 10)
        section.top_margin = Cm(PAGE["marginTopMm"] / 10)
        section.bottom_margin = Cm(PAGE["marginBottomMm"] / 10)
        section.left_margin = Cm(PAGE["marginLeftMm"] / 10)
        section.right_margin = Cm(PAGE["marginRightMm"] / 10)

    # Set default font
    style = doc.styles["Normal"]
    style.font.name = theme["font"]
    style.font.size = Pt(TYPE["bodyPt"])
    style._element.rPr.rFonts.set(qn("w:eastAsia"), theme["font"])
    style.paragraph_format.space_before = Pt(0)
    style.paragraph_format.space_after = Pt(0)

    basics = resume_document.get("basics") or {}
    name = basics.get("name") or resume_document.get("title") or "简历"
    goal = resume_document.get("goal")
    if isinstance(goal, dict):
        target_role = str(goal.get("target_role") or "").strip()
        target_context = " · ".join(
            str(value).strip()
            for value in (goal.get("target_organization"), goal.get("research_direction"))
            if str(value or "").strip()
        )
    else:
        target_role = str(resume_document.get("targetRole") or "").strip()
        target_context = ""

    photo = photo_bytes(basics.get('photo'))
    if photo:
        photo_p = doc.add_paragraph()
        photo_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        photo_p.paragraph_format.keep_with_next = True
        photo_p.add_run().add_picture(BytesIO(photo), width=Cm(2.6), height=Cm(2.6))

    # ===== Header: Name =====
    name_p = doc.add_paragraph()
    name_p.alignment = theme["header_alignment"]
    name_p.paragraph_format.space_after = Pt(SPACE["nameAfterPt"])
    # Inline formatting is initialized below; the name remains bold by template.
    name_run = name_p.add_run(name)
    name_run.bold = True
    name_run.font.size = Pt(TYPE["namePt"])
    name_run.font.color.rgb = RGBColor(*theme["primary"])

    # ===== Header: Target direction =====
    target_role_p = None
    target_context_p = None
    if target_role:
        target_role_p = doc.add_paragraph()
        target_role_p.alignment = theme["header_alignment"]
        target_role_p.paragraph_format.space_after = Pt(SPACE["headlineAfterPt"])
        target_role_run = target_role_p.add_run(target_role)
        target_role_run.bold = True
        target_role_run.font.size = Pt(TYPE["headlinePt"])
        target_role_run.font.color.rgb = RGBColor(*theme["secondary"])
    if target_context:
        target_context_p = doc.add_paragraph()
        target_context_p.alignment = theme["header_alignment"]
        target_context_p.paragraph_format.space_after = Pt(SPACE["headlineAfterPt"])
        target_context_run = target_context_p.add_run(target_context)
        target_context_run.font.size = Pt(TYPE["contactPt"])
        target_context_run.font.color.rgb = RGBColor(*theme["secondary"])

    # ===== Header: Contact info =====
    headline = basics.get("headline", "")
    if headline:
        headline_p = doc.add_paragraph()
        headline_p.alignment = theme["header_alignment"]
        headline_p.paragraph_format.space_after = Pt(SPACE["headlineAfterPt"])
        _add_formatted_runs(
            headline_p, headline, inline_marks("/basics/headline"),
            size=TYPE["headlinePt"], color=RGBColor(*theme["secondary"]),
        )

    contact_parts = contact_line_parts(basics)
    header_rule_p = name_p
    if contact_parts:
        contact_p = doc.add_paragraph()
        contact_p.alignment = theme["header_alignment"]
        contact_p.paragraph_format.space_after = Pt(SPACE["headerAfterPt"])
        contact_text, contact_ranges = composed_text(contact_parts, "   ")
        _add_formatted_runs(
            contact_p, contact_text, contact_ranges,
            size=TYPE["contactPt"], color=RGBColor(*theme["secondary"]),
        )
        header_rule_p = contact_p
    elif headline:
        headline_p.paragraph_format.space_after = Pt(SPACE["headerAfterPt"])
        header_rule_p = headline_p
    elif target_context_p:
        target_context_p.paragraph_format.space_after = Pt(SPACE["headerAfterPt"])
        header_rule_p = target_context_p
    elif target_role_p:
        target_role_p.paragraph_format.space_after = Pt(SPACE["headerAfterPt"])
        header_rule_p = target_role_p

    _add_paragraph_bottom_border(
        header_rule_p,
        theme["accent"],
        size=theme.get("header_rule_size", 4 if template_id == "postgraduate-interview-v1" else 8),
    )

    allowed_sections = set(theme["default_order"])
    raw_order = resume_document.get("sectionOrder")
    section_order: List[str] = []
    if isinstance(raw_order, list):
        for key in raw_order:
            if key in allowed_sections and key not in section_order:
                section_order.append(key)
    section_order.extend(key for key in theme["default_order"] if key not in section_order)

    def render_education() -> None:
        items = [(index, item) for index, item in enumerate(resume_document.get("education") or []) if _entry_has_content(item)]
        if not items:
            return
        _add_section_heading(doc, theme["labels"]["education"], theme)
        for item_index, item in items:
            bold = entry_is_bold(item)
            school = item.get("school", "")
            detail, detail_ranges = composed_text([
                (item.get("major", ""), f"/education/{item_index}/major"),
                (item.get("degree", ""), f"/education/{item_index}/degree"),
            ], " · ")
            dates, date_ranges = composed_text([
                (item.get("startDate", ""), f"/education/{item_index}/startDate"),
                (item.get("endDate", ""), f"/education/{item_index}/endDate"),
            ], " - ")
            _add_entry_header(
                doc, school, detail, dates, theme, bold_all=bold,
                title_ranges=inline_marks(f"/education/{item_index}/school"),
                subtitle_ranges=detail_ranges,
                right_ranges=date_ranges,
            )
            gpa = item.get("gpa", "")
            if gpa:
                gpa_ranges = [
                    {**mark, "start": int(mark.get("start", 0)) + 5, "end": int(mark.get("end", 0)) + 5}
                    for mark in inline_marks(f"/education/{item_index}/gpa") if isinstance(mark, dict)
                ]
                _add_bullet(doc, f"GPA: {gpa}", theme, bold=bold, bold_ranges=gpa_ranges)
            coursework = str(item.get("coursework") or "").strip()
            if coursework:
                _add_body_line(
                    doc, coursework, theme, bold=bold,
                    bold_ranges=inline_marks(f"/education/{item_index}/coursework"),
                )
            for highlight_index, highlight in enumerate(item.get("highlights", []) or []):
                if str(highlight).strip():
                    _add_bullet(
                        doc, str(highlight), theme, bold=bold,
                        bold_ranges=inline_marks(f"/education/{item_index}/highlights/{highlight_index}"),
                    )

    def render_entries(key: str) -> None:
        items = [(index, item) for index, item in enumerate(resume_document.get(key) or []) if _entry_has_content(item)]
        if not items:
            return
        _add_section_heading(doc, theme["labels"][key], theme)
        for item_index, item in items:
            bold = entry_is_bold(item)
            heading_field = "company" if item.get("company") else "name" if item.get("name") else "title"
            heading = item.get(heading_field) or "经历"
            role = item.get("role", "")
            dates, date_ranges = composed_text([
                (item.get("startDate", ""), f"/{key}/{item_index}/startDate"),
                (item.get("endDate", ""), f"/{key}/{item_index}/endDate"),
            ], " - ")
            _add_entry_header(
                doc, heading, role, dates, theme, bold_all=bold,
                title_ranges=inline_marks(f"/{key}/{item_index}/{heading_field}"),
                subtitle_ranges=inline_marks(f"/{key}/{item_index}/role"),
                right_ranges=date_ranges,
            )
            tech_text, tech_ranges = composed_text([
                (technology, f"/{key}/{item_index}/techStack/{technology_index}")
                for technology_index, technology in enumerate(item.get("techStack") or [])
            ], " / ")
            _add_tech_stack(doc, [tech_text] if tech_text else [], theme, bold=bold, bold_ranges=tech_ranges)
            for bullet_index, bullet in enumerate(item.get("bullets", []) or []):
                if str(bullet).strip():
                    _add_bullet(
                        doc, str(bullet), theme, bold=bold,
                        bold_ranges=inline_marks(f"/{key}/{item_index}/bullets/{bullet_index}"),
                    )

    def render_skills() -> None:
        skills = [
            (index, group) for index, group in enumerate(resume_document.get("skills") or [])
            if any(str(value).strip() for value in group.get("skills") or [])
        ]
        if not skills:
            return
        _add_section_heading(doc, theme["labels"]["skills"], theme)
        for group_index, group in skills:
            bold = entry_is_bold(group)
            label = group.get("label") or "技能"
            values, value_ranges = composed_text([
                (skill, f"/skills/{group_index}/skills/{skill_index}")
                for skill_index, skill in enumerate(group.get("skills") or [])
            ], " / ")
            if not values:
                continue
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(SPACE["paragraphPt"])
            p.paragraph_format.space_after = Pt(SPACE["paragraphPt"])
            _add_formatted_runs(
                p, f"{label}：", inline_marks(f"/skills/{group_index}/label"),
                default_bold=True, size=TYPE["bodyTextPt"], color=RGBColor(*theme["primary"]),
            )
            _add_formatted_runs(
                p, values, value_ranges, default_bold=bold,
                size=TYPE["bodyTextPt"], color=RGBColor(*theme["body"]),
            )

    def render_awards() -> None:
        awards = [(index, item) for index, item in enumerate(resume_document.get("awards") or []) if _entry_has_content(item)]
        if not awards:
            return
        _add_section_heading(doc, theme["labels"]["awards"], theme)
        for award_index, award in awards:
            bold = entry_is_bold(award)
            title, title_ranges = composed_text([
                (award.get("title", ""), f"/awards/{award_index}/title"),
                (award.get("issuer", ""), f"/awards/{award_index}/issuer"),
            ], " · ")
            _add_entry_header(
                doc,
                title,
                "",
                award.get("date", ""),
                theme,
                bold_all=bold,
                title_ranges=title_ranges,
                right_ranges=inline_marks(f"/awards/{award_index}/date"),
            )

    def render_self_evaluation() -> None:
        value = resume_document.get("selfEvaluation")
        if not value:
            return
        _add_section_heading(doc, theme["labels"]["selfEvaluation"], theme)
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(SPACE["paragraphPt"])
        p.paragraph_format.space_after = Pt(SPACE["paragraphPt"])
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        p.paragraph_format.line_spacing = Pt(TYPE["bodyTextPt"] * TYPE["contentLineHeight"])
        _add_formatted_runs(
            p, str(value), inline_marks("/selfEvaluation"),
            size=TYPE["bodyTextPt"], color=RGBColor(*theme["body"]),
        )

    def render_two_column_items(
        key: str,
        items: List[Dict[str, Any]],
        title_getter,
        subtitle_getter,
        description_getter=lambda item: "",
        cards: bool = False,
    ) -> None:
        items = [(index, item) for index, item in enumerate(items) if _entry_has_content(item)]
        if not items:
            return
        _add_section_heading(doc, theme["labels"][key], theme)
        table = doc.add_table(rows=(len(items) + 1) // 2, cols=2)
        table.autofit = False
        _remove_table_borders(table)
        for table_index, (item_index, item) in enumerate(items):
            cell = table.cell(table_index // 2, table_index % 2)
            cell.width = Cm(9.35)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
            _set_cell_margins(cell, 70 if cards else 30, 85, 70 if cards else 30, 85)
            if cards:
                _set_cell_border(
                    cell,
                    top={"sz": 3, "color": "E2E8F0"},
                    start={"sz": 3, "color": "E2E8F0"},
                    bottom={"sz": 3, "color": "E2E8F0"},
                    end={"sz": 3, "color": "E2E8F0"},
                )
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0.4)
            title_field = "name" if key == "languages" else "label" if key == "industryExpertise" else "title"
            _add_formatted_runs(
                paragraph, str(title_getter(item) or ""), inline_marks(f"/{key}/{item_index}/{title_field}"),
                default_bold=True, size=TYPE["bodyTextPt"], color=RGBColor(*theme["primary"]),
            )
            subtitle = subtitle_getter(item)
            if subtitle:
                paragraph.add_run("  ")
                subtitle_field = "level" if key in {"languages", "industryExpertise"} else "provider"
                _add_formatted_runs(
                    paragraph, str(subtitle), inline_marks(f"/{key}/{item_index}/{subtitle_field}"),
                    size=TYPE["metaPt"], color=RGBColor(*theme["secondary"]),
                )
            description = description_getter(item)
            if description:
                description_p = cell.add_paragraph()
                description_p.paragraph_format.space_after = Pt(0)
                _add_formatted_runs(
                    description_p, str(description), inline_marks(f"/{key}/{item_index}/description"),
                    size=TYPE["compactPt"], color=RGBColor(*theme["body"]),
                )

        if len(items) % 2:
            empty_cell = table.cell(len(items) // 2, 1)
            _set_cell_margins(empty_cell, 0, 0, 0, 0)

    def render_languages() -> None:
        items = resume_document.get("languages") or []
        render_two_column_items(
            "languages",
            items,
            lambda item: item.get("name") or "语言",
            lambda item: item.get("level") or "",
        )

    def render_descriptive_section(key: str) -> None:
        raw_items = resume_document.get(key) or []
        items = [item for item in raw_items if _entry_has_content(item)]
        if not items:
            return
        if key in {"courses", "strengths", "interests", "industryExpertise"}:
            render_two_column_items(
                key,
                items,
                lambda item: item.get("title") or item.get("name") or item.get("label") or theme["labels"][key],
                lambda item: item.get("provider") or item.get("level") or "",
                lambda item: item.get("description") or "",
                cards=key in {"courses", "strengths", "interests"},
            )
            return
        section_label = theme["labels"][key]
        if key == "custom" and items[0].get("label"):
            section_label = items[0]["label"]
        _add_section_heading(doc, section_label, theme)
        for item_index, item in enumerate(raw_items):
            if not _entry_has_content(item):
                continue
            bold = entry_is_bold(item)
            title_field = next((field for field in ("title", "name", "label", "organization") if item.get(field)), "title")
            title = item.get(title_field) or section_label
            subtitle_field = next((field for field in ("provider", "role", "level") if item.get(field)), "role")
            subtitle = item.get(subtitle_field) or ""
            dates, date_ranges = composed_text([
                (item.get("startDate", ""), f"/{key}/{item_index}/startDate"),
                (item.get("endDate", ""), f"/{key}/{item_index}/endDate"),
            ], " - ")
            _add_entry_header(
                doc, title, subtitle, dates, theme, bold_all=bold,
                title_ranges=inline_marks(f"/{key}/{item_index}/{title_field}"),
                subtitle_ranges=inline_marks(f"/{key}/{item_index}/{subtitle_field}"),
                right_ranges=date_ranges,
            )
            description = item.get("description")
            if description:
                _add_bullet(
                    doc, str(description), theme, bold=bold,
                    bold_ranges=inline_marks(f"/{key}/{item_index}/description"),
                )
            for bullet_index, bullet in enumerate(item.get("bullets", []) or []):
                if str(bullet).strip():
                    _add_bullet(
                        doc, str(bullet), theme, bold=bold,
                        bold_ranges=inline_marks(f"/{key}/{item_index}/bullets/{bullet_index}"),
                    )

    renderers = {
        "education": render_education,
        "experiences": lambda: render_entries("experiences"),
        "projects": lambda: render_entries("projects"),
        "research": lambda: render_entries("research"),
        "skills": render_skills,
        "awards": render_awards,
        "selfEvaluation": render_self_evaluation,
        "languages": render_languages,
        "courses": lambda: render_descriptive_section("courses"),
        "strengths": lambda: render_descriptive_section("strengths"),
        "volunteering": lambda: render_descriptive_section("volunteering"),
        "interests": lambda: render_descriptive_section("interests"),
        "industryExpertise": lambda: render_descriptive_section("industryExpertise"),
        "custom": lambda: render_descriptive_section("custom"),
    }
    for section_key in section_order:
        renderers[section_key]()

    # Write to bytes
    _apply_resume_line_spacing(doc, resume_document)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
