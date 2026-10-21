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
def get_workspace_handoff(name):
    from hrdesk_helpdesk_customizations.soc_service import get_workspace_handoff as get_handoff

    return get_handoff(name)


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
def generate_soc_documents(name):
    from hrdesk_helpdesk_customizations.soc_service import generate_document_pair

    return generate_document_pair(name)


@frappe.whitelist()
def generate_soc_pdf(name, print_format=""):
    """Backward-compatible alias; the approved workflow always generates a pair."""
    del print_format
    return generate_soc_documents(name)


@frappe.whitelist()
def list_soc_documents(name):
    from hrdesk_helpdesk_customizations.soc_service import list_documents_internal

    return list_documents_internal(name)


@frappe.whitelist()
def publish_soc_documents(name, message):
    from hrdesk_helpdesk_customizations.soc_service import publish_document_pair

    return publish_document_pair(name, message)


@frappe.whitelist()
def release_soc_document(document_name, message):
    """Backward-compatible alias that publishes the complete document pair."""
    name = frappe.db.get_value("HRD SOC Document", document_name, "soc_request")
    if not name:
        frappe.throw(_("Dokumen SOC tidak ditemukan."), frappe.DoesNotExistError)
    return publish_soc_documents(name, message)


@frappe.whitelist()
def submit_signed_documents(name, partner_soc_file, customer_sac_file, message=""):
    from hrdesk_helpdesk_customizations.soc_service import submit_signed_document_pair

    return submit_signed_document_pair(
        name, partner_soc_file, customer_sac_file, message
    )


@frappe.whitelist()
def reject_signed_documents(name, reason):
    from hrdesk_helpdesk_customizations.soc_service import reject_signed_documents as reject

    return reject(name, reason)


@frappe.whitelist()
def approve_workspace_creation(name, acceptance_confirmed=0):
    from hrdesk_helpdesk_customizations.soc_service import approve_workspace_creation as approve

    return approve(name, acceptance_confirmed)


@frappe.whitelist()
def reopen_for_amendment(name, reason):
    from hrdesk_helpdesk_customizations.soc_service import reopen_for_amendment as reopen

    return reopen(name, reason)


@frappe.whitelist()
def request_cancellation(name, reason):
    from hrdesk_helpdesk_customizations.soc_service import request_cancellation as request

    return request(name, reason)


@frappe.whitelist()
def approve_cancellation(name):
    from hrdesk_helpdesk_customizations.soc_service import approve_cancellation as approve

    return approve(name)


@frappe.whitelist()
def record_provisioning_failure(name, error_summary):
    from hrdesk_helpdesk_customizations.soc_service import record_provisioning_failure as record

    return record(name, error_summary)


@frappe.whitelist()
def complete_workspace(
    name, workspace_reference, access_username, access_secret, instructions=""
):
    from hrdesk_helpdesk_customizations.soc_service import complete_workspace as complete

    return complete(
        name, workspace_reference, access_username, access_secret, instructions
    )


@frappe.whitelist()
def emergency_override_status(name, status, reason):
    from hrdesk_helpdesk_customizations.soc_service import emergency_override_status as override

    return override(name, status, reason)

