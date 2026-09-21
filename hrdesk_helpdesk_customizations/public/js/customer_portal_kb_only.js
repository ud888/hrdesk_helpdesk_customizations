(function customerPortalKnowledgeBaseOnly() {
  "use strict";

  const script = document.currentScript;
  if (!script) return;

  const ticketingEnabled = script.dataset.ticketingEnabled === "true";
  const isCustomerPortalUser =
    script.dataset.customerPortalUser === "true";
  if (ticketingEnabled || !isCustomerPortalUser) return;

  const knowledgeBasePath = "/helpdesk/kb-public";
  const customerTicketPrefix = "/helpdesk/my-tickets";
  const hiddenAttribute = "data-hrdesk-kb-only-hidden";
  const ticketLabels = new Set([
    "tickets",
    "my tickets",
    "new ticket",
    "create ticket",
    "tiket",
    "tiket saya",
    "buat tiket",
  ]);

  function pathFrom(url) {
    if (url === undefined || url === null || url === "") {
      return window.location.pathname;
    }
    try {
      return new URL(String(url), window.location.origin).pathname;
    } catch (_error) {
      return "";
    }
  }

  function isBlockedPath(path) {
    return path === "/helpdesk" || path === "/helpdesk/" ||
      path.startsWith(customerTicketPrefix);
  }

  function enforceCurrentRoute() {
    if (isBlockedPath(window.location.pathname)) {
      window.location.replace(knowledgeBasePath);
    }
  }

  const originalPushState = window.history.pushState.bind(window.history);
  const originalReplaceState = window.history.replaceState.bind(window.history);
  window.history.pushState = function pushState(state, unused, url) {
    if (isBlockedPath(pathFrom(url))) {
      window.location.assign(knowledgeBasePath);
      return undefined;
    }
    return originalPushState(state, unused, url);
  };
  window.history.replaceState = function replaceState(state, unused, url) {
    if (isBlockedPath(pathFrom(url))) {
      window.location.replace(knowledgeBasePath);
      return undefined;
    }
    return originalReplaceState(state, unused, url);
  };

  function hide(element) {
    if (!element || element.hasAttribute(hiddenAttribute)) return;
    element.setAttribute(hiddenAttribute, "true");
    element.setAttribute("aria-hidden", "true");
    element.style.setProperty("display", "none", "important");
  }

  function hideTicketControls(root) {
    const scope = root && root.querySelectorAll ? root : document;

    scope.querySelectorAll("a[href]").forEach((link) => {
      if (!pathFrom(link.getAttribute("href")).startsWith(customerTicketPrefix)) {
        return;
      }
      const parentText = (link.parentElement?.textContent || "").toLowerCase();
      if (parentText.includes("ticket") || parentText.includes("tiket")) {
        hide(link.parentElement);
      } else {
        hide(link);
      }
    });

    scope
      .querySelectorAll("nav button, nav [role='button'], aside button, aside [role='button']")
      .forEach((control) => {
        const label = (control.textContent || "").trim().toLowerCase();
        if (ticketLabels.has(label)) hide(control);
      });
  }

  document.documentElement.dataset.hrdeskCustomerPortalMode = "kb-only";
  hideTicketControls(document);

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === Node.ELEMENT_NODE) hideTicketControls(node);
      });
    });
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  document.addEventListener(
    "click",
    (event) => {
      const link = event.target.closest?.("a[href]");
      if (link && pathFrom(link.getAttribute("href")).startsWith(customerTicketPrefix)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        window.location.assign(knowledgeBasePath);
      }
    },
    true
  );

  window.addEventListener("popstate", enforceCurrentRoute);
  enforceCurrentRoute();
})();
