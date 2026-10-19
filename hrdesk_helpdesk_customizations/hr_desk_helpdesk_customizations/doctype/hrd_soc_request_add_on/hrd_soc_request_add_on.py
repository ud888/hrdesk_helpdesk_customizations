from frappe.model.document import Document


class HRDSOCRequestAddOn(Document):
    pass


# Frappe removes hyphens when resolving a DocType controller class. Keep the
# generated class name for compatibility and expose the name Frappe expects for
# the "HRD SOC Request Add-on" DocType.
HRDSOCRequestAddon = HRDSOCRequestAddOn

