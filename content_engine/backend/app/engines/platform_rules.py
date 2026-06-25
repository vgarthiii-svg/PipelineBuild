"""Platform & content-type best-practices rules engine.

Rules are data, not code — so they can be edited in Settings and stored in the
DB. PLATFORM_RULE_SEED defines the system defaults that seed the platform_rules
table on first run. Each entry encodes the required structure, best practices,
and constraints used by the prompt builder and the scorer.
"""
from __future__ import annotations

# The 13 supported content types (maps to the product spec).
CONTENT_TYPES = [
    ("linkedin", "LinkedIn post"),
    ("email", "Email marketing campaign"),
    ("website", "Website copy"),
    ("landing", "Landing page"),
    ("blog", "Blog post"),
    ("newsletter", "Newsletter content"),
    ("social", "Social media post"),
    ("ad", "Short-form ad copy"),
    ("thought_leadership", "Long-form thought leadership"),
    ("sales", "Sales enablement copy"),
    ("press", "Press-release-style announcement"),
    ("brief", "SEO content brief"),
    ("repurpose", "Repurposed content"),
]

PLATFORMS = [
    "LinkedIn", "Email", "Website", "Blog", "X/Twitter", "Instagram",
    "Facebook", "TikTok", "YouTube", "Newsletter", "Press", "Generic",
]


PLATFORM_RULE_SEED: list[dict] = [
    {
        "platform": "LinkedIn", "content_type": "linkedin", "label": "LinkedIn Post",
        "structure": ["Hook (line 1)", "Context", "Insight/Story", "Takeaways", "Closing thought / CTA"],
        "best_practices": [
            "Open with a strong, scroll-stopping hook in the first line",
            "Make professional relevance clear quickly",
            "Use short paragraphs and white space",
            "Native, human tone — not corporate-speak",
            "Limited, purposeful emoji use",
            "No spammy or excessive hashtags (1-3 relevant max)",
            "End with a strong closing thought or a question that invites comments",
            "Design for comments and shares, not just likes",
        ],
        "constraints": {"max_chars": 3000, "ideal_chars": 1300, "hashtags": "1-3", "emoji": "sparing", "links": "in comments preferred"},
    },
    {
        "platform": "Email", "content_type": "email", "label": "Email Marketing Campaign",
        "structure": ["Subject lines (3 options)", "Preview text", "Opening", "Body (scannable)", "Primary CTA", "Compliance footer placeholder"],
        "best_practices": [
            "Provide 3 subject line options and preview text",
            "Lead with the offer/value; keep it scannable",
            "Exactly one primary CTA",
            "Mobile-friendly structure; short paragraphs",
            "Include a compliance/unsubscribe footer placeholder",
            "Offer A/B test variants for subject and CTA",
        ],
        "constraints": {"subject_max_chars": 60, "preview_max_chars": 90, "primary_ctas": 1, "ab_variants": True},
    },
    {
        "platform": "Website", "content_type": "website", "label": "Website Copy",
        "structure": ["Above-the-fold headline", "Subheadline", "Problem statement", "Value proposition", "Benefits", "Proof points", "CTA section", "SEO metadata"],
        "best_practices": [
            "Clear above-the-fold headline + subheadline",
            "State the problem, then the value proposition",
            "Benefit-led, not feature-led",
            "Include proof points / social proof",
            "Conversion-focused CTA section",
            "Provide SEO title and meta description",
        ],
        "constraints": {"seo_title_max": 60, "meta_desc_max": 155},
    },
    {
        "platform": "Website", "content_type": "landing", "label": "Landing Page",
        "structure": ["Hero (headline+sub+CTA)", "Pain point", "Solution", "Benefits", "Social proof", "Features", "Objection handling", "CTA", "Form copy", "Thank-you copy"],
        "best_practices": [
            "Single conversion goal; remove navigation distractions",
            "Hero states outcome + primary CTA above the fold",
            "Name the pain, present the solution, list benefits",
            "Include social proof and objection handling",
            "Concise form copy and a thank-you page message",
        ],
        "constraints": {"primary_ctas": 1, "message_match": True},
    },
    {
        "platform": "Blog", "content_type": "blog", "label": "Blog Post (SEO)",
        "structure": ["SEO title", "Meta description", "H1", "Intro", "H2/H3 body", "Internal links", "External sources", "FAQ", "CTA"],
        "best_practices": [
            "Provide SEO title, meta description, and target keywords",
            "Match search intent; answer the main question early",
            "Use H1/H2/H3 hierarchy and an outline",
            "Suggest internal link anchors and credible external sources",
            "Include an FAQ section and a closing CTA",
        ],
        "constraints": {"seo_title_max": 60, "meta_desc_max": 155, "min_words": 800},
    },
    {
        "platform": "Newsletter", "content_type": "newsletter", "label": "Newsletter",
        "structure": ["Subject", "Intro/hook", "Main section", "Secondary items", "One CTA", "Sign-off"],
        "best_practices": [
            "Personable, consistent voice", "One clear primary CTA",
            "Skimmable sections with subheads", "Value before promotion",
        ],
        "constraints": {"subject_max_chars": 60, "primary_ctas": 1},
    },
    {
        "platform": "X/Twitter", "content_type": "social", "label": "Social Post / Thread",
        "structure": ["Hook post", "Supporting posts", "Payoff", "CTA"],
        "best_practices": [
            "Hook in the first line/post", "One idea per post",
            "Concrete > abstract", "Thread payoff at the end", "Native formatting",
        ],
        "constraints": {"post_max_chars": 280, "hashtags": "0-2"},
    },
    {
        "platform": "Generic", "content_type": "ad", "label": "Short-form Ad Copy",
        "structure": ["Headline", "Primary text", "Description", "CTA button"],
        "best_practices": [
            "Lead with the strongest benefit or hook", "Match audience and funnel stage",
            "Single CTA", "Provide multiple variants for testing", "Honor ad-policy compliance",
        ],
        "constraints": {"headline_max": 40, "primary_text_max": 125, "variants": 3},
    },
    {
        "platform": "LinkedIn", "content_type": "thought_leadership", "label": "Thought Leadership",
        "structure": ["Provocative thesis", "Context/stakes", "Argument with evidence", "Counterpoint", "Implications", "Call to reflection/action"],
        "best_practices": [
            "Lead with a clear, defensible point of view", "Support with evidence and experience",
            "Acknowledge nuance/counterpoints", "Avoid jargon; write for credibility",
        ],
        "constraints": {"ideal_words": 900},
    },
    {
        "platform": "Generic", "content_type": "sales", "label": "Sales Enablement Copy",
        "structure": ["Opening", "Pain/trigger", "Value & differentiation", "Proof", "Objection handling", "Clear ask"],
        "best_practices": [
            "Personalize to the buyer and trigger", "Lead with relevance, not the pitch",
            "Quantify value; include proof", "One clear ask/next step",
        ],
        "constraints": {"primary_ctas": 1},
    },
    {
        "platform": "Press", "content_type": "press", "label": "Press-style Announcement",
        "structure": ["Headline", "Dateline", "Lead paragraph (who/what/when/where/why)", "Body", "Quote", "Boilerplate", "Contact"],
        "best_practices": [
            "Inverted pyramid: most important first", "Factual, AP-style, no hype",
            "Include a credible quote and boilerplate", "Attribute all claims",
        ],
        "constraints": {"ap_style": True},
    },
    {
        "platform": "Generic", "content_type": "brief", "label": "SEO Content Brief",
        "structure": ["Target keyword & intent", "SERP/competitor notes", "Suggested title & meta", "Outline (H2/H3)", "Key questions to answer", "Internal/external links", "Word count target"],
        "best_practices": [
            "Tie everything to search intent", "Provide a concrete outline a writer can follow",
            "List entities, questions, and links to include", "Set a word-count target",
        ],
        "constraints": {"deliverable": "brief"},
    },
]


def find_rule(platform: str, content_type: str) -> dict | None:
    """Lookup helper used when the DB is not the source (tests, fallbacks)."""
    for r in PLATFORM_RULE_SEED:
        if r["content_type"] == content_type:
            if not platform or r["platform"].lower() == platform.lower():
                return r
    for r in PLATFORM_RULE_SEED:
        if r["content_type"] == content_type:
            return r
    return None
