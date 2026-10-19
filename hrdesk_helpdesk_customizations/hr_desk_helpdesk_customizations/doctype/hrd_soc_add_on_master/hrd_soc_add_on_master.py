from frappe.model.document import Document


class HRDSOCAddOnMaster(Document):
    pass


# Frappe removes hyphens when resolving a DocType controller class. Keep the
# generated class name for compatibility and expose the name Frappe expects for
# the "HRD SOC Add-on Master" DocType.
HRDSOCAddonMaster = HRDSOCAddOnMaster

