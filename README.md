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

