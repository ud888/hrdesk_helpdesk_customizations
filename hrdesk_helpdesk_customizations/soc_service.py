from html import escape
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import now_datetime, sanitize_html, today
from frappe.utils.file_manager import get_file, save_file

from hrdesk_helpdesk_customizations.partner_access import (
    get_membership,
    is_internal,
    is_request_manager,
    require_partner,
    roles_for,
)
from hrdesk_helpdesk_customizations.portal_constants import (
    COMMERCIAL_ROLE,
    COMMERCIAL_TEAM,
    PORTAL_ADMIN_ROLE,
    SOC_REQUEST_KIND,
    SOC_TICKET_TYPE,
)
from hrdesk_helpdesk_customizations.portal_policy import can_access_soc
from hrdesk_helpdesk_customizations.soc_access import (
    can_access_soc_document,
    can_access_soc_request,
)
from hrdesk_helpdesk_customizations.soc_rules import SOC_STATUSES, SOC_TYPES


REQUEST_FIELDS = (
    "name",
    "soc_type",
    "soc_status",
    "submission_date",
    "submitted_by",
    "partner",
    "ticket",
    "customer",
    "customer_company_name",
    "customer_address",
    "customer_pic_name",
    "customer_pic_position",
    "customer_pic_email",
    "customer_pic_phone",
    "super_admin_email",
    "domain_workspace",
    "reseller_billing_contact_email",
    "reseller_billing_contact_phone",
    "package_type",
    "subscription_start_date",
    "subscription_end_date",
    "subscription_period",
    "payment_term",
    "go_live_target_date",
    "estimated_employee_count",
    "number_of_admin_users",
    "number_of_payroll_groups",
    "implementation_included",
    "training_included",
    "revision_reason",
    "creation",
    "modified",
)

EDITABLE_FIELDS = {
    "soc_type",
    "customer",
    "customer_company_name",
    "customer_address",
    "customer_pic_name",
    "customer_pic_position",
    "customer_pic_email",
    "customer_pic_phone",
    "super_admin_email",
    "domain_workspace",
    "reseller_billing_contact_email",
    "reseller_billing_contact_phone",
    "package_type",
    "subscription_start_date",
    "subscription_end_date",
    "payment_term",
    "go_live_target_date",
    "estimated_employee_count",
    "number_of_admin_users",
    "number_of_payroll_groups",
    "implementation_included",
    "training_included",
}


def data(value):
    return frappe.parse_json(value) if isinstance(value, str) else (value or {})


def plain_html(value):
    text = str(value or "").strip()
    return sanitize_html("<p>" + escape(text).replace("\n", "<br>") + "</p>")


def pending_files(attachments):
    names = frappe.parse_json(attachments) if isinstance(attachments, str) else attachments
    result = []
    for name in names or []:
        file = frappe.get_doc("File", name)
        if file.owner != frappe.session.user or file.attached_to_doctype or not file.is_private:
            frappe.throw(_("Lampiran tidak valid."), frappe.PermissionError)
        result.append(file)
    return result


def require_commercial():
    roles = roles_for()
    if frappe.session.user != "Administrator" and not roles.intersection(
        {"System Manager", PORTAL_ADMIN_ROLE, COMMERCIAL_ROLE}
    ):
        frappe.throw(_("Akses HR Desk Commercial diperlukan."), frappe.PermissionError)


def _authorized_customer(customer, partner):
    if not customer:
        return
    responsible = frappe.db.get_value(
        "HD Customer", customer, "custom_hrdesk_responsible_partner"
    )
    if responsible != partner:
        frappe.throw(_("Customer tidak berada dalam cakupan partner."), frappe.PermissionError)


def _apply_values(doc, values):
    for fieldname in EDITABLE_FIELDS:
        if fieldname in values:
            doc.set(fieldname, values.get(fieldname))
    if "add_ons" in values:
        doc.set("add_ons", [])
        for item in values.get("add_ons") or []:
            row = data(item)
            if row.get("add_on"):
                doc.append(
                    "add_ons",
                    {"add_on": row.get("add_on"), "quantity": row.get("quantity")},
                )


def _ticket_summary(soc, partner_name):
    rows = (
        ("Partner", partner_name),
        ("Customer", soc.customer_company_name),
        ("SOC Type", soc.soc_type),
        ("Package", soc.package_type),
        ("Subscription Period", soc.subscription_period or "-"),
        ("Go-Live Target Date", soc.go_live_target_date or "-"),
        ("SOC Request Reference", soc.name),
    )
    items = "".join(
        f"<li><strong>{escape(label)}:</strong> {escape(str(value))}</li>"
        for label, value in rows
    )
    return sanitize_html(f"<p>Permintaan SOC baru telah diajukan.</p><ul>{items}</ul>")


def form_options():
    membership = require_partner()
    return {
        "partner": frappe.db.get_value(
            "HD Customer", membership.partner, "customer_name"
        )
        or membership.partner,
        "soc_types": list(SOC_TYPES),
        "packages": frappe.get_all(
            "HRD SOC Package",
            filters={"active": 1},
            fields=["name", "package_name"],
            order_by="package_name asc",
        ),
        "payment_terms": frappe.get_all(
            "HRD SOC Payment Term",
            filters={"active": 1},
            fields=["name", "term_name"],
            order_by="term_name asc",
        ),
        "add_ons": frappe.get_all(
            "HRD SOC Add-on Master",
            filters={"active": 1},
            fields=["name", "add_on_name"],
            order_by="add_on_name asc",
        ),
        "customers": frappe.get_all(
            "HD Customer",
            filters={"custom_hrdesk_responsible_partner": membership.partner},
            fields=["name", "customer_name"],
            order_by="customer_name asc",
            limit_page_length=100,
        ),
    }


def create_request(values, attachments=None):
    membership = require_partner()
    values = data(values)
    client_request_id = str(values.get("client_request_id") or "").strip()
    if len(client_request_id) < 8 or len(client_request_id) > 128:
        frappe.throw(_("Client Request ID tidak valid."))

    existing = frappe.db.get_value(
        "HRD SOC Request",
        {"partner": membership.partner, "client_request_id": client_request_id},
        ["name", "ticket", "soc_status"],
        as_dict=True,
    )
    if existing:
        return {**existing, "created": False}

    _authorized_customer(values.get("customer"), membership.partner)
    files = pending_files(attachments)
    soc = frappe.new_doc("HRD SOC Request")
    soc.partner = membership.partner
    soc.submitted_by = frappe.session.user
    soc.submission_date = today()
    soc.client_request_id = client_request_id
    soc.soc_status = "Submitted"
    _apply_values(soc, values)
    soc.insert(ignore_permissions=True)

    partner_name = frappe.db.get_value(
        "HD Customer", membership.partner, "customer_name"
    ) or membership.partner
    ticket = frappe.new_doc("HD Ticket")
    ticket.subject = (
        f"SOC Request - {soc.customer_company_name} - {soc.soc_type}"
    )[:140]
    ticket.description = _ticket_summary(soc, partner_name)
    ticket.raised_by = frappe.session.user
    ticket.via_customer_portal = 1
    ticket.ticket_type = SOC_TICKET_TYPE
    ticket.custom_portal_request_kind = SOC_REQUEST_KIND
    ticket.custom_partner_organization = membership.partner
    ticket.custom_partner_submitted_by = frappe.session.user
    ticket.custom_relevant_customer = soc.customer or None
    ticket.custom_soc_request = soc.name
    ticket.agent_group = COMMERCIAL_TEAM
    ticket.insert(ignore_permissions=True)

    soc.ticket = ticket.name
    soc.flags.hrdesk_link_ticket = True
    soc.save(ignore_permissions=True)
    for file in files:
        file.attached_to_doctype = "HD Ticket"
        file.attached_to_name = ticket.name
        file.save(ignore_permissions=True)
    return {
        "name": soc.name,
        "ticket": ticket.name,
        "soc_status": soc.soc_status,
        "created": True,
    }


def _request_for_partner(name):
    request = frappe.get_doc("HRD SOC Request", name)
    if not can_access_soc_request(request):
        frappe.throw(_("Anda tidak memiliki akses ke permintaan ini."), frappe.PermissionError)
    return request


def ticket_for_reference(name):
    if frappe.db.exists("HRD SOC Request", name):
        request = _request_for_partner(name)
        return frappe.get_doc("HD Ticket", request.ticket)
    ticket = frappe.get_doc("HD Ticket", name)
    if ticket.custom_portal_request_kind != SOC_REQUEST_KIND:
        frappe.throw(_("Permintaan SOC tidak ditemukan."), frappe.DoesNotExistError)
    if not can_access_soc(ticket, require_partner()):
        frappe.throw(_("Anda tidak memiliki akses ke permintaan ini."), frappe.PermissionError)
    return ticket


def list_requests(scope="mine", search="", status="", limit=50):
    membership = require_partner()
    filters = {"partner": membership.partner}
    if scope == "organization":
        if not is_request_manager():
            frappe.throw(_("Akses manajer permintaan diperlukan."), frappe.PermissionError)
    else:
        filters["submitted_by"] = frappe.session.user
    if status:
        filters["soc_status"] = status
    or_filters = None
    if str(search or "").strip():
        term = f"%{str(search).strip()[:80]}%"
        or_filters = {"name": ["like", term], "customer_company_name": ["like", term]}
    rows = frappe.get_all(
        "HRD SOC Request",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "submission_date",
            "customer_company_name",
            "package_type",
            "subscription_start_date",
            "subscription_end_date",
            "soc_status",
            "ticket",
            "modified",
        ],
        order_by="modified desc",
        limit_page_length=min(max(int(limit or 50), 1), 100),
    )
    ticket_names = [row.ticket for row in rows if row.ticket]
    ticket_statuses = {
        row.name: row.status
        for row in frappe.get_all(
            "HD Ticket",
            filters={"name": ["in", ticket_names]},
            fields=["name", "status"],
        )
    } if ticket_names else {}
    for row in rows:
        row["ticket_status"] = ticket_statuses.get(row.ticket)
    return rows


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


def get_request(name):
    request = _request_for_partner(name)
    result = {field: request.get(field) for field in REQUEST_FIELDS}
    result["add_ons"] = [
        {"add_on": row.add_on, "quantity": row.quantity}
        for row in request.add_ons
    ]
    ticket = frappe.get_doc("HD Ticket", request.ticket)
    result["ticket_status"] = ticket.status
    result["ticket_subject"] = ticket.subject
    result["ticket_url"] = f"/helpdesk/my-tickets/{quote(ticket.name)}"
    result["description"] = ticket.description
    result["can_edit"] = request.soc_status == "Revision Requested"
    result["replies"] = frappe.get_all(
        "Communication",
        filters={"reference_doctype": "HD Ticket", "reference_name": ticket.name},
        fields=["name", "sender", "content", "communication_date"],
        order_by="creation asc",
    )
    result["attachments"] = _files_for("HD Ticket", ticket.name)
    for reply in result["replies"]:
        reply["attachments"] = _files_for("Communication", reply.name)
    documents = frappe.get_all(
        "HRD SOC Document",
        filters={"soc_request": request.name, "released": 1},
        fields=["name", "version", "print_format", "file", "released_on"],
        order_by="version desc",
    )
    for document in documents:
        document["download_url"] = (
            "/api/method/hrdesk_helpdesk_customizations.api.partner_portal.download"
            f"?file_name={quote(document.file)}"
        )
    result["documents"] = documents
    return result


def update_request(name, values, attachments=None):
    request = _request_for_partner(name)
    if request.soc_status != "Revision Requested":
        frappe.throw(_("SOC hanya dapat diperbarui saat revisi diminta."), frappe.PermissionError)
    values = data(values)
    files = pending_files(attachments)
    _authorized_customer(values.get("customer"), request.partner)
    _apply_values(request, values)
    request.flags.hrdesk_partner_revision = True
    request.soc_status = "Under Review"
    request.save(ignore_permissions=True)
    ticket = frappe.get_doc("HD Ticket", request.ticket)
    ticket.create_communication_via_contact(
        plain_html(
            f"Data SOC {request.name} telah diperbarui sesuai permintaan revisi."
        ),
        attachments=[{"name": file.name} for file in files],
    )
    return {"name": request.name, "soc_status": request.soc_status, "ticket": request.ticket}


def set_status(name, status, revision_reason=""):
    require_commercial()
    if status not in SOC_STATUSES:
        frappe.throw(_("Status SOC tidak valid."))
    request = frappe.get_doc("HRD SOC Request", name)
    if status == "Revision Requested" and not str(revision_reason or "").strip():
        frappe.throw(_("Alasan revisi wajib diisi."))
    request.revision_reason = str(revision_reason or "").strip() or request.revision_reason
    request.soc_status = status
    request.save()
    return {"name": request.name, "soc_status": request.soc_status}


def print_formats():
    require_commercial()
    return frappe.get_all(
        "Print Format",
        filters={"doc_type": "HRD SOC Request", "disabled": 0},
        pluck="name",
        order_by="name asc",
    )


def generate_pdf(name, print_format="SOC Request Form - Standard"):
    require_commercial()
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status not in {"Approved", "PDF Sent"}:
        frappe.throw(_("PDF hanya dapat dibuat dari SOC yang sudah Approved."))
    if not frappe.db.exists(
        "Print Format", {"name": print_format, "doc_type": "HRD SOC Request", "disabled": 0}
    ):
        frappe.throw(_("Template PDF tidak valid."))

    previous = frappe.get_all(
        "HRD SOC Document",
        filters={"soc_request": request.name},
        fields=["version"],
        order_by="version desc",
        limit_page_length=1,
    )
    version = int(previous[0].version if previous else 0) + 1
    document = frappe.get_doc(
        {
            "doctype": "HRD SOC Document",
            "soc_request": request.name,
            "ticket": request.ticket,
            "version": version,
            "print_format": print_format,
            "released": 0,
            "generated_by": frappe.session.user,
            "generated_on": now_datetime(),
        }
    ).insert()
    pdf = frappe.get_print(
        "HRD SOC Request", request.name, print_format=print_format, as_pdf=True
    )
    file = save_file(
        f"{request.name}-v{version}.pdf",
        pdf,
        "HRD SOC Document",
        document.name,
        is_private=1,
    )
    document.file = file.name
    document.save()
    return {
        "name": document.name,
        "version": version,
        "download_url": (
            "/api/method/hrdesk_helpdesk_customizations.api.partner_portal.download"
            f"?file_name={quote(file.name)}"
        ),
        "released": False,
    }


def list_documents_internal(name):
    require_commercial()
    return frappe.get_all(
        "HRD SOC Document",
        filters={"soc_request": name},
        fields=["name", "version", "print_format", "file", "released", "generated_on"],
        order_by="version desc",
    )


def release_document(document_name, message):
    require_commercial()
    document = frappe.get_doc("HRD SOC Document", document_name)
    if document.released:
        return {"name": document.name, "released": True, "communication": document.communication}
    request = frappe.get_doc("HRD SOC Request", document.soc_request)
    if request.soc_status not in {"Approved", "PDF Sent"}:
        frappe.throw(_("SOC harus Approved sebelum dokumen dirilis."))
    if not document.file:
        frappe.throw(_("File PDF belum tersedia."))
    message = str(message or "").strip()
    if not message:
        frappe.throw(_("Pesan balasan wajib diisi."))

    ticket = frappe.get_doc("HD Ticket", request.ticket)
    ticket.reply_via_agent(
        plain_html(message),
        to=ticket.raised_by,
        attachments=[document.file],
    )
    communication = frappe.db.get_value(
        "Communication",
        {
            "reference_doctype": "HD Ticket",
            "reference_name": ticket.name,
            "sent_or_received": "Sent",
        },
        "name",
        order_by="creation desc",
    )
    source_url = frappe.db.get_value("File", document.file, "file_url")
    ticket_file = frappe.db.get_value(
        "File",
        {
            "attached_to_doctype": "HD Ticket",
            "attached_to_name": ticket.name,
            "file_url": source_url,
        },
        "name",
        order_by="creation desc",
    )
    document.released = 1
    document.released_by = frappe.session.user
    document.released_on = now_datetime()
    document.communication = communication
    document.ticket_file = ticket_file
    document.save()
    if request.soc_status != "PDF Sent":
        request.soc_status = "PDF Sent"
        request.save()
    return {
        "name": document.name,
        "released": True,
        "communication": communication,
        "ticket_file": ticket_file,
    }


def download_file(file_name):
    file = frappe.get_doc("File", file_name)
    if not file.is_private:
        frappe.throw(_("Dokumen SOC wajib disimpan sebagai file privat."), frappe.PermissionError)
    if file.attached_to_doctype == "HRD SOC Document":
        document = frappe.get_doc("HRD SOC Document", file.attached_to_name)
        if not can_access_soc_document(document):
            frappe.throw(_("Anda tidak memiliki akses ke dokumen ini."), frappe.PermissionError)
    else:
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
        ticket = frappe.get_doc("HD Ticket", ticket_name)
        if not is_internal() and not can_access_soc(ticket, require_partner()):
            frappe.throw(_("Anda tidak memiliki akses ke dokumen ini."), frappe.PermissionError)
    filename, content = get_file(file.file_url)
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = content
    frappe.local.response.type = "download"
    frappe.local.response.headers = {
        "Cache-Control": "private, no-store, max-age=0",
        "Pragma": "no-cache",
    }

