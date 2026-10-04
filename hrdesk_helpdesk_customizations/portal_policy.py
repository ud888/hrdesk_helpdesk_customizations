from hrdesk_helpdesk_customizations.portal_constants import SOC_REQUEST_KIND


def ticket_scope_sql(user, membership, escape):
    """Additional SQL restriction layered on top of native Helpdesk permissions."""
    if not membership:
        return ""
    user_value = escape(user)
    partner_value = escape(membership.partner)
    own_soc = f"`tabHD Ticket`.custom_partner_submitted_by = {user_value}"
    if membership.request_manager:
        own_soc = (
            f"`tabHD Ticket`.custom_partner_organization = {partner_value}"
        )
    kind = escape(SOC_REQUEST_KIND)
    own_ticket = (
        "(`tabHD Ticket`.owner = {u} OR `tabHD Ticket`.contact = {u} "
        "OR `tabHD Ticket`.raised_by = {u})"
    ).format(u=user_value)
    customer_scope = own_ticket
    if membership.l1_support_access:
        customer_scope = (
            f"({own_ticket} OR EXISTS (SELECT 1 FROM `tabHD Customer` customer "
            "WHERE customer.name = `tabHD Ticket`.customer "
            f"AND customer.custom_hrdesk_responsible_partner = {partner_value}))"
        )
    return (
        f"((COALESCE(`tabHD Ticket`.custom_portal_request_kind, '') = {kind} "
        f"AND ({own_soc})) OR (COALESCE(`tabHD Ticket`.custom_portal_request_kind, '') != {kind} "
        f"AND {customer_scope}))"
    )


def can_access_soc(ticket, membership) -> bool:
    if not membership:
        return False
    if ticket.custom_partner_organization != membership.partner:
        return False
    if membership.request_manager:
        return True
    return ticket.custom_partner_submitted_by == membership.user
