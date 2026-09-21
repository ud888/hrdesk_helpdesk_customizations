# HR Desk Helpdesk Customizations

Minimal Frappe application for HR Desk-specific Helpdesk behavior.

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
