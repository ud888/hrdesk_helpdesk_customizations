(() => {
  "use strict";

  const form = document.querySelector("#hrd-soc-form");
  if (!form?.querySelector('[name="soc_type"]')) return;

  const api = "hrdesk_helpdesk_customizations.api.partner_portal";
  const state = { options: null, scope: "mine", request: null };
  const text = (value) => document.createTextNode(value == null ? "" : String(value));
  const empty = (element) => { while (element?.firstChild) element.firstChild.remove(); };
  const value = (name) => form.elements[name]?.value ?? "";
  const newRequestId = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  form.dataset.clientRequestId = newRequestId();

  const call = async (method, args = {}) => {
    const body = new URLSearchParams();
    Object.entries(args).forEach(([key, item]) => body.set(key, typeof item === "string" ? item : JSON.stringify(item)));
    const response = await fetch(`/api/method/${method}`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded", "X-Frappe-CSRF-Token": window.frappe?.csrf_token || "" }, body,
    });
    const payload = await response.json();
    if (!response.ok || payload.exception) throw new Error(payload.message || "Permintaan tidak dapat diproses.");
    return payload.message;
  };

  const upload = async (files) => {
    const names = [];
    for (const file of files || []) {
      const body = new FormData(); body.append("file", file); body.append("is_private", "1");
      const response = await fetch("/api/method/upload_file", { method: "POST", credentials: "same-origin", headers: { "X-Frappe-CSRF-Token": window.frappe?.csrf_token || "" }, body });
      const payload = await response.json();
      if (!response.ok || !payload.message?.name) throw new Error("Lampiran tidak dapat diunggah.");
      names.push(payload.message.name);
    }
    return names;
  };

  const option = (label, optionValue = label) => new Option(label, optionValue);
  const fillSelect = (name, rows, labelField, placeholder) => {
    const select = form.elements[name]; empty(select); select.add(option(placeholder, ""));
    rows.forEach((row) => select.add(option(row[labelField] || row.name, row.name)));
  };

  const renderAddOns = (rows) => {
    const target = document.querySelector("#hrd-add-ons"); empty(target);
    rows.forEach((row) => {
      const tr = document.createElement("tr"); tr.dataset.name = row.name;
      const choose = document.createElement("input"); choose.type = "checkbox"; choose.className = "hrd-add-on-check";
      const quantity = document.createElement("input"); quantity.type = "number"; quantity.min = "1"; quantity.value = "1"; quantity.disabled = true; quantity.className = "hrd-add-on-quantity";
      choose.addEventListener("change", () => { quantity.disabled = !choose.checked; if (choose.checked) quantity.focus(); });
      const c1 = document.createElement("td"); c1.append(choose);
      const c2 = document.createElement("td"); c2.append(text(row.add_on_name || row.name));
      const c3 = document.createElement("td"); c3.append(quantity); tr.append(c1, c2, c3); target.append(tr);
    });
  };

  const loadOptions = async () => {
    state.options = await call(`${api}.soc_form_options`);
    fillSelect("soc_type", state.options.soc_types.map((name) => ({ name })), "name", "Pilih SOC type");
    fillSelect("package_type", state.options.packages, "package_name", "Pilih package");
    fillSelect("payment_term", state.options.payment_terms, "term_name", "Pilih payment term");
    fillSelect("customer", state.options.customers, "customer_name", "Customer baru / belum terdaftar");
    form.elements.partner_display.value = state.options.partner;
    renderAddOns(state.options.add_ons);
    if (!state.options.packages.length) document.querySelector("#hrd-form-status").textContent = "Package belum dikonfigurasi oleh HR Desk.";
  };

  form.elements.customer.addEventListener("change", () => {
    const customer = state.options?.customers.find((item) => item.name === value("customer"));
    if (customer) form.elements.customer_company_name.value = customer.customer_name || customer.name;
  });

  const formData = () => ({
    client_request_id: form.dataset.clientRequestId,
    soc_type: value("soc_type"), customer: value("customer"), customer_company_name: value("customer_company_name").trim(),
    customer_address: value("customer_address").trim(), customer_pic_name: value("customer_pic_name").trim(), customer_pic_position: value("customer_pic_position").trim(),
    customer_pic_email: value("customer_pic_email").trim(), customer_pic_phone: value("customer_pic_phone").trim(), super_admin_email: value("super_admin_email").trim(),
    domain_workspace: value("domain_workspace").trim(), reseller_billing_contact_email: value("reseller_billing_contact_email").trim(), reseller_billing_contact_phone: value("reseller_billing_contact_phone").trim(),
    package_type: value("package_type"), payment_term: value("payment_term"), subscription_start_date: value("subscription_start_date"), subscription_end_date: value("subscription_end_date"), go_live_target_date: value("go_live_target_date"),
    estimated_employee_count: Number(value("estimated_employee_count") || 0), number_of_admin_users: Number(value("number_of_admin_users") || 0), number_of_payroll_groups: Number(value("number_of_payroll_groups") || 0),
    implementation_included: form.elements.implementation_included.checked ? 1 : 0, training_included: form.elements.training_included.checked ? 1 : 0,
    add_ons: [...document.querySelectorAll("#hrd-add-ons tr")].filter((row) => row.querySelector(".hrd-add-on-check").checked).map((row) => ({ add_on: row.dataset.name, quantity: Number(row.querySelector(".hrd-add-on-quantity").value || 0) })),
  });

  const resetForm = () => {
    form.reset(); form.dataset.editing = ""; form.dataset.clientRequestId = newRequestId();
    form.elements.partner_display.value = state.options?.partner || ""; renderAddOns(state.options?.add_ons || []);
    document.querySelector("#hrd-soc-form-title").textContent = "Create SOC Request";
    document.querySelector("#hrd-soc-submit").textContent = "Kirim Permintaan SOC";
    document.querySelector("#hrd-cancel-edit").hidden = true;
  };
  document.querySelector("#hrd-cancel-edit").addEventListener("click", resetForm);

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.querySelector("#hrd-form-status");
    if (value("subscription_start_date") && value("subscription_end_date") && value("subscription_end_date") < value("subscription_start_date")) {
      status.textContent = "Tanggal akhir subscription tidak boleh mendahului tanggal mulai."; return;
    }
    status.textContent = "Menyimpan…";
    try {
      const attachments = await upload(form.elements.attachments.files);
      const editing = form.dataset.editing;
      const result = editing
        ? await call(`${api}.update_soc_request`, { name: editing, data: formData(), attachments })
        : await call(`${api}.create_soc_request`, { data: formData(), attachments });
      status.textContent = editing ? `Revisi ${result.name} berhasil dikirim.` : `${result.name} berhasil dibuat dengan tiket #${result.ticket}.`;
      resetForm(); await loadRequests(); await loadRequest(result.name);
    } catch (error) { status.textContent = error.message; }
  });

  const formatDate = (item) => item ? new Intl.DateTimeFormat("id-ID", { dateStyle: "medium" }).format(new Date(`${String(item).slice(0, 10)}T00:00:00`)) : "-";
  const loadRequests = async () => {
    const target = document.querySelector("#hrd-requests"); empty(target);
    try {
      const rows = await call(`${api}.list_soc_requests`, { scope: state.scope, search: document.querySelector("#hrd-request-search").value.trim(), status: document.querySelector("#hrd-request-status").value });
      if (!rows.length) { const tr = document.createElement("tr"); const td = document.createElement("td"); td.colSpan = 9; td.append(text("Belum ada SOC Request.")); tr.append(td); target.append(tr); return; }
      rows.forEach((row) => {
        const tr = document.createElement("tr");
        [row.name, formatDate(row.submission_date), row.customer_company_name, row.package_type, `${formatDate(row.subscription_start_date)} – ${formatDate(row.subscription_end_date)}`, row.soc_status, row.ticket_status || "-", formatDate(row.modified)].forEach((item) => { const td = document.createElement("td"); td.append(text(item)); tr.append(td); });
        const action = document.createElement("td"); const button = document.createElement("button"); button.type = "button"; button.append(text("Buka")); button.addEventListener("click", () => loadRequest(row.name)); action.append(button); tr.append(action); target.append(tr);
      });
    } catch (error) { const tr = document.createElement("tr"); const td = document.createElement("td"); td.colSpan = 9; td.append(text(error.message)); tr.append(td); target.append(tr); }
  };

  const fileList = (files) => {
    const list = document.createElement("ul");
    (files || []).forEach((file) => { const li = document.createElement("li"); const link = document.createElement("a"); link.href = file.download_url; link.append(text(file.file_name || `SOC PDF v${file.version}`)); li.append(link); list.append(li); });
    return list;
  };

  const detailTable = (request) => {
    const dl = document.createElement("dl"); dl.className = "hrd-detail-grid";
    const rows = [["Partner", request.partner], ["Customer", request.customer_company_name], ["SOC Type", request.soc_type], ["Package", request.package_type], ["Subscription", request.subscription_period || "-"], ["Go-Live Target", formatDate(request.go_live_target_date)], ["SOC Status", request.soc_status], ["Ticket Status", request.ticket_status]];
    rows.forEach(([label, item]) => { const dt = document.createElement("dt"); dt.append(text(label)); const dd = document.createElement("dd"); dd.append(text(item)); dl.append(dt, dd); }); return dl;
  };

  const populateRevision = (request) => {
    for (const [key, item] of Object.entries(request)) if (form.elements[key] && !["attachments", "partner_display"].includes(key)) {
      if (form.elements[key].type === "checkbox") form.elements[key].checked = Boolean(item); else form.elements[key].value = item ?? "";
    }
    const selected = new Map((request.add_ons || []).map((item) => [item.add_on, item.quantity]));
    document.querySelectorAll("#hrd-add-ons tr").forEach((row) => { const check = row.querySelector(".hrd-add-on-check"); const quantity = row.querySelector(".hrd-add-on-quantity"); check.checked = selected.has(row.dataset.name); quantity.disabled = !check.checked; quantity.value = selected.get(row.dataset.name) || 1; });
    form.dataset.editing = request.name; document.querySelector("#hrd-soc-form-title").textContent = `Revisi ${request.name}`; document.querySelector("#hrd-soc-submit").textContent = "Kirim Revisi"; document.querySelector("#hrd-cancel-edit").hidden = false; document.querySelector("#submit").scrollIntoView({ behavior: "smooth" });
  };

  const loadRequest = async (name) => {
    const target = document.querySelector("#hrd-request-detail"); empty(target);
    try {
      const request = await call(`${api}.get_soc_request`, { name }); state.request = request;
      const heading = document.createElement("div"); heading.className = "hrd-section-heading"; const h2 = document.createElement("h2"); h2.append(text(`${request.name} — ${request.customer_company_name}`)); const ticket = document.createElement("a"); ticket.href = request.ticket_url; ticket.append(text(`Buka Helpdesk Ticket #${request.ticket}`)); heading.append(h2, ticket); target.append(heading, detailTable(request));
      if (request.revision_reason) { const notice = document.createElement("aside"); notice.className = "hrd-notice"; notice.append(text(`Revisi diminta: ${request.revision_reason}`)); target.append(notice); }
      const addOnTitle = document.createElement("h3"); addOnTitle.append(text("Module & Add-on")); const addOns = document.createElement("ul"); (request.add_ons || []).forEach((item) => { const li = document.createElement("li"); li.append(text(`${item.add_on}: ${item.quantity}`)); addOns.append(li); }); target.append(addOnTitle, addOns);
      const documentTitle = document.createElement("h3"); documentTitle.append(text("SOC Documents")); target.append(documentTitle, fileList(request.documents));
      if (request.can_edit) { const edit = document.createElement("button"); edit.type = "button"; edit.className = "hrd-primary"; edit.append(text("Perbarui Data Revisi")); edit.addEventListener("click", () => populateRevision(request)); target.append(edit); }
      const threadTitle = document.createElement("h3"); threadTitle.append(text("Ticket Conversation")); const thread = document.createElement("div"); thread.className = "hrd-thread";
      (request.replies || []).forEach((reply) => { const section = document.createElement("section"); const meta = document.createElement("strong"); meta.append(text(`${reply.sender || "HR Desk"} · ${reply.communication_date || ""}`)); const content = document.createElement("div"); content.innerHTML = reply.content || ""; section.append(meta, content, fileList(reply.attachments)); thread.append(section); }); target.append(threadTitle, thread);
      const replyForm = document.createElement("form"); replyForm.className = "hrd-reply"; const message = document.createElement("textarea"); message.required = true; message.rows = 4; message.placeholder = "Tulis balasan untuk HR Desk"; const attachments = document.createElement("input"); attachments.type = "file"; attachments.multiple = true; const send = document.createElement("button"); send.type = "submit"; send.className = "hrd-primary"; send.append(text("Kirim Balasan")); const replyStatus = document.createElement("p"); replyStatus.setAttribute("role", "status"); replyForm.append(message, attachments, send, replyStatus);
      replyForm.addEventListener("submit", async (event) => { event.preventDefault(); replyStatus.textContent = "Mengirim…"; try { const files = await upload(attachments.files); await call(`${api}.reply`, { name: request.name, message: message.value, attachments: files }); await loadRequest(request.name); } catch (error) { replyStatus.textContent = error.message; } }); target.append(replyForm); target.hidden = false; target.scrollIntoView({ behavior: "smooth" });
    } catch (error) { target.append(text(error.message)); target.hidden = false; }
  };

  document.querySelectorAll("[data-scope]").forEach((button) => button.addEventListener("click", () => { state.scope = button.dataset.scope; loadRequests(); }));
  let timer; document.querySelector("#hrd-request-search").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(loadRequests, 300); });
  document.querySelector("#hrd-request-status").addEventListener("change", loadRequests);
  Promise.all([loadOptions(), loadRequests()]).catch((error) => { document.querySelector("#hrd-form-status").textContent = error.message; });
})();

