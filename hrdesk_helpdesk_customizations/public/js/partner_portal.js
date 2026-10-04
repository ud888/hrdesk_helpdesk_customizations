(() => {
  "use strict";

  const call = async (method, args = {}) => {
    const body = new URLSearchParams();
    Object.entries(args).forEach(([key, value]) => body.set(key, typeof value === "string" ? value : JSON.stringify(value)));
    const response = await fetch(`/api/method/${method}`, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded", "X-Frappe-CSRF-Token": window.frappe?.csrf_token || "" },
      body,
    });
    const payload = await response.json();
    if (!response.ok || payload.exception) throw new Error(payload.message || "Permintaan tidak dapat diproses.");
    return payload.message;
  };

  const empty = (element) => { while (element?.firstChild) element.firstChild.remove(); };
  const text = (value) => document.createTextNode(value == null ? "" : String(value));
  const api = "hrdesk_helpdesk_customizations.api.partner_portal";

  const upload = async (files) => {
    const names = [];
    for (const file of files) {
      const form = new FormData(); form.append("file", file); form.append("is_private", "1");
      const response = await fetch("/api/method/upload_file", { method: "POST", credentials: "same-origin", headers: { "X-Frappe-CSRF-Token": window.frappe?.csrf_token || "" }, body: form });
      const payload = await response.json();
      if (!response.ok || !payload.message?.name) throw new Error("Lampiran tidak dapat diunggah.");
      names.push(payload.message.name);
    }
    return names;
  };

  const articleCard = (article) => {
    const card = document.createElement("article");
    const heading = document.createElement("h3"); heading.append(text(article.title || article.subject));
    const summary = document.createElement("p"); summary.append(text(article.content || article.description || ""));
    const link = document.createElement("a"); link.href = `/helpdesk/kb-public/articles/${article.name}`; link.append(text("Baca artikel"));
    card.append(heading, summary, link); return card;
  };

  const loadKnowledge = async (query = "") => {
    const target = document.querySelector("#hrd-kb-results"); empty(target);
    if (query.length >= 3) {
      const rows = await call("hrdesk_helpdesk_customizations.overrides.knowledge_base.search", { query });
      rows.forEach((row) => target.append(articleCard(row)));
      if (!rows.length) target.append(text("Tidak ada artikel yang sesuai."));
      return;
    }
    const categories = await call("hrdesk_helpdesk_customizations.overrides.knowledge_base.get_categories");
    for (const category of categories) {
      const heading = document.createElement("article");
      const title = document.createElement("h3"); title.append(text(category.category_name)); heading.append(title); target.append(heading);
      const articles = await call("hrdesk_helpdesk_customizations.overrides.knowledge_base.get_category_articles", { category: category.name });
      articles.forEach((article) => target.append(articleCard(article)));
    }
  };

  const loadCustomers = async () => {
    const select = document.querySelector('#hrd-soc-form [name="relevant_customer"]');
    const rows = await call(`${api}.customer_options`);
    rows.forEach((row) => select.add(new Option(row.customer_name || row.name, row.name)));
  };

  const loadRequests = async (scope = "mine") => {
    const target = document.querySelector("#hrd-requests"); empty(target);
    const rows = await call(`${api}.list_soc_requests`, { scope });
    if (!rows.length) { target.append(text("Belum ada permintaan SOC.")); return; }
    rows.forEach((row) => {
      const card = document.createElement("article");
      const heading = document.createElement("h3"); heading.append(text(`#${row.name} — ${row.subject}`));
      const status = document.createElement("p"); status.append(text(`Status: ${row.status}`));
      const open = document.createElement("button"); open.type = "button"; open.append(text("Buka permintaan")); open.addEventListener("click", () => loadRequest(row.name));
      card.append(heading, status, open); target.append(card);
    });
  };

  const fileList = (files) => {
    const list = document.createElement("ul");
    (files || []).forEach((file) => { const item = document.createElement("li"); const link = document.createElement("a"); link.href = file.download_url; link.append(text(file.file_name)); item.append(link); list.append(item); });
    return list;
  };

  const loadRequest = async (name) => {
    const target = document.querySelector("#hrd-request-detail"); empty(target);
    const request = await call(`${api}.get_soc_request`, { name });
    const heading = document.createElement("h2"); heading.append(text(`#${request.name} — ${request.subject}`));
    const body = document.createElement("div"); body.innerHTML = request.description || "";
    const thread = document.createElement("div");
    (request.replies || []).forEach((reply) => { const section = document.createElement("section"); const meta = document.createElement("strong"); meta.append(text(`${reply.sender || "HR Desk"} · ${reply.communication_date || ""}`)); const content = document.createElement("div"); content.innerHTML = reply.content || ""; section.append(meta, content, fileList(reply.attachments)); thread.append(section); });
    const form = document.createElement("form"); const message = document.createElement("textarea"); message.required = true; message.rows = 4; message.placeholder = "Tulis balasan"; const files = document.createElement("input"); files.type = "file"; files.multiple = true; const send = document.createElement("button"); send.type = "submit"; send.className = "hrd-primary"; send.append(text("Kirim Balasan")); const status = document.createElement("p"); status.setAttribute("role", "status"); form.append(message, files, send, status);
    form.addEventListener("submit", async (event) => { event.preventDefault(); status.textContent = "Mengirim…"; try { const attachments = await upload(files.files); await call(`${api}.reply`, { name, message: message.value, attachments }); await loadRequest(name); } catch (error) { status.textContent = error.message; } });
    target.append(heading, body, fileList(request.attachments), thread, form); target.hidden = false; target.scrollIntoView({ behavior: "smooth" });
  };

  const form = document.querySelector("#hrd-soc-form");
  form?.addEventListener("submit", async (event) => {
    event.preventDefault(); const status = document.querySelector("#hrd-form-status"); status.textContent = "Mengirim…";
    try { const values = new FormData(form); const attachments = await upload(form.elements.attachments.files); const result = await call(`${api}.create_soc_request`, { data: { subject: values.get("subject"), description: values.get("description"), relevant_customer: values.get("relevant_customer") }, attachments }); status.textContent = `Permintaan #${result.name} berhasil dibuat.`; form.reset(); await loadRequests(); } catch (error) { status.textContent = error.message; }
  });

  document.querySelectorAll("[data-scope]").forEach((button) => button.addEventListener("click", () => loadRequests(button.dataset.scope)));
  let searchTimer;
  document.querySelector("#hrd-kb-search")?.addEventListener("input", (event) => { clearTimeout(searchTimer); searchTimer = setTimeout(() => loadKnowledge(event.target.value.trim()), 300); });
  Promise.all([loadKnowledge(), loadCustomers(), loadRequests()]).catch((error) => console.error("Partner Portal:", error.message));
})();

