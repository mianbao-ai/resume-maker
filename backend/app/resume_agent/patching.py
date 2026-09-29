"""Safe JSON-pointer patching for ResumeDocument."""
from copy import deepcopy
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

ALLOWED_ROOTS = {
    "templateId",
    "sectionOrder",
    "basics",
    "education",
    "projects",
    "experiences",
    "research",
    "awards",
    "skills",
    "selfEvaluation",
    "formatting",
    "languages",
    "courses",
    "strengths",
    "volunteering",
    "interests",
    "industryExpertise",
    "custom",
}

VALID_TEMPLATE_IDS = {
    "postgraduate-interview-v1",
    "campus-recruiting-v1",
    "campus-sidebar-v1",
    "ats-classic-v1",
    "tech-elegant-v1",
    "modern-sidebar-v1",
    "senior-dense-v1",
}

ALL_SECTION_KEYS = (
    "education",
    "research",
    "experiences",
    "projects",
    "skills",
    "awards",
    "selfEvaluation",
    "languages",
    "courses",
    "strengths",
    "volunteering",
    "interests",
    "industryExpertise",
    "custom",
)

DEFAULT_SECTION_ORDERS = {
    "postgraduate-interview-v1": [
        "education",
        "research",
        "projects",
        "experiences",
        "awards",
        "skills",
        "selfEvaluation",
        "languages",
        "courses",
        "strengths",
        "volunteering",
        "interests",
        "industryExpertise",
        "custom",
    ],
    "campus-recruiting-v1": [
        "education",
        "experiences",
        "projects",
        "research",
        "skills",
        "awards",
        "selfEvaluation",
        "languages",
        "courses",
        "strengths",
        "volunteering",
        "interests",
        "industryExpertise",
        "custom",
    ],
    "campus-sidebar-v1": [
        "education",
        "research",
        "projects",
        "experiences",
        "awards",
        "volunteering",
        "skills",
        "languages",
        "selfEvaluation",
        "courses",
        "strengths",
        "interests",
        "industryExpertise",
        "custom",
    ],
    "ats-classic-v1": [
        "education", "experiences", "projects", "research", "skills", "awards",
        "selfEvaluation", "languages", "courses", "strengths", "volunteering",
        "industryExpertise", "interests", "custom",
    ],
    "tech-elegant-v1": [
        "experiences", "projects", "skills", "education", "research", "awards",
        "selfEvaluation", "languages", "courses", "strengths", "volunteering",
        "industryExpertise", "interests", "custom",
    ],
    "modern-sidebar-v1": [
        "experiences", "projects", "education", "research", "selfEvaluation",
        "volunteering", "skills", "strengths", "languages", "awards", "courses",
        "industryExpertise", "interests", "custom",
    ],
    "senior-dense-v1": [
        "experiences", "projects", "research", "skills", "education", "awards",
        "industryExpertise", "selfEvaluation", "languages", "courses", "strengths",
        "volunteering", "interests", "custom",
    ],
}

SYSTEM_FIELDS = {"id", "userId", "sourceResumeId", "version", "createdAt", "updatedAt"}

SECTION_LIST_FIELDS = (
    "education",
    "projects",
    "experiences",
    "research",
    "awards",
    "skills",
    "languages",
    "courses",
    "strengths",
    "volunteering",
    "interests",
    "industryExpertise",
    "custom",
)


class PatchError(ValueError):
    pass


_COURSE_LABEL = re.compile(
    r"^(主修课程|核心课程|专业课程|必修课|core courses|major courses)[:：]?\s*",
    re.I,
)
_NOT_COURSE = re.compile(
    r"[。！？]|负责|完成|获得|参与|研究|设计了|实现|排名|奖学金|荣誉|论文|绩点|年级|"
    r"GPA|CET|IELTS|TOEFL|published|developed|award|三好|优秀毕业生|班干部",
    re.I,
)


def _strip_course_label(text: str) -> str:
    return _COURSE_LABEL.sub("", (text or "").strip()).strip("、，,;； ")


def _is_course_token(text: str) -> bool:
    body = re.sub(r"\s+", "", _strip_course_label(text))
    if not body or _NOT_COURSE.search(text or ""):
        return False
    if re.search(r"[\u4e00-\u9fff]", body):
        return len(body) <= 16
    words = [part for part in re.split(r"\s+", (text or "").strip()) if part]
    return len(words) <= 4 and len(body) <= 40


def format_coursework_line(courses: Iterable[Any]) -> str:
    names: List[str] = []
    seen = set()
    for item in courses:
        raw = _strip_course_label(str(item or ""))
        parts = [part.strip() for part in re.split(r"[、,，;；\n]", raw) if part.strip()]
        for part in parts:
            key = re.sub(r"\s+", "", part).lower()
            if not key or key in seen:
                continue
            seen.add(key)
            names.append(part)
    if not names:
        return ""
    return "主修课程：" + "、".join(names)


def _partition_course_highlights(highlights: List[str]) -> Tuple[List[str], List[str]]:
    if len(highlights) == 1:
        text = highlights[0]
        parts = [part.strip() for part in re.split(r"[、,，;；\n]", _strip_course_label(text)) if part.strip()]
        labeled = bool(_COURSE_LABEL.match(text.strip()))
        if parts and (labeled or len(parts) >= 3) and all(_is_course_token(part) for part in parts):
            return parts, []
    course_like = [item for item in highlights if _is_course_token(item)]
    others = [item for item in highlights if item not in course_like]
    if len(course_like) >= 2 or (course_like and not others):
        return [_strip_course_label(item) for item in course_like], others
    return [], highlights


def collapse_education_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Keep coursework as one labeled line; leave real education highlights as bullets."""
    highlights_in = item.get("highlights")
    highlights = (
        [str(value).strip() for value in highlights_in if str(value).strip()]
        if isinstance(highlights_in, list)
        else []
    )
    existing = str(item.get("coursework") or "").strip()
    course_names, others = _partition_course_highlights(highlights)
    if existing:
        item["coursework"] = existing if _COURSE_LABEL.match(existing) else format_coursework_line([existing])
        item["highlights"] = others
        return item
    if course_names:
        item["coursework"] = format_coursework_line(course_names)
        item["highlights"] = others
    return item


KEY_CONTACT_FIELDS = ("gender", "phone", "email", "location")


def is_github_profile_link(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    label = str(item.get("label") or "").strip().lower()
    url = str(item.get("url") or "").strip().lower()
    if label == "github":
        return True
    return "github.com" in url and label in {"", "主页"}


def _ensure_contact_id(item: Dict[str, Any], prefix: str) -> str:
    current = str(item.get("id") or "").strip()
    if current:
        return current
    item["id"] = f"{prefix}_{uuid4().hex[:12]}"
    return item["id"]


def default_contact_order(basics: Dict[str, Any]) -> List[str]:
    extras = [item for item in (basics.get("extras") or []) if isinstance(item, dict)]
    links = [
        item
        for item in (basics.get("links") or [])
        if isinstance(item, dict) and not is_github_profile_link(item)
    ]
    age_tokens = [
        f"extra:{_ensure_contact_id(item, 'profile')}"
        for item in extras
        if str(item.get("label") or "") == "年龄"
    ]
    other_tokens = [
        f"extra:{_ensure_contact_id(item, 'profile')}"
        for item in extras
        if str(item.get("label") or "") != "年龄"
    ]
    link_tokens = [f"link:{_ensure_contact_id(item, 'link')}" for item in links]
    leading = ["gender"] if str(basics.get("gender") or "").strip() else []
    return [*leading, *age_tokens, "phone", "email", "location", *other_tokens, *link_tokens]


def normalize_basics_contacts(basics: Dict[str, Any]) -> Dict[str, Any]:
    extras = [item for item in (basics.get("extras") or []) if isinstance(item, dict)]
    links = [
        item
        for item in (basics.get("links") or [])
        if isinstance(item, dict)
    ]
    for item in extras:
        _ensure_contact_id(item, "profile")
    for item in links:
        _ensure_contact_id(item, "link")
    basics["extras"] = extras
    basics["links"] = links
    valid = set(KEY_CONTACT_FIELDS)
    valid.update(f"extra:{item['id']}" for item in extras)
    valid.update(f"link:{item['id']}" for item in links if not is_github_profile_link(item))
    raw = basics.get("contactOrder")
    order: List[str] = []
    if isinstance(raw, list) and raw:
        for token in raw:
            if not isinstance(token, str) or token not in valid or token in order:
                continue
            if token == "gender" and not str(basics.get("gender") or "").strip():
                continue
            order.append(token)
        for token in default_contact_order(basics):
            if token not in order:
                order.append(token)
    else:
        order = default_contact_order(basics)
    basics["contactOrder"] = order
    return basics


def normalize_resume_document(document: Any) -> Dict[str, Any]:
    """Return a render-safe ResumeDocument without malformed section entries."""
    if not isinstance(document, dict):
        return {}

    normalized = deepcopy(document)
    if not isinstance(normalized.get("goal"), dict):
        normalized.pop("goal", None)
    if not isinstance(normalized.get("basics"), dict):
        normalized["basics"] = {}
    basics = normalized["basics"]
    for field in ("name", "headline", "gender", "phone", "email", "location"):
        current = basics.get(field)
        basics[field] = current.strip() if isinstance(current, str) else ""
    photo = basics.get("photo")
    if (
        not isinstance(photo, str)
        or not photo.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,"))
        or len(photo) > 2_000_000
    ):
        basics.pop("photo", None)
    extras = basics.get("extras")
    basics["extras"] = extras if isinstance(extras, list) else []
    links = basics.get("links")
    basics["links"] = links if isinstance(links, list) else []
    normalize_basics_contacts(basics)
    if not isinstance(normalized.get("formatting"), dict):
        normalized["formatting"] = {"entries": {}, "inline": {}}
    else:
        if not isinstance(normalized["formatting"].get("entries"), dict):
            normalized["formatting"]["entries"] = {}
        if not isinstance(normalized["formatting"].get("inline"), dict):
            normalized["formatting"]["inline"] = {}
        line_spacing = normalized["formatting"].get("lineSpacing")
        if line_spacing is not None:
            try:
                normalized["formatting"]["lineSpacing"] = min(1.8, max(1.15, float(line_spacing)))
            except (TypeError, ValueError):
                normalized["formatting"].pop("lineSpacing", None)

    for field in SECTION_LIST_FIELDS:
        items = normalized.get(field)
        normalized[field] = (
            [item for item in items if isinstance(item, dict)]
            if isinstance(items, list)
            else []
        )
    for item in normalized["education"]:
        collapse_education_item(item)

    default_template_id = (
        "postgraduate-interview-v1"
        if normalized.get("audience") == "graduate_examiner"
        else "tech-elegant-v1"
    )
    template_id = normalized.get("templateId")
    if template_id not in VALID_TEMPLATE_IDS:
        template_id = default_template_id
    normalized["templateId"] = template_id

    raw_order = normalized.get("sectionOrder")
    provided_order = []
    if isinstance(raw_order, list):
        for key in raw_order:
            if key in ALL_SECTION_KEYS and key not in provided_order:
                provided_order.append(key)
    default_order = DEFAULT_SECTION_ORDERS[template_id]
    normalized["sectionOrder"] = provided_order + [
        key for key in default_order if key not in provided_order
    ]

    return normalized


def _validate_presentation(document: Dict[str, Any]) -> None:
    template_id = document.get("templateId")
    if template_id is not None and template_id not in VALID_TEMPLATE_IDS:
        raise PatchError("Unknown resume template")

    section_order = document.get("sectionOrder")
    if section_order is None:
        return
    if not isinstance(section_order, list):
        raise PatchError("Section order must be a list")
    if len(section_order) != len(set(section_order)):
        raise PatchError("Section order cannot contain duplicates")
    if set(section_order) != set(ALL_SECTION_KEYS):
        raise PatchError("Section order must include every supported resume section")


def _added_value(patch: Dict[str, Any]) -> Any:
    """Support the canonical `value` field and legacy AI patches using `after`."""
    value = patch.get("value")
    if value is None:
        value = patch.get("after")
    if value is None:
        raise PatchError("Add patch must include a non-null value")
    return value


def _parts(path: str) -> List[str]:
    if not path.startswith("/"):
        raise PatchError("Patch path must be a JSON pointer")
    parts = [p.replace("~1", "/").replace("~0", "~") for p in path.strip("/").split("/") if p]
    if not parts or parts[0] not in ALLOWED_ROOTS:
        raise PatchError(f"Patch path is not allowed: {path}")
    if any(part in SYSTEM_FIELDS for part in parts):
        raise PatchError(f"Patch path cannot modify system fields: {path}")
    return parts


def get_value(document: Any, path: str) -> Any:
    current = document
    for part in _parts(path):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise PatchError(f"Cannot traverse path: {path}")
    return current


def _parent(document: Any, path: str):
    parts = _parts(path)
    current = document
    for index, part in enumerate(parts[:-1]):
        upcoming = parts[index + 1]
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            if part not in current or current[part] is None:
                current[part] = [] if upcoming.isdigit() else {}
            current = current[part]
        else:
            raise PatchError(f"Cannot traverse path: {path}")
    return current, parts[-1]


def _parse_json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _values_equivalent(current: Any, before: Any) -> bool:
    """Compare patch snapshots, tolerating JSON strings and omitted ids."""
    if before is None:
        return True
    if current == before:
        return True
    if isinstance(before, str):
        stripped = before.strip()
        if isinstance(current, str) and current.strip() == stripped:
            return True
        parsed = _parse_json_value(stripped)
        if parsed is not stripped and _values_equivalent(current, parsed):
            return True
        return False
    if isinstance(before, dict) and isinstance(current, dict):
        keys = [key for key in before if key != "id"]
        if not keys:
            return True
        return all(_values_equivalent(current.get(key), before.get(key)) for key in keys)
    if isinstance(before, list) and isinstance(current, list):
        if len(before) != len(current):
            return False
        return all(_values_equivalent(left, right) for left, right in zip(current, before))
    return False


def _can_rebase_replace(current: Any, before: Any, after: Any) -> bool:
    """Allow whole-section replace when the model summarized `before` as prose."""
    if not isinstance(before, str):
        return False
    coerced = _parse_json_value(after)
    return isinstance(current, (list, dict)) and type(current) is type(coerced)


def override_proposal_text(
    patches: List[Dict[str, Any]],
    overrides: Optional[Dict[str, Any]],
    patch_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Replace only text payloads on existing patches; keep paths and snapshots intact."""
    result = deepcopy(patches)
    selected = {patch.get("id"): patch for patch in result if patch_ids is None or patch.get("id") in patch_ids}
    if not selected:
        raise PatchError("请选择至少一项修改")
    for patch_id, value in (overrides or {}).items():
        patch = selected.get(patch_id)
        if patch is None:
            raise PatchError("我的版本包含不属于当前提案的修改")
        path = patch.get("path", "")
        path_parts = [part for part in path.split("/") if part]
        if patch.get("op") not in {"add", "replace"} or path == "/basics/photo" or (path_parts and path_parts[0] in {"templateId", "sectionOrder", "formatting"}):
            raise PatchError("此项修改不支持文本改写")
        original = _added_value(patch) if patch["op"] == "add" else patch.get("after")
        if isinstance(original, str) and not original.lstrip().startswith(("[", "{", "data:image/")):
            if not isinstance(value, str) or not value.strip():
                raise PatchError("我的版本不能为空，且必须是文本")
            value = value.strip()
        elif isinstance(original, list) and all(isinstance(item, str) for item in original):
            if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
                raise PatchError("我的版本必须是非空文本列表")
            value = [item.strip() for item in value]
        else:
            raise PatchError("结构化条目不支持整体文本替换")
        patch["value" if patch["op"] == "add" else "after"] = value
        if patch["op"] == "add" and "after" in patch:
            patch["after"] = value
    return result


def apply_patches(
    document: Dict[str, Any],
    patches: Iterable[Dict[str, Any]],
    patch_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    selected = [
        patch for patch in patches
        if patch_ids is None or patch.get("id") in set(patch_ids)
    ]
    if patch_ids is not None and len(selected) != len(set(patch_ids)):
        raise PatchError("Some requested patches do not exist on the proposal")

    next_doc = deepcopy(document)
    for patch in selected:
        op = patch.get("op")
        path = patch.get("path")
        if not path:
            raise PatchError("Patch path is required")

        if op in {"replace", "remove"}:
            before = patch.get("before")
            current = get_value(next_doc, path)
            after = patch.get("after")
            if before is not None and not _values_equivalent(current, before):
                if not (op == "replace" and _can_rebase_replace(current, before, after)):
                    raise PatchError("Patch is stale; current value does not match before value")

        parent, key = _parent(next_doc, path)
        if isinstance(parent, list):
            index = int(key)
            if op == "add":
                parent.insert(index, _added_value(patch))
            elif op == "replace":
                current = parent[index]
                parent[index] = _parse_json_value(patch.get("after")) if isinstance(current, (list, dict)) else patch.get("after")
            elif op == "remove":
                parent.pop(index)
            else:
                raise PatchError(f"Unsupported patch op: {op}")
        elif isinstance(parent, dict):
            if op == "add":
                parent[key] = _added_value(patch)
            elif op == "replace":
                current = parent.get(key)
                parent[key] = _parse_json_value(patch.get("after")) if isinstance(current, (list, dict)) else patch.get("after")
            elif op == "remove":
                parent.pop(key, None)
            else:
                raise PatchError(f"Unsupported patch op: {op}")
        else:
            raise PatchError(f"Cannot apply patch at path: {path}")

    _validate_presentation(next_doc)
    return next_doc
