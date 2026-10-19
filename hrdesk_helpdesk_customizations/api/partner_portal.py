from html import escape
import frappe
from frappe import _
from frappe.utils import sanitize_html

from hrdesk_helpdesk_customizations.partner_access import (
    get_membership,
    is_request_manager,
    require_partner,
)


def _plain_html(value):
    text = str(value or "").strip()
    return sanitize_html("<p>" + escape(text).replace("\n", "<br>") + "</p>")


def _soc_ticket(name):
    from hrdesk_helpdesk_customizations.soc_service import ticket_for_reference

    return ticket_for_reference(name)


def _pending_files(attachments):
    names = frappe.parse_json(attachments) if isinstance(attachments, str) else attachments
    result = []
    for name in names or []:
        file = frappe.get_doc("File", name)
        if (
            file.owner != frappe.session.user
            or file.attached_to_doctype
            or not file.is_private
        ):
            frappe.throw(_("Lampiran tidak valid."), frappe.PermissionError)
        result.append(file)
    return result


@frappe.whitelist()
def portal_context():
    membership = require_partner()
    return {
        "user": frappe.session.user,
        "partner": frappe.db.get_value(
            "HD Customer", membership.partner, "customer_name"
        ) or membership.partner,
        "request_manager": bool(is_request_manager()),
        "l1_support_access": bool(membership.l1_support_access),
    }


@frappe.whitelist()
def create_soc_request(data, attachments=None):
    from hrdesk_helpdesk_customizations.soc_service import create_request

    return create_request(data, attachments)


@frappe.whitelist()
def customer_options(search=""):
    membership = require_partner()
    filters = {"custom_hrdesk_responsible_partner": membership.partner}
    if search:
        filters["customer_name"] = ["like", f"%{str(search)[:80]}%"]
    return frappe.get_all(
        "HD Customer",
        filters=filters,
        fields=["name", "customer_name"],
        order_by="customer_name asc",
        limit_page_length=50,
    )


@frappe.whitelist()
def list_soc_requests(scope="mine", search="", status="", limit=50):
    from hrdesk_helpdesk_customizations.soc_service import list_requests

    return list_requests(scope, search, status, limit)


@frappe.whitelist()
def get_soc_request(name):
    from hrdesk_helpdesk_customizations.soc_service import get_request

    return get_request(name)


@frappe.whitelist()
def reply(name, message, attachments=None):
    ticket = _soc_ticket(name)
    if not str(message or "").strip():
        frappe.throw(_("Balasan tidak boleh kosong."))
    files = _pending_files(attachments)
    ticket.create_communication_via_contact(
        _plain_html(message),
        attachments=[{"name": file.name} for file in files],
    )
    return {"name": ticket.name, "replied": True}


@frappe.whitelist()
def download(file_name):
    from hrdesk_helpdesk_customizations.soc_service import download_file

    return download_file(file_name)


@frappe.whitelist()
def soc_form_options():
    from hrdesk_helpdesk_customizations.soc_service import form_options

    return form_options()


@frappe.whitelist()
def update_soc_request(name, data, attachments=None):
    from hrdesk_helpdesk_customizations.soc_service import update_request

    return update_request(name, data, attachments)


@frappe.whitelist()
def set_soc_status(name, status, revision_reason=""):
    from hrdesk_helpdesk_customizations.soc_service import set_status

    return set_status(name, status, revision_reason)


@frappe.whitelist()
def soc_print_formats():
    from hrdesk_helpdesk_customizations.soc_service import print_formats

    return print_formats()


@frappe.whitelist()
def generate_soc_pdf(name, print_format="SOC Request Form - Standard"):
    from hrdesk_helpdesk_customizations.soc_service import generate_pdf

    return generate_pdf(name, print_format)


@frappe.whitelist()
def list_soc_documents(name):
    from hrdesk_helpdesk_customizations.soc_service import list_documents_internal

    return list_documents_internal(name)


@frappe.whitelist()
def release_soc_document(document_name, message):
    from hrdesk_helpdesk_customizations.soc_service import release_document

    return release_document(document_name, message)

