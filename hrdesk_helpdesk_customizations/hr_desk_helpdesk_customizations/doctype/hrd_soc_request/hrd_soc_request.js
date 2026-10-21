frappe.ui.form.on("HRD SOC Request", {
  refresh(frm) {
    if (frm.is_new()) return;
    const method = "hrdesk_helpdesk_customizations.api.partner_portal";
    const roles = new Set(frappe.user_roles || []);
    const isAdministrator = frappe.session.user === "Administrator";
    const canHDS = isAdministrator || roles.has("HR Desk Commercial");
    const canHDT = canHDS || roles.has("HR Desk Technical");
    const invoke = async (action, args = {}, message = __("Processing…")) => {
      await frappe.call({ method: `${method}.${action}`, args: { name: frm.doc.name, ...args }, freeze: true, freeze_message: message });
      await frm.reload_doc();
    };
    const promptReason = (title, action, label = __("Reason")) => frappe.prompt(
      [{ fieldname: "reason", fieldtype: "Small Text", label, reqd: 1 }],
      (values) => invoke(action, { reason: values.reason }),
      title,
    );
    const generate = async () => {
      const result = await frappe.call({ method: `${method}.generate_soc_documents`, args: { name: frm.doc.name }, freeze: true, freeze_message: __("Generating Partner SOC and End Customer SAC…") });
      (result.message?.documents || []).forEach((document) => window.open(document.download_url, "_blank", "noopener"));
      await frm.reload_doc();
    };
    const publish = () => frappe.prompt(
      [{ fieldname: "message", fieldtype: "Small Text", label: __("Reply to Partner"), default: __("Partner SOC dan End Customer SAC telah tersedia untuk ditandatangani."), reqd: 1 }],
      (values) => invoke("publish_soc_documents", { message: values.message }, __("Publishing SOC and SAC…")),
      __("Publish SOC and SAC"),
    );

    if (canHDS && ["SOC Requested", "SOC Published"].includes(frm.doc.soc_status)) {
      frm.add_custom_button(__("Generate SOC & SAC"), generate);
      frm.add_custom_button(__("Publish SOC & SAC"), publish);
    }
    if (canHDS && ["SOC Published", "SOC Signed"].includes(frm.doc.soc_status)) {
      frm.add_custom_button(__("Reopen for Amendment"), () => promptReason(__("Reopen for Amendment"), "reopen_for_amendment", __("Amendment Reason")));
    }
    if (canHDS && frm.doc.soc_status === "SOC Signed") {
      frm.add_custom_button(__("Reject Signed Documents"), () => promptReason(__("Reject Signed Documents"), "reject_signed_documents", __("Rejection Reason")));
      frm.add_custom_button(__("Approve Workspace Creation"), () => frappe.prompt(
        [{ fieldname: "acceptance_confirmed", fieldtype: "Check", label: __("I confirm all required signatures are complete, legible, and match the published document version"), reqd: 1 }],
        (values) => invoke("approve_workspace_creation", { acceptance_confirmed: values.acceptance_confirmed }),
        __("Confirm Signed Documents"),
      ));
    }
    if (canHDS && frm.doc.cancellation_reason && !["Workspace Created", "Cancelled"].includes(frm.doc.soc_status)) {
      frm.add_custom_button(__("Approve Cancellation"), () => invoke("approve_cancellation"));
    }
    if (canHDT && frm.doc.soc_status === "Workspace Creation") {
      frm.add_custom_button(__("Record Provisioning Failure"), () => frappe.prompt(
        [{ fieldname: "error_summary", fieldtype: "Small Text", label: __("Non-secret Error Summary"), reqd: 1 }],
        (values) => invoke("record_provisioning_failure", values),
        __("Record Provisioning Failure"),
      ));
      frm.add_custom_button(__("Complete Workspace"), () => {
        const dialog = new frappe.ui.Dialog({
          title: __("Complete Workspace and Create Protected Handoff"),
          fields: [
            { fieldname: "workspace_reference", fieldtype: "Data", label: __("Workspace URL / Reference"), reqd: 1 },
            { fieldname: "access_username", fieldtype: "Data", label: __("Access Username"), reqd: 1 },
            { fieldname: "access_secret", fieldtype: "Password", label: __("Temporary Access Secret"), reqd: 1 },
            { fieldname: "instructions", fieldtype: "Small Text", label: __("Access Instructions") },
          ],
          primary_action_label: __("Complete Workspace"),
          primary_action: async (values) => { await invoke("complete_workspace", values, __("Creating protected handoff…")); dialog.hide(); },
        });
        dialog.show();
      });
    }
  },
});

