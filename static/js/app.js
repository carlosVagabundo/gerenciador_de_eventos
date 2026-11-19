(function () {
  var root = document.documentElement;

  // Tema claro / escuro
  function setTheme(theme) {
    root.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch (e) {}
  }
  document.querySelectorAll(".theme-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });
  });

  // Menu no celular
  var toggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("main-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Avisos somem sozinhos
  document.querySelectorAll(".alert").forEach(function (alertBox) {
    setTimeout(function () { alertBox.classList.add("fade"); }, 4500);
    setTimeout(function () { alertBox.remove(); }, 5200);
  });

  // Caixa de confirmação no estilo do site (formulários com data-confirm-title)
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
      cancelBtn.focus();
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
      if (event.key === "Tab") {
        event.preventDefault();
        (document.activeElement === cancelBtn ? okBtn : cancelBtn).focus();
      }
    });
  }
})();