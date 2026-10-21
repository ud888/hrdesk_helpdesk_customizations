import frappe


STATUS_MAP = {
    "Draft": "SOC Requested",
    "Submitted": "SOC Requested",
    "Under Review": "SOC Requested",
    "Revision Requested": "SOC Requested",
    "Approved": "SOC Requested",
    "PDF Sent": "SOC Published",
    "Completed": "SOC Published",
    "Cancelled": "Cancelled",
}


def execute():
    """Conservatively migrate the legacy workflow without implying signatures or provisioning."""
    if not frappe.db.exists("DocType", "HRD SOC Request"):
        return
    for old_status, new_status in STATUS_MAP.items():
        frappe.db.sql(
            """
            UPDATE `tabHRD SOC Request`
            SET soc_status = %s,
                request_version = COALESCE(NULLIF(request_version, 0), 1),
                partner_update_allowed = 0
            WHERE soc_status = %s
            """,
            (new_status, old_status),
        )
    if frappe.db.exists("DocType", "HRD SOC Document"):
        frappe.db.sql(
            """
            UPDATE `tabHRD SOC Document`
            SET request_version = COALESCE(NULLIF(request_version, 0), 1),
                document_type = COALESCE(NULLIF(document_type, ''), 'Partner SOC'),
                document_status = CASE
                    WHEN released = 1 THEN 'Published'
                    ELSE 'Draft'
                END
            """
        )
