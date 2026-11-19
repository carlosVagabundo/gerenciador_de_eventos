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
})();