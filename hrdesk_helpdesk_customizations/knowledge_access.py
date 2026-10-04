import frappe
from frappe import _

from hrdesk_helpdesk_customizations.partner_access import (
    allowed_audiences,
    can_read_article,
    can_read_category,
    is_editor,
)


def article_query(user=None, doctype=None):
    del doctype
    user = user or frappe.session.user
    audiences = sorted(allowed_audiences(user))
    values = ", ".join(frappe.db.escape(value) for value in audiences)
    category_filter = (
        "`tabHD Article`.category IN (SELECT name FROM `tabHD Article Category` "
        f"WHERE COALESCE(custom_hrdesk_audience, 'Public') IN ({values}))"
    )
    if is_editor(user):
        return category_filter
    return f"(`tabHD Article`.status = 'Published' AND {category_filter})"


def category_query(user=None, doctype=None):
    del doctype
    audiences = sorted(allowed_audiences(user))
    values = ", ".join(frappe.db.escape(value) for value in audiences)
    return (
        "COALESCE(`tabHD Article Category`.custom_hrdesk_audience, 'Public') "
        f"IN ({values})"
    )


def article_has_permission(doc, ptype=None, user=None, debug=False):
    del debug
    if ptype in {"read", "select", "print", "email", "export"}:
        return can_read_article(doc, user)
    if ptype in {"create", "write", "delete", "share"}:
        return is_editor(user)
    return True


def category_has_permission(doc, ptype=None, user=None, debug=False):
    del debug
    if ptype in {"read", "select", "print", "email", "export"}:
        return can_read_category(doc.name, user)
    if ptype in {"create", "write", "delete", "share"}:
        return is_editor(user)
    return True


def validate_category(doc, method=None):
    del method
    if doc.is_new() or doc.has_value_changed("custom_hrdesk_audience"):
        if not is_editor():
            frappe.throw(
                _("Only an authorized knowledge editor may change article audience."),
                frappe.PermissionError,
            )


def validate_article(doc, method=None):
    del method
    if not is_editor() and (
        doc.is_new()
        or doc.has_value_changed("category")
        or doc.has_value_changed("status")
        or doc.has_value_changed("content")
        or doc.has_value_changed("title")
    ):
        frappe.throw(
            _("Only an authorized knowledge editor may change articles."),
            frappe.PermissionError,
        )


def _article_audience(article_name):
    category = frappe.db.get_value("HD Article", article_name, "category")
    if not category:
        return "Public"
    return (
        frappe.db.get_value(
            "HD Article Category", category, "custom_hrdesk_audience"
        )
        or "Public"
    )


def secure_article_file(doc, method=None):
    """Move restricted article attachments into Frappe's private file store.

    File saves its content during ``before_insert``, before application-level
    validate hooks run.  Converting after insert/update lets the File controller
    perform its normal public-to-private move without replacing upload handling.
    """
    del method
    if getattr(doc.flags, "hrdesk_securing_article_file", False):
        return
    if doc.attached_to_doctype != "HD Article" or not doc.attached_to_name:
        return
    if _article_audience(doc.attached_to_name) == "Public" or doc.is_private:
        return

    doc.flags.hrdesk_securing_article_file = True
    try:
        doc.is_private = 1
        doc.save(ignore_permissions=True)
    finally:
        doc.flags.hrdesk_securing_article_file = False


def secure_article_attachments(doc, method=None):
    del method
    if _article_audience(doc.name) == "Public":
        return
    for file_name in frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "HD Article",
            "attached_to_name": doc.name,
            "is_private": 0,
        },
        pluck="name",
    ):
        secure_article_file(frappe.get_doc("File", file_name))


def secure_category_attachments(doc, method=None):
    del method
    audience = doc.get("custom_hrdesk_audience") or "Public"
    if audience == "Public":
        return
    for article_name in frappe.get_all(
        "HD Article", filters={"category": doc.name}, pluck="name"
    ):
        for file_name in frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": "HD Article",
                "attached_to_name": article_name,
                "is_private": 0,
            },
            pluck="name",
        ):
            secure_article_file(frappe.get_doc("File", file_name))


def file_has_permission(doc, ptype=None, user=None, debug=False):
    del debug
    if doc.attached_to_doctype != "HD Article" or not doc.attached_to_name:
        return True
    article = frappe.db.get_value(
        "HD Article",
        doc.attached_to_name,
        ["name", "category", "status"],
        as_dict=True,
    )
    if not article:
        return False
    if ptype in {"read", "select"}:
        return can_read_article(article, user)
    return is_editor(user)


def require_category(category, user=None):
    if not can_read_category(category, user):
        frappe.throw(_("Anda tidak memiliki akses ke kategori ini."), frappe.PermissionError)
