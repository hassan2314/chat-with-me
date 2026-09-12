RULES = [
    (
        ["why hire", "why you", "why should", "strengths", "fit", "hire you"],
        ["about", "experience", "project"],
    ),
    (
        ["tell me about yourself", "who are you", "about you", "who is hassan"],
        ["about", "experience"],
    ),
    (
        [
            "nestjs",
            "next.js",
            "nextjs",
            "postgres",
            "postgresql",
            "prisma",
            "sequelize",
            "docker",
            "document ai",
        ],
        ["experience", "skill", "project"],
    ),
    (
        ["degree", "university", "numl", "education", "fyp", "coursework"],
        ["education", "project"],
    ),
    (
        [
            "available",
            "notice",
            "relocate",
            "contact",
            "email",
            "resume",
            "phone",
            "linkedin",
        ],
        ["about"],
    ),
    (
        ["project", "built", "portfolio", "github", "live demo"],
        ["project", "experience"],
    ),
]


def classify(question: str) -> list[str] | None:
    q = question.lower()
    for keywords, cats in RULES:
        if any(k in q for k in keywords):
            return cats
    return None
