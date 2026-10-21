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
    SOC_REQUEST_KIND,
    SOC_TICKET_TYPE,
    TECHNICAL_ROLE,
)
from hrdesk_helpdesk_customizations.portal_policy import can_access_soc
from hrdesk_helpdesk_customizations.soc_access import (
    can_access_soc_document,
    can_access_soc_request,
)
from hrdesk_helpdesk_customizations.soc_rules import SOC_STATUSES, SOC_TYPES


PARTNER_SOC_FORMAT = "Partner SOC - New Customer"
END_CUSTOMER_SAC_FORMAT = "End Customer SAC - New Customer"
DOCUMENT_FORMATS = {
    "Partner SOC": PARTNER_SOC_FORMAT,
    "End Customer SAC": END_CUSTOMER_SAC_FORMAT,
}


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
    "customer_tax_id",
    "customer_pic_name",
    "customer_pic_position",
    "customer_pic_email",
    "customer_pic_phone",
    "super_admin_name",
    "super_admin_position",
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
    "subscription_number",
    "package_description",
    "monthly_price",
    "annual_subtotal",
    "partner_discount_percent",
    "annual_total_after_discount",
    "payment_scheme",
    "request_version",
    "partner_update_allowed",
    "revision_reason",
    "signature_rejection_reason",
    "cancellation_requested_by",
    "cancellation_requested_on",
    "cancellation_reason",
    "creation",
    "modified",
)

EDITABLE_FIELDS = {
    "soc_type",
    "customer",
    "customer_company_name",
    "customer_address",
    "customer_tax_id",
    "customer_pic_name",
    "customer_pic_position",
    "customer_pic_email",
    "customer_pic_phone",
    "super_admin_name",
    "super_admin_position",
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
    "subscription_number",
    "package_description",
    "monthly_price",
    "partner_discount_percent",
    "payment_scheme",
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


def require_hds():
    roles = roles_for()
    if frappe.session.user != "Administrator" and COMMERCIAL_ROLE not in roles:
        frappe.throw(_("Akses HDS diperlukan."), frappe.PermissionError)


def require_hdt():
    roles = roles_for()
    if frappe.session.user != "Administrator" and not roles.intersection(
        {COMMERCIAL_ROLE, TECHNICAL_ROLE}
    ):
        frappe.throw(_("Akses HDS atau HDT diperlukan."), frappe.PermissionError)


def require_system_manager():
    if frappe.session.user != "Administrator" and "System Manager" not in roles_for():
        frappe.throw(_("Akses System Manager diperlukan."), frappe.PermissionError)


def _role_users(role):
    users = frappe.get_all(
        "Has Role",
        filters={"role": role, "parenttype": "User"},
        pluck="parent",
    )
    return [
        user
        for user in users
        if frappe.db.get_value("User", user, "enabled") and user != "Administrator"
    ]


def _partner_supervisors(partner):
    return frappe.get_all(
        "HRD Partner Membership",
        filters={
            "partner": partner,
            "active": 1,
            "portal_access": 1,
            "request_manager": 1,
        },
        pluck="user",
    )


def _notify(recipients, subject, message):
    recipients = sorted({recipient for recipient in recipients if recipient})
    if recipients:
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=plain_html(message),
            delayed=True,
        )


def _record_event(
    request,
    event_type,
    action,
    *,
    from_status="",
    to_status="",
    details="",
    document_version=0,
    attempt_no=0,
):
    frappe.get_doc(
        {
            "doctype": "HRD SOC Event",
            "soc_request": request.name,
            "ticket": request.ticket,
            "event_type": event_type,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "request_version": request.request_version,
            "document_version": document_version,
            "attempt_no": attempt_no,
            "details": str(details or "").strip(),
            "actor": frappe.session.user,
            "event_on": now_datetime(),
        }
    ).insert(ignore_permissions=True)


def _transition(request, target, actor, action, event_type="Transition", details=""):
    previous = request.soc_status
    request.flags.hrdesk_workflow_action = True
    request.flags.hrdesk_workflow_actor = actor
    request.soc_status = target
    request.last_transition_by = frappe.session.user
    request.last_transition_on = now_datetime()
    request.save(ignore_permissions=True)
    _record_event(
        request,
        event_type,
        action,
        from_status=previous,
        to_status=target,
        details=details,
    )
    return request


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
    soc.soc_status = "SOC Requested"
    soc.request_version = 1
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
    _record_event(
        soc,
        "Transition",
        "Submit SOC Request",
        to_status="SOC Requested",
    )
    _notify(
        [frappe.session.user, *_partner_supervisors(soc.partner), *_role_users(COMMERCIAL_ROLE)],
        f"SOC Requested - {soc.name}",
        f"Permintaan SOC {soc.name} untuk {soc.customer_company_name} telah diajukan.",
    )
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


def get_workspace_handoff(name):
    request = _request_for_partner(name)
    if frappe.session.user != request.submitted_by:
        frappe.throw(
            _("Workspace handoff hanya tersedia bagi PA yang mengajukan SOC."),
            frappe.PermissionError,
        )
    if request.soc_status != "Workspace Created":
        frappe.throw(_("Workspace handoff belum tersedia."), frappe.DoesNotExistError)
    handoff_name = frappe.db.get_value(
        "HRD SOC Handoff", {"soc_request": request.name}, "name"
    )
    if not handoff_name:
        frappe.throw(_("Workspace handoff belum tersedia."), frappe.DoesNotExistError)
    handoff = frappe.get_doc("HRD SOC Handoff", handoff_name)
    return {
        "workspace_reference": handoff.workspace_reference,
        "access_username": handoff.access_username,
        "access_secret": handoff.get_password("access_secret"),
        "instructions": handoff.instructions,
        "created_on": handoff.created_on,
    }


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
    result["can_edit"] = bool(
        request.soc_status == "SOC Requested" and request.partner_update_allowed
    )
    result["can_submit_signed"] = request.soc_status == "SOC Published"
    result["can_request_cancellation"] = request.soc_status in {
        "SOC Requested",
        "SOC Published",
    }
    result["handoff_available"] = bool(
        request.soc_status == "Workspace Created"
        and frappe.session.user == request.submitted_by
        and frappe.db.exists("HRD SOC Handoff", {"soc_request": request.name})
    )
    result["replies"] = frappe.get_all(
        "Communication",
        filters={
            "reference_doctype": "HD Ticket",
            "reference_name": ticket.name,
            "communication_type": "Communication",
        },
        fields=["name", "sender", "content", "communication_date"],
        order_by="creation asc",
    )
    result["attachments"] = _files_for("HD Ticket", ticket.name)
    for reply in result["replies"]:
        reply["attachments"] = _files_for("Communication", reply.name)
    documents = frappe.get_all(
        "HRD SOC Document",
        filters={"soc_request": request.name, "released": 1},
        fields=[
            "name",
            "request_version",
            "document_type",
            "version",
            "print_format",
            "file",
            "document_status",
            "signed_file",
            "released_on",
            "signed_on",
        ],
        order_by="request_version desc, document_type asc",
    )
    for document in documents:
        document["download_url"] = (
            "/api/method/hrdesk_helpdesk_customizations.api.partner_portal.download"
            f"?file_name={quote(document.file)}"
        )
        if document.signed_file:
            document["signed_download_url"] = (
                "/api/method/hrdesk_helpdesk_customizations.api.partner_portal.download"
                f"?file_name={quote(document.signed_file)}"
            )
    result["documents"] = documents
    return result


def update_request(name, values, attachments=None):
    request = _request_for_partner(name)
    if request.soc_status != "SOC Requested" or not request.partner_update_allowed:
        frappe.throw(_("SOC hanya dapat diperbarui setelah amendment dibuka oleh HDS."), frappe.PermissionError)
    values = data(values)
    files = pending_files(attachments)
    _authorized_customer(values.get("customer"), request.partner)
    _apply_values(request, values)
    request.flags.hrdesk_partner_revision = True
    request.partner_update_allowed = 0
    request.save(ignore_permissions=True)
    ticket = frappe.get_doc("HD Ticket", request.ticket)
    ticket.create_communication_via_contact(
        plain_html(
            f"Data SOC {request.name} telah diperbarui sesuai permintaan amendment."
        ),
        attachments=[{"name": file.name} for file in files],
    )
    _record_event(
        request,
        "Amendment",
        "Partner Submitted Amendment",
        details=request.revision_reason,
    )
    _notify(
        _role_users(COMMERCIAL_ROLE),
        f"SOC Amendment Submitted - {request.name}",
        f"Data amendment untuk SOC {request.name} telah dikirim oleh partner.",
    )
    return {"name": request.name, "soc_status": request.soc_status, "ticket": request.ticket}


def set_status(name, status, revision_reason=""):
    del name, status, revision_reason
    frappe.throw(_("Gunakan aksi workflow SOC yang sesuai."), frappe.PermissionError)


def print_formats():
    require_hds()
    return frappe.get_all(
        "Print Format",
        filters={"doc_type": "HRD SOC Request", "disabled": 0},
        pluck="name",
        order_by="name asc",
    )


def _latest_document_version(name):
    rows = frappe.get_all(
        "HRD SOC Document",
        filters={"soc_request": name},
        fields=["version"],
        order_by="version desc",
        limit_page_length=1,
    )
    return int(rows[0].version if rows else 0)


def _document_pair(name, version=None, released=None):
    filters = {"soc_request": name}
    if version is not None:
        filters["version"] = version
    if released is not None:
        filters["released"] = int(bool(released))
    return frappe.get_all(
        "HRD SOC Document",
        filters=filters,
        fields=[
            "name",
            "request_version",
            "document_type",
            "version",
            "print_format",
            "file",
            "document_status",
            "released",
            "signed_file",
            "communication",
        ],
        order_by="version desc, document_type asc",
    )


def generate_document_pair(name):
    require_hds()
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status not in {"SOC Requested", "SOC Published"}:
        frappe.throw(_("Dokumen hanya dapat dibuat sebelum signed submission."))
    if request.partner_update_allowed:
        frappe.throw(_("Partner harus menyelesaikan amendment sebelum dokumen dibuat."))
    for print_format in DOCUMENT_FORMATS.values():
        if not frappe.db.exists(
            "Print Format",
            {"name": print_format, "doc_type": "HRD SOC Request", "disabled": 0},
        ):
            frappe.throw(_("Print Format {0} belum tersedia.").format(print_format))

    latest = _latest_document_version(name)
    existing = _document_pair(name, latest) if latest else []
    if len(existing) == 2 and not any(row.released for row in existing):
        return {"version": latest, "documents": existing, "created": False}

    version = latest + 1
    documents = []
    for document_type, print_format in DOCUMENT_FORMATS.items():
        document = frappe.get_doc(
            {
                "doctype": "HRD SOC Document",
                "soc_request": request.name,
                "ticket": request.ticket,
                "request_version": request.request_version,
                "document_type": document_type,
                "version": version,
                "print_format": print_format,
                "document_status": "Draft",
                "released": 0,
                "generated_by": frappe.session.user,
                "generated_on": now_datetime(),
            }
        ).insert(ignore_permissions=True)
        pdf = frappe.get_print(
            "HRD SOC Request", request.name, print_format=print_format, as_pdf=True
        )
        suffix = "partner-soc" if document_type == "Partner SOC" else "customer-sac"
        file = save_file(
            f"{request.name}-v{version}-{suffix}.pdf",
            pdf,
            "HRD SOC Document",
            document.name,
            is_private=1,
        )
        document.flags.hrdesk_document_action = True
        document.file = file.name
        document.save(ignore_permissions=True)
        documents.append(
            {
                "name": document.name,
                "document_type": document_type,
                "version": version,
                "download_url": (
                    "/api/method/hrdesk_helpdesk_customizations.api.partner_portal.download"
                    f"?file_name={quote(file.name)}"
                ),
            }
        )
    _record_event(
        request,
        "Document Publication",
        "Generate SOC/SAC Pair",
        document_version=version,
    )
    return {"version": version, "documents": documents, "created": True}


def list_documents_internal(name):
    require_hdt()
    return frappe.get_all(
        "HRD SOC Document",
        filters={"soc_request": name},
        fields=[
            "name",
            "request_version",
            "document_type",
            "version",
            "print_format",
            "file",
            "document_status",
            "released",
            "signed_file",
            "generated_on",
        ],
        order_by="version desc, document_type asc",
    )


def publish_document_pair(name, message):
    require_hds()
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status not in {"SOC Requested", "SOC Published"}:
        frappe.throw(_("Dokumen hanya dapat dipublikasikan sebelum signed submission."))
    version = _latest_document_version(name)
    documents = _document_pair(name, version)
    if {row.document_type for row in documents} != set(DOCUMENT_FORMATS):
        frappe.throw(_("Partner SOC dan End Customer SAC wajib tersedia."))
    if any(not row.file for row in documents):
        frappe.throw(_("File Partner SOC dan End Customer SAC wajib tersedia."))
    if all(row.released for row in documents):
        return {"version": version, "published": True, "documents": documents}
    message = str(message or "").strip()
    if not message:
        frappe.throw(_("Pesan balasan wajib diisi."))

    ticket = frappe.get_doc("HD Ticket", request.ticket)
    ticket.reply_via_agent(
        plain_html(message),
        to=ticket.raised_by,
        attachments=[row.file for row in documents],
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
    for old in frappe.get_all(
        "HRD SOC Document",
        filters={"soc_request": name, "released": 1, "version": ["<", version]},
        pluck="name",
    ):
        old_document = frappe.get_doc("HRD SOC Document", old)
        old_document.flags.hrdesk_document_action = True
        old_document.document_status = "Superseded"
        old_document.save(ignore_permissions=True)
    for row in documents:
        document = frappe.get_doc("HRD SOC Document", row.name)
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
        document.flags.hrdesk_document_action = True
        document.released = 1
        document.document_status = "Published"
        document.released_by = frappe.session.user
        document.released_on = now_datetime()
        document.communication = communication
        document.ticket_file = ticket_file
        document.save(ignore_permissions=True)
    if request.soc_status == "SOC Requested":
        request.published_by = frappe.session.user
        request.published_on = now_datetime()
        _transition(
            request,
            "SOC Published",
            "hds",
            "Publish SOC/SAC Pair",
            "Document Publication",
            f"Document version {version}",
        )
    else:
        _record_event(
            request,
            "Document Publication",
            "Republish SOC/SAC Pair",
            document_version=version,
        )
    _notify(
        _partner_supervisors(request.partner),
        f"SOC Documents Published - {request.name}",
        f"Partner SOC dan End Customer SAC versi {version} telah tersedia.",
    )
    return {"version": version, "published": True, "communication": communication}


def submit_signed_document_pair(name, partner_soc_file, customer_sac_file, message=""):
    request = _request_for_partner(name)
    if request.soc_status != "SOC Published":
        frappe.throw(_("Signed documents hanya dapat dikirim pada status SOC Published."))
    files = pending_files([partner_soc_file, customer_sac_file])
    if len(files) != 2 or files[0].name == files[1].name:
        frappe.throw(_("Signed Partner SOC dan End Customer SAC wajib diunggah terpisah."))
    allowed_extensions = (".pdf", ".png", ".jpg", ".jpeg")
    for file in files:
        if not str(file.file_name or "").lower().endswith(allowed_extensions):
            frappe.throw(_("Signed document harus berupa PDF, PNG, atau JPG."))
    version = _latest_document_version(name)
    documents = _document_pair(name, version, released=True)
    by_type = {row.document_type: row for row in documents}
    if set(by_type) != set(DOCUMENT_FORMATS):
        frappe.throw(_("Pasangan dokumen published tidak lengkap."))
    ticket = frappe.get_doc("HD Ticket", request.ticket)
    ticket.create_communication_via_contact(
        plain_html(message or f"Signed Partner SOC dan End Customer SAC untuk {name} telah dikirim."),
        attachments=[{"name": file.name} for file in files],
    )
    submitted = {
        "Partner SOC": files[0].name,
        "End Customer SAC": files[1].name,
    }
    for document_type, row in by_type.items():
        document = frappe.get_doc("HRD SOC Document", row.name)
        document.flags.hrdesk_document_action = True
        document.signed_file = submitted[document_type]
        document.signed_by = frappe.session.user
        document.signed_on = now_datetime()
        document.document_status = "Signed"
        document.signature_rejection_reason = None
        document.save(ignore_permissions=True)
    request.signed_by = frappe.session.user
    request.signed_on = now_datetime()
    request.signature_rejection_reason = None
    _transition(
        request,
        "SOC Signed",
        "partner",
        "Submit Signed SOC/SAC",
        "Signed Submission",
        f"Document version {version}",
    )
    _notify(
        _role_users(COMMERCIAL_ROLE),
        f"Signed SOC/SAC Submitted - {request.name}",
        f"Signed Partner SOC dan End Customer SAC untuk {request.name} menunggu pemeriksaan HDS.",
    )
    return {"name": request.name, "soc_status": request.soc_status, "version": version}


def reject_signed_documents(name, reason):
    require_hds()
    reason = str(reason or "").strip()
    if not reason:
        frappe.throw(_("Alasan penolakan signature wajib diisi."))
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status != "SOC Signed":
        frappe.throw(_("Hanya SOC Signed yang dapat ditolak."))
    version = _latest_document_version(name)
    for row in _document_pair(name, version, released=True):
        document = frappe.get_doc("HRD SOC Document", row.name)
        document.flags.hrdesk_document_action = True
        document.document_status = "Rejected"
        document.signature_rejection_reason = reason
        document.save(ignore_permissions=True)
    request.signature_rejection_reason = reason
    _transition(
        request,
        "SOC Published",
        "hds",
        "Reject Signed SOC/SAC",
        "Signature Rejection",
        reason,
    )
    _notify(
        [request.submitted_by, *_partner_supervisors(request.partner)],
        f"Signed SOC/SAC Rejected - {request.name}",
        f"Signed documents ditolak. Alasan: {reason}",
    )
    return {"name": request.name, "soc_status": request.soc_status}


def approve_workspace_creation(name, acceptance_confirmed=0):
    require_hds()
    if str(acceptance_confirmed).lower() not in {"1", "true", "yes"}:
        frappe.throw(
            _(
                "Konfirmasi bahwa signature lengkap, terbaca, dan sesuai versi published wajib diberikan."
            )
        )
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status != "SOC Signed":
        frappe.throw(_("Workspace hanya dapat disetujui dari status SOC Signed."))
    version = _latest_document_version(name)
    documents = _document_pair(name, version, released=True)
    if len(documents) != 2 or any(not row.signed_file for row in documents):
        frappe.throw(_("Signed Partner SOC dan End Customer SAC wajib lengkap."))
    request.workspace_approved_by = frappe.session.user
    request.workspace_approved_on = now_datetime()
    _transition(request, "Workspace Creation", "hds", "Approve Workspace Creation")
    _notify(
        [*_role_users(TECHNICAL_ROLE), *_role_users(COMMERCIAL_ROLE)],
        f"Workspace Creation Approved - {request.name}",
        f"SOC {request.name} siap diproses untuk workspace creation.",
    )
    _notify(
        [request.submitted_by, *_partner_supervisors(request.partner)],
        f"Workspace Creation In Progress - {request.name}",
        f"SOC {request.name} telah disetujui dan workspace sedang diproses.",
    )
    return {"name": request.name, "soc_status": request.soc_status}


def reopen_for_amendment(name, reason):
    require_hds()
    reason = str(reason or "").strip()
    if not reason:
        frappe.throw(_("Alasan amendment wajib diisi."))
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status not in {"SOC Published", "SOC Signed"}:
        frappe.throw(_("Amendment hanya dapat dibuka setelah SOC dipublikasikan."))
    for row in _document_pair(name):
        if row.document_status in {"Published", "Signed", "Rejected"}:
            document = frappe.get_doc("HRD SOC Document", row.name)
            document.flags.hrdesk_document_action = True
            document.document_status = "Superseded"
            document.save(ignore_permissions=True)
    request.request_version = int(request.request_version or 1) + 1
    request.partner_update_allowed = 1
    request.revision_reason = reason
    request.published_by = None
    request.published_on = None
    request.signed_by = None
    request.signed_on = None
    _transition(
        request,
        "SOC Requested",
        "hds",
        "Reopen for Amendment",
        "Amendment",
        reason,
    )
    _notify(
        [request.submitted_by, *_partner_supervisors(request.partner)],
        f"SOC Amendment Required - {request.name}",
        f"SOC perlu diperbarui. Alasan: {reason}",
    )
    return {"name": request.name, "soc_status": request.soc_status}


def request_cancellation(name, reason):
    request = _request_for_partner(name)
    reason = str(reason or "").strip()
    if request.soc_status not in {"SOC Requested", "SOC Published"}:
        frappe.throw(_("Cancellation hanya dapat diminta sebelum signed submission."))
    if not reason:
        frappe.throw(_("Alasan cancellation wajib diisi."))
    request.flags.hrdesk_partner_cancellation = True
    request.cancellation_requested_by = frappe.session.user
    request.cancellation_requested_on = now_datetime()
    request.cancellation_reason = reason
    request.save(ignore_permissions=True)
    _record_event(request, "Cancellation Requested", "Request Cancellation", details=reason)
    _notify(
        _role_users(COMMERCIAL_ROLE),
        f"SOC Cancellation Requested - {request.name}",
        f"Cancellation SOC {request.name} diminta. Alasan: {reason}",
    )
    return {"name": request.name, "cancellation_requested": True}


def approve_cancellation(name):
    require_hds()
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status in {"Workspace Created", "Cancelled"}:
        frappe.throw(_("SOC ini tidak dapat dibatalkan."))
    if not request.cancellation_reason:
        frappe.throw(_("Cancellation request belum tersedia."))
    request.cancelled_by = frappe.session.user
    request.cancelled_on = now_datetime()
    _transition(
        request,
        "Cancelled",
        "hds",
        "Approve Cancellation",
        "Cancellation Approved",
        request.cancellation_reason,
    )
    _notify(
        [request.submitted_by, *_partner_supervisors(request.partner)],
        f"SOC Cancelled - {request.name}",
        f"SOC {request.name} telah dibatalkan.",
    )
    return {"name": request.name, "soc_status": request.soc_status}


def record_provisioning_failure(name, error_summary):
    require_hdt()
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status != "Workspace Creation":
        frappe.throw(_("Provisioning failure hanya dapat dicatat pada Workspace Creation."))
    error_summary = str(error_summary or "").strip()
    if not error_summary:
        frappe.throw(_("Ringkasan error wajib diisi."))
    attempt_no = frappe.db.count(
        "HRD SOC Event",
        {"soc_request": name, "event_type": ["in", ["Provisioning Failed", "Provisioning Succeeded"]]},
    ) + 1
    _record_event(
        request,
        "Provisioning Failed",
        "Record Provisioning Failure",
        details=error_summary,
        attempt_no=attempt_no,
    )
    _notify(
        [*_role_users(TECHNICAL_ROLE), *_role_users(COMMERCIAL_ROLE)],
        f"Workspace Provisioning Failed - {request.name}",
        f"Provisioning attempt {attempt_no} gagal dan memerlukan tindak lanjut internal.",
    )
    return {"name": request.name, "soc_status": request.soc_status, "attempt_no": attempt_no}


def complete_workspace(name, workspace_reference, access_username, access_secret, instructions=""):
    require_hdt()
    request = frappe.get_doc("HRD SOC Request", name)
    if request.soc_status != "Workspace Creation":
        frappe.throw(_("Workspace hanya dapat diselesaikan pada status Workspace Creation."))
    workspace_reference = str(workspace_reference or "").strip()
    access_username = str(access_username or "").strip()
    access_secret = str(access_secret or "").strip()
    if not workspace_reference or not access_username or not access_secret:
        frappe.throw(_("Workspace reference, username, dan temporary secret wajib diisi."))
    handoff = frappe.get_doc(
        {
            "doctype": "HRD SOC Handoff",
            "soc_request": request.name,
            "ticket": request.ticket,
            "workspace_reference": workspace_reference,
            "access_username": access_username,
            "access_secret": access_secret,
            "instructions": str(instructions or "").strip(),
            "created_by": frappe.session.user,
            "created_on": now_datetime(),
        }
    ).insert(ignore_permissions=True)
    attempt_no = frappe.db.count(
        "HRD SOC Event",
        {"soc_request": name, "event_type": ["in", ["Provisioning Failed", "Provisioning Succeeded"]]},
    ) + 1
    request.workspace_reference = workspace_reference
    request.workspace_created_by = frappe.session.user
    request.workspace_created_on = now_datetime()
    _transition(request, "Workspace Created", "hdt", "Complete Workspace Creation")
    _record_event(
        request,
        "Provisioning Succeeded",
        "Workspace Provisioned",
        attempt_no=attempt_no,
        details=workspace_reference,
    )
    _record_event(request, "Workspace Handoff", "Create Protected Handoff", details=handoff.name)
    ticket = frappe.get_doc("HD Ticket", request.ticket)
    ticket.reply_via_agent(
        plain_html(
            "Workspace telah dibuat. Detail akses tersedia pada pesan terlindungi di Partner Portal dan hanya dapat dibuka oleh PA yang mengajukan SOC."
        ),
        to=ticket.raised_by,
    )
    _notify(
        _partner_supervisors(request.partner),
        f"Workspace Created - {request.name}",
        f"Workspace untuk SOC {request.name} telah dibuat. Detail akses hanya tersedia bagi PA pengaju.",
    )
    return {"name": request.name, "soc_status": request.soc_status, "handoff": handoff.name}


def emergency_override_status(name, status, reason):
    require_system_manager()
    reason = str(reason or "").strip()
    if status not in SOC_STATUSES or not reason:
        frappe.throw(_("Status dan alasan emergency override wajib valid."))
    request = frappe.get_doc("HRD SOC Request", name)
    if status == "SOC Published" and len(_document_pair(name, released=True)) < 2:
        frappe.throw(_("Emergency override tidak dapat melewati dokumen published."))
    if status in {"SOC Signed", "Workspace Creation"}:
        documents = _document_pair(name, _latest_document_version(name), released=True)
        if len(documents) < 2 or any(not row.signed_file for row in documents):
            frappe.throw(_("Emergency override tidak dapat melewati signed SOC/SAC."))
    if status == "Workspace Created" and not frappe.db.exists(
        "HRD SOC Handoff", {"soc_request": name}
    ):
        frappe.throw(_("Emergency override tidak dapat melewati workspace handoff."))
    previous = request.soc_status
    request.flags.hrdesk_emergency_override = True
    request.soc_status = status
    request.last_transition_by = frappe.session.user
    request.last_transition_on = now_datetime()
    request.save(ignore_permissions=True)
    _record_event(
        request,
        "Emergency Override",
        "Emergency Status Override",
        from_status=previous,
        to_status=status,
        details=reason,
    )
    return {"name": request.name, "soc_status": request.soc_status}


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

