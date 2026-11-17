document.querySelectorAll(".alert").forEach((alert) => {
  window.setTimeout(() => alert.classList.add("fade"), 4500);
});
