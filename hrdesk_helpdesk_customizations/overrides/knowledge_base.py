from html import escape

import frappe
from frappe import _
from frappe.utils import get_user_info_for_avatar, strip_html_tags

from hrdesk_helpdesk_customizations.knowledge_access import require_category
from hrdesk_helpdesk_customizations.ordering import sort_categories
from hrdesk_helpdesk_customizations.partner_access import (
    allowed_audiences,
    can_read_article,
)


def _allowed_categories(user=None):
    return frappe.get_all(
        "HD Article Category",
        filters={
            "custom_hrdesk_audience": ["in", sorted(allowed_audiences(user))]
        },
        pluck="name",
    )


@frappe.whitelist(allow_guest=True)
def get_categories() -> list[dict]:
    """Return only categories visible to the current audience."""
    categories = frappe.get_all(
        "HD Article Category",
        filters={"name": ["in", _allowed_categories()]},
        fields=[
            "name",
            "category_name",
            "modified",
            "custom_hrdesk_audience",
        ],
    )
    for category in categories:
        category["article_count"] = frappe.db.count(
            "HD Article",
            {"category": category.name, "status": "Published"},
        )
    visible = [category for category in categories if category.article_count > 0]
    return list(sort_categories(visible))


@frappe.whitelist(allow_guest=True)
def get_category_articles(category: str):
    require_category(category)
    articles = frappe.get_all(
        "HD Article",
        filters={"category": category, "status": "Published"},
        fields=["name", "title", "published_on", "modified", "author", "content"],
        order_by="idx asc, modified desc",
    )
    for article in articles:
        article["author"] = get_user_info_for_avatar(article.author)
        article["content"] = strip_html_tags(article.content or "")[:100]
    return articles


@frappe.whitelist(allow_guest=True)
def get_article(name: str):
    article = frappe.get_doc("HD Article", name).as_dict()
    if not can_read_article(article):
        frappe.throw(_("Access denied"), frappe.PermissionError)
    author = get_user_info_for_avatar(article.author)
    feedback = 0
    if frappe.session.user != "Guest":
        feedback = (
            frappe.db.get_value(
                "HD Article Feedback",
                {"article": name, "user": frappe.session.user},
                "feedback",
            )
            or 0
        )
    return {
        "name": article.name,
        "title": article.title,
        "content": article.content,
        "author": author,
        "creation": article.creation,
        "status": article.status,
        "published_on": article.published_on,
        "modified": article.modified,
        "category_name": frappe.db.get_value(
            "HD Article Category", article.category, "category_name"
        ),
        "category_id": article.category,
        "feedback": int(feedback),
    }


@frappe.whitelist(allow_guest=True)
def get_category_title(category: str):
    require_category(category)
    return frappe.db.get_value("HD Article Category", category, "category_name")


@frappe.whitelist(allow_guest=True)
def increment_views(article: str):
    record = frappe.db.get_value(
        "HD Article", article, ["name", "category", "status"], as_dict=True
    )
    if not record or not can_read_article(record):
        frappe.throw(_("Access denied"), frappe.PermissionError)
    frappe.db.set_value(
        "HD Article",
        article,
        "views",
        (frappe.db.get_value("HD Article", article, "views") or 0) + 1,
        update_modified=False,
    )


@frappe.whitelist(allow_guest=True)
def search(query: str):
    """Audience-filter before limiting results; never expose restricted counts."""
    query = " ".join((query or "").strip().split())[:100]
    if len(query) < 3:
        return []
    categories = _allowed_categories()
    if not categories:
        return []
    rows = frappe.get_all(
        "HD Article",
        filters={"status": "Published", "category": ["in", categories]},
        or_filters={
            "title": ["like", f"%{query}%"],
            "content": ["like", f"%{query}%"],
        },
        fields=["name", "title", "content"],
        order_by="modified desc",
        limit_page_length=5,
    )
    return [
        {
            "id": row.name,
            "name": row.name,
            "doctype": "HD Article",
            "subject": row.title,
            "headings": "",
            "description": escape(strip_html_tags(row.content or "")[:180]),
        }
        for row in rows
    ]
