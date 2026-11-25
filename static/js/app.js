(function () {
  var root = document.documentElement;

  // ---------- Tema claro / escuro ----------
  var themeButtons = document.querySelectorAll(".theme-toggle");

  function syncThemeButtons() {
    var dark = root.getAttribute("data-theme") === "dark";
    themeButtons.forEach(function (btn) {
      btn.setAttribute("aria-pressed", dark ? "true" : "false");
      btn.setAttribute("aria-label", dark ? "Usar tema claro" : "Usar tema escuro");
    });
  }

  function setTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch (e) {}
    syncThemeButtons();
  }

  themeButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });
  });
  syncThemeButtons();

  // ---------- Menu no celular ----------
  var toggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("main-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    });
  }

  // ---------- Avisos somem sozinhos ----------
  document.querySelectorAll(".alert").forEach(function (alertBox) {
    setTimeout(function () { alertBox.classList.add("fade"); }, 6000);
    setTimeout(function () { alertBox.remove(); }, 6800);
  });

  // ---------- Menus "Calendário": fecham ao clicar fora ou apertar Esc ----------
  document.addEventListener("click", function (event) {
    document.querySelectorAll("details.menu[open]").forEach(function (menu) {
      if (!menu.contains(event.target)) { menu.removeAttribute("open"); }
    });
  });
  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") { return; }
    document.querySelectorAll("details.menu[open]").forEach(function (menu) {
      menu.removeAttribute("open");
      var summary = menu.querySelector("summary");
      if (summary) { summary.focus(); }
    });
  });

  // ---------- Caixa de confirmação no estilo do site ----------
  var modal = document.getElementById("confirm-modal");
  if (modal) {
    var iconEl = document.getElementById("confirm-icon");
    var titleEl = document.getElementById("confirm-title");
    var textEl = document.getElementById("confirm-text");
    var okBtn = document.getElementById("confirm-ok");
    var cancelBtn = document.getElementById("confirm-cancel");
    var pendingForm = null;
    var lastFocus = null;

    function openConfirm(form) {
      pendingForm = form;
      lastFocus = document.activeElement;
      iconEl.textContent = form.getAttribute("data-confirm-icon") || "⚠️";
      titleEl.textContent = form.getAttribute("data-confirm-title") || "Tem certeza?";
      textEl.textContent = form.getAttribute("data-confirm") || "";
      okBtn.textContent = form.getAttribute("data-confirm-button") || "Confirmar";
      cancelBtn.textContent = form.getAttribute("data-confirm-cancel") || "Cancelar";
      modal.hidden = false;
      document.body.classList.add("modal-open");
      cancelBtn.focus();                       // foco no botão mais seguro
    }

    function closeConfirm() {
      modal.hidden = true;
      document.body.classList.remove("modal-open");
      pendingForm = null;
      if (lastFocus && lastFocus.focus) { lastFocus.focus(); }
    }

    document.addEventListener("submit", function (event) {
      var form = event.target;
      if (form && form.hasAttribute && form.hasAttribute("data-confirm-title")) {
        event.preventDefault();
        openConfirm(form);
      }
    });

    okBtn.addEventListener("click", function () {
      var form = pendingForm;
      closeConfirm();
      if (form) { form.submit(); }
    });
    cancelBtn.addEventListener("click", closeConfirm);
    modal.addEventListener("click", function (event) {
      if (event.target === modal) { closeConfirm(); }
    });
    document.addEventListener("keydown", function (event) {
      if (modal.hidden) { return; }
      if (event.key === "Escape") { closeConfirm(); }
      if (event.key === "Tab") {               // mantém o foco dentro da caixa
        event.preventDefault();
        (document.activeElement === cancelBtn ? okBtn : cancelBtn).focus();
      }
    });
  }

  // ---------- Evita envio duplo: depois do 1º envio, os botões do formulário ficam desativados ----------
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (event.defaultPrevented || !form || !form.querySelectorAll) { return; }   // ex.: a caixa de confirmação cancelou
    form.querySelectorAll("button:not([type=button])").forEach(function (btn) {
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
    });
  });
  window.addEventListener("pageshow", function (event) {                         // voltar com o botão do navegador
    if (!event.persisted) { return; }
    document.querySelectorAll("button[aria-busy=true]").forEach(function (btn) {
      btn.disabled = false;
      btn.removeAttribute("aria-busy");
    });
  });
})();
