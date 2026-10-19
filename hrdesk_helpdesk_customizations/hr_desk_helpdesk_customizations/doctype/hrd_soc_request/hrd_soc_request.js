frappe.ui.form.on("HRD SOC Request", {
  refresh(frm) {
    if (frm.is_new()) return;
    const method = "hrdesk_helpdesk_customizations.api.partner_portal";

    const move = (status, revisionReason = "") =>
      frappe.call({
        method: `${method}.set_soc_status`,
        args: { name: frm.doc.name, status, revision_reason: revisionReason },
        freeze: true,
        callback: () => frm.reload_doc(),
      });

    if (frm.doc.soc_status === "Submitted") {
      frm.add_custom_button(__("Start Review"), () => move("Under Review"));
    }
    if (frm.doc.soc_status === "Under Review") {
      frm.add_custom_button(__("Request Revision"), () => {
        frappe.prompt(
          [{ fieldname: "reason", fieldtype: "Small Text", label: __("Revision Reason"), reqd: 1 }],
          (values) => move("Revision Requested", values.reason),
          __("Request Revision"),
        );
      });
      frm.add_custom_button(__("Approve"), () => move("Approved"));
    }
    if (["Approved", "PDF Sent"].includes(frm.doc.soc_status)) {
      frm.add_custom_button(__("Generate PDF"), async () => {
        const formats = await frappe.call({ method: `${method}.soc_print_formats` });
        const options = formats.message || [];
        if (!options.length) {
          frappe.msgprint(__("No SOC Print Format is available."));
          return;
        }
        frappe.prompt(
          [{ fieldname: "print_format", fieldtype: "Select", label: __("Print Format"), options, default: options[0], reqd: 1 }],
          async (values) => {
            const result = await frappe.call({
              method: `${method}.generate_soc_pdf`,
              args: { name: frm.doc.name, print_format: values.print_format },
              freeze: true,
              freeze_message: __("Generating SOC PDF…"),
            });
            window.open(result.message.download_url, "_blank", "noopener");
            frm.reload_doc();
          },
          __("Generate SOC PDF"),
        );
      });

      frm.add_custom_button(__("Release Latest PDF"), async () => {
        const result = await frappe.call({ method: `${method}.list_soc_documents`, args: { name: frm.doc.name } });
        const draft = (result.message || []).find((item) => !item.released);
        if (!draft) {
          frappe.msgprint(__("Generate a new PDF before releasing it."));
          return;
        }
        const dialog = new frappe.ui.Dialog({
          title: __("Release SOC PDF"),
          fields: [{ fieldname: "message", fieldtype: "Small Text", label: __("Reply to Partner"), default: __("Dokumen SOC telah selesai ditinjau dan dilampirkan pada tiket ini."), reqd: 1 }],
          primary_action_label: __("Attach and Reply"),
          primary_action: async (values) => {
            await frappe.call({
              method: `${method}.release_soc_document`,
              args: { document_name: draft.name, message: values.message },
              freeze: true,
              freeze_message: __("Attaching PDF and replying…"),
            });
            dialog.hide();
            frm.reload_doc();
          },
        });
        dialog.show();
      });
    }
    if (frm.doc.soc_status === "PDF Sent") {
      frm.add_custom_button(__("Complete"), () => move("Completed"));
    }
  },
});

