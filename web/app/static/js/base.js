"use strict";

document.addEventListener("DOMContentLoaded", () => {
  initMobileNavigation();
});

function initMobileNavigation() {
  const toggle = document.getElementById("mobile-menu-toggle");
  const menu = document.getElementById("mobile-menu");

  if (!toggle || !menu) {
    return;
  }

  toggle.setAttribute("aria-expanded", "false");

  toggle.addEventListener("click", () => {
    const isNowHidden = menu.classList.toggle("hidden");
    toggle.setAttribute("aria-expanded", String(!isNowHidden));
  });

  const links = menu.querySelectorAll("a");
  links.forEach((link) => {
    link.addEventListener("click", () => {
      if (!menu.classList.contains("hidden")) {
        menu.classList.add("hidden");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  });
}