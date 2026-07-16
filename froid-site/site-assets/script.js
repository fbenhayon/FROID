// FROID site — comportamento das seções "Só para Nerds"
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".nerds-toggle").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var targetId = btn.getAttribute("data-target");
      var panel = document.getElementById(targetId);
      if (!panel) return;
      var isOpen = panel.classList.contains("open");
      panel.classList.toggle("open", !isOpen);
      btn.setAttribute("aria-expanded", String(!isOpen));
      btn.textContent = isOpen
        ? btn.getAttribute("data-label-closed") || "Só para Nerds"
        : btn.getAttribute("data-label-open") || "Fechar detalhes técnicos";
    });
  });

  // Fecha o painel ao clicar fora dele
  document.addEventListener("click", function (e) {
    document.querySelectorAll(".nerds-panel.open").forEach(function (panel) {
      var wrapper = panel.closest(".nerds-wrapper");
      if (wrapper && !wrapper.contains(e.target)) {
        panel.classList.remove("open");
        var btn = wrapper.querySelector(".nerds-toggle");
        if (btn) {
          btn.setAttribute("aria-expanded", "false");
          btn.textContent = btn.getAttribute("data-label-closed") || "Só para Nerds";
        }
      }
    });
  });
});
