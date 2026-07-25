// FROID site — comportamento das seções "Só para Nerds"
document.addEventListener("DOMContentLoaded", function () {
  // Destaca no header o link da página atual (itálico + sublinhado via CSS .ativo)
  var pagina = (location.pathname.split("/").pop() || "index.html").toLowerCase();
  document.querySelectorAll(".nav-links a").forEach(function (a) {
    var href = (a.getAttribute("href") || "").toLowerCase();
    if (href === pagina) a.classList.add("ativo");
  });

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

  // ---------- Lightbox: amplia as fotos (.site-img) ao clicar ----------
  (function () {
    var imgs = document.querySelectorAll("img.site-img, .gallery figure img");
    if (!imgs.length) return;

    var closeLabels = { pt: "Fechar", en: "Close", es: "Cerrar", fr: "Fermer" };
    var lang = (document.documentElement.getAttribute("lang") || "pt")
      .slice(0, 2)
      .toLowerCase();
    var closeLabel = closeLabels[lang] || "Fechar";

    var overlay = document.createElement("div");
    overlay.className = "lightbox-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML =
      '<button class="lightbox-close" type="button" aria-label="' +
      closeLabel +
      '">&times;</button>' +
      '<figure class="lightbox-figure">' +
      '<img class="lightbox-img" src="" alt="" />' +
      '<figcaption class="lightbox-caption"></figcaption>' +
      "</figure>";
    document.body.appendChild(overlay);

    var lbImg = overlay.querySelector(".lightbox-img");
    var lbCaption = overlay.querySelector(".lightbox-caption");
    var lastFocus = null;

    function openLightbox(src, alt) {
      lastFocus = document.activeElement;
      lbImg.setAttribute("src", src);
      lbImg.setAttribute("alt", alt || "");
      lbCaption.textContent = alt || "";
      lbCaption.style.display = alt ? "" : "none";
      overlay.classList.add("open");
      overlay.setAttribute("aria-hidden", "false");
      document.body.classList.add("lightbox-lock");
      overlay.querySelector(".lightbox-close").focus();
    }

    function closeLightbox() {
      overlay.classList.remove("open");
      overlay.setAttribute("aria-hidden", "true");
      document.body.classList.remove("lightbox-lock");
      lbImg.setAttribute("src", "");
      if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
    }

    imgs.forEach(function (img) {
      img.classList.add("zoomable");
      img.setAttribute("tabindex", "0");
      img.setAttribute("role", "button");
      img.addEventListener("click", function () {
        openLightbox(img.currentSrc || img.src, img.getAttribute("alt"));
      });
      img.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openLightbox(img.currentSrc || img.src, img.getAttribute("alt"));
        }
      });
    });

    // Clicar em qualquer ponto do overlay (fundo, imagem ou botão) fecha
    overlay.addEventListener("click", closeLightbox);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && overlay.classList.contains("open")) closeLightbox();
    });
  })();
});
