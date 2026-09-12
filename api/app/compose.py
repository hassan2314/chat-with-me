def _join(items: list | None, sep: str = " ") -> str:
    return sep.join(str(x) for x in (items or []) if x)


def about_text(row: dict) -> str:
    extra = row.get("extra") or {}
    extra_bits = [f"{k}: {v}" for k, v in extra.items() if v]
    return "\n".join(
        [
            "Category: about",
            f"Title: {row['title']}",
            row.get("body") or "",
            *extra_bits,
        ]
    )


def education_text(row: dict) -> str:
    years = " – ".join(
        str(x) for x in (row.get("start_year"), row.get("end_year")) if x
    )
    return "\n".join(
        [
            "Category: education",
            f"Degree: {row['degree']}",
            f"Institution: {row['institution']}",
            f"Dates: {years}",
            row.get("description") or "",
            "Coursework: " + _join(row.get("coursework"), ", "),
            "Achievements: " + _join(row.get("achievements"), "; "),
        ]
    )


def experience_text(row: dict, projects: list[dict] | None = None) -> str:
    parts = [
        "Category: experience",
        f"Role: {row['title']} at {row['company']}, {row.get('location') or ''}",
        f"Dates: {row.get('start_label') or ''} – {row.get('end_label') or ''}",
        "Highlights: " + _join(row.get("highlights")),
    ]
    for project in projects or []:
        name = project.get("name")
        bullets = _join(project.get("bullets"))
        if name:
            url = f" ({project['url']})" if project.get("url") else ""
            parts.append(f"Project: {name}{url}. {bullets}")
        elif bullets:
            parts.append(f"Work: {bullets}")
    parts.append("Technologies: " + _join(row.get("technologies"), ", "))
    return "\n".join(parts)


def skill_text(row: dict) -> str:
    level = row.get("level")
    level_line = f"Proficiency: {level}" if level is not None else ""
    return "\n".join(
        [
            "Category: skill",
            f"Group: {row['group_name']}",
            f"Skill: {row['name']}",
            level_line,
        ]
    )


def project_text(row: dict) -> str:
    return "\n".join(
        [
            "Category: project",
            f"Title: {row['title']}",
            f"Subtitle: {row.get('subtitle') or ''}",
            row.get("description") or "",
            "Technologies: " + _join(row.get("technologies"), ", "),
            f"GitHub: {row.get('github_url') or ''}",
            f"Live: {row.get('live_url') or ''}",
        ]
    )
