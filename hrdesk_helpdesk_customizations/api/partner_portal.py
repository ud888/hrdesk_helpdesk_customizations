from html import escape
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import sanitize_html
from frappe.utils.file_manager import get_file

from hrdesk_helpdesk_customizations.partner_access import (
    get_membership,
    is_request_manager,
    require_partner,
)
from hrdesk_helpdesk_customizations.portal_constants import (
    COMMERCIAL_TEAM,
    SOC_REQUEST_KIND,
)
from hrdesk_helpdesk_customizations.portal_policy import can_access_soc

PUBLIC_FIELDS = [
    "name",
    "subject",
    "status",
    "creation",
    "modified",
    "custom_relevant_customer",
]


def _plain_html(value):
    text = str(value or "").strip()
    return sanitize_html("<p>" + escape(text).replace("\n", "<br>") + "</p>")


def _data(value):
    return frappe.parse_json(value) if isinstance(value, str) else (value or {})


def _soc_ticket(name):
    ticket = frappe.get_doc("HD Ticket", name)
    if ticket.custom_portal_request_kind != SOC_REQUEST_KIND:
        frappe.throw(_("Permintaan SOC tidak ditemukan."), frappe.DoesNotExistError)
    if not can_access_soc(ticket, require_partner()):
        frappe.throw(_("Anda tidak memiliki akses ke permintaan ini."), frappe.PermissionError)
    return ticket


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
    membership = require_partner()
    values = _data(data)
    subject = str(values.get("subject") or "").strip()
    description = str(values.get("description") or "").strip()
    if not subject or not description:
        frappe.throw(_("Subjek dan deskripsi wajib diisi."))
    customer = str(values.get("relevant_customer") or "").strip()
    if customer:
        responsible = frappe.db.get_value(
            "HD Customer", customer, "custom_hrdesk_responsible_partner"
        )
        if responsible != membership.partner:
            frappe.throw(_("Referensi pelanggan tidak berada dalam cakupan partner."))

    ticket = frappe.new_doc("HD Ticket")
    ticket.subject = subject[:140]
    ticket.description = _plain_html(description)
    ticket.via_customer_portal = 1
    ticket.custom_portal_request_kind = SOC_REQUEST_KIND
    ticket.custom_partner_organization = membership.partner
    ticket.custom_partner_submitted_by = frappe.session.user
    ticket.custom_relevant_customer = customer or None
    ticket.agent_group = COMMERCIAL_TEAM
    ticket.insert(ignore_permissions=True)

    for file in _pending_files(attachments):
        file.attached_to_doctype = "HD Ticket"
        file.attached_to_name = ticket.name
        file.save(ignore_permissions=True)
    return {"name": ticket.name, "status": ticket.status}


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
def list_soc_requests(scope="mine", limit=20):
    membership = require_partner()
    filters = {
        "custom_portal_request_kind": SOC_REQUEST_KIND,
        "custom_partner_organization": membership.partner,
    }
    if scope == "organization":
        if not is_request_manager():
            frappe.throw(_("Akses manajer permintaan diperlukan."), frappe.PermissionError)
    else:
        filters["custom_partner_submitted_by"] = frappe.session.user
    return frappe.get_all(
        "HD Ticket",
        filters=filters,
        fields=PUBLIC_FIELDS,
        order_by="modified desc",
        limit_page_length=min(max(int(limit or 20), 1), 100),
    )


@frappe.whitelist()
def get_soc_request(name):
    ticket = _soc_ticket(name)
    result = {field: ticket.get(field) for field in PUBLIC_FIELDS}
    result["description"] = ticket.description
    result["replies"] = frappe.get_all(
        "Communication",
        filters={"reference_doctype": "HD Ticket", "reference_name": ticket.name},
        fields=["name", "sender", "content", "communication_date"],
        order_by="creation asc",
    )
    result["attachments"] = _files_for("HD Ticket", ticket.name)
    for reply in result["replies"]:
        reply["attachments"] = _files_for("Communication", reply.name)
    return result


def _files_for(doctype, name):
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": doctype,
            "attached_to_name": name,
            "is_private": 1,
        },
        fields=["name", "file_name"],
    )
    for file in files:
        file["download_url"] = (
            "/api/method/hrdesk_helpdesk_customizations.api.partner_portal.download"
            f"?file_name={quote(file.name)}"
        )
    return files


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
    file = frappe.get_doc("File", file_name)
    if not file.is_private:
        frappe.throw(_("Lampiran partner harus bersifat privat."), frappe.PermissionError)
    ticket_name = None
    if file.attached_to_doctype == "HD Ticket":
        ticket_name = file.attached_to_name
    elif file.attached_to_doctype == "Communication":
        reference = frappe.db.get_value(
            "Communication",
            file.attached_to_name,
            ["reference_doctype", "reference_name"],
            as_dict=True,
        )
        if reference and reference.reference_doctype == "HD Ticket":
            ticket_name = reference.reference_name
    if not ticket_name:
        frappe.throw(_("Lampiran tidak ditemukan."), frappe.DoesNotExistError)
    _soc_ticket(ticket_name)
    filename, content = get_file(file.file_url)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.headers = {
        "Cache-Control": "private, no-store, max-age=0",
        "Pragma": "no-cache",
    }

