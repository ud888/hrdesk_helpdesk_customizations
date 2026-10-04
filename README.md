# HR Desk Helpdesk Customizations

Focused Frappe application for the HR Desk customer and partner experiences on
one Helpdesk site and database.

## Knowledge Base category order

The app overrides `helpdesk.api.knowledge_base.get_categories` and preserves the
upstream category data while returning the seven HR Desk customer-portal
categories in this order:

1. Panduan Tampilan
2. Karyawan
3. Kehadiran
4. Cuti & Lembur
5. Klaim & Loan
6. Payroll
7. Panel Admin

Any future category not listed above remains visible after these categories and
keeps its relative order from Helpdesk. Empty categories remain excluded because
the upstream Helpdesk method continues to provide the source response.

## Customer portal ticketing feature flag

The site configuration key `CUSTOMER_PORTAL_TICKETING_ENABLED` controls only
customer-portal ticketing. It defaults to `false` when the key is absent.

- `false`: Knowledge Base-only customer portal.
- `true`: Knowledge Base plus customer ticketing.

Store the setting in the site's `site_config.json`. On Frappe Cloud, manage it
from the site's **Site Config** tab. Use a JSON boolean, not a quoted string.

When disabled, the app:

- redirects `/helpdesk` and `/helpdesk/my-tickets...` customer requests to
  `/helpdesk/kb-public`;
- hides customer ticket navigation and links to customer ticket routes;
- rewrites customer SPA navigation attempts to the Knowledge Base; and
- blocks customer calls to `helpdesk.helpdesk.doctype.hd_ticket.api.new` and
  customer-role `HD Ticket` inserts.

Agent routes such as `/helpdesk/tickets...`, agent ticket APIs, the `HD Ticket`
DocType, and email-to-ticket processing are not disabled or removed.

## One-site partner portal

The same Frappe site can serve:

- `support.hrdesk.id` for the existing customer Helpdesk portal; and
- `partner.hrdesk.id` with `/partners` as the authenticated partner entrance.

The hostname only selects the entrance. Authorization always uses roles and an
active `HRD Partner Membership`; it never trusts the hostname.

Native `HD Article` records remain authoritative. `HD Article Category` has an
administrator-editable `custom_hrdesk_audience` value: Public, Customer,
Partner, or Internal. Existing categories are classified Public on migration so
the current customer KB remains available.

Partner SOC requests remain native `HD Ticket` records. The server derives the
submitting user and partner organization from membership. Partner members see
their own SOC requests; designated request managers see their own partner's SOC
requests. Internal notes are not returned by the partner APIs.

Before enabling partner access, configure the site keys:

```json
{
  "allowed_custom_endpoints": [
    "hrdesk_helpdesk_customizations.api.partner_portal"
  ],
  "HRDESK_PORTAL_ENFORCE_TEAM_RESTRICTIONS": false
}
```

Leave team enforcement false until every external L1 agent has an active
membership, every partner has an L1 team, and every supported customer is mapped
to its responsible partner. Then set it to true and migrate the explicit site.
Never use an all-sites migration for this rollout.
