document.addEventListener("DOMContentLoaded", () => {
  const accordionItems = Array.from(document.querySelectorAll(".accordion-item"));
  const triggers = Array.from(document.querySelectorAll(".accordion-trigger"));
  const bodySection = document.body.dataset.activeSection;

  const openSection = (sectionKey) => {
    accordionItems.forEach((item) => {
      const isTarget = item.querySelector(".accordion-trigger")?.dataset.section === sectionKey;
      item.classList.toggle("is-open", isTarget);
    });
  };

  // Abrir sección inicial si se indicó desde el contexto
  if (bodySection) {
    openSection(bodySection);
  } else if (accordionItems.length > 0) {
    accordionItems[0].classList.add("is-open");
  }

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const section = trigger.dataset.section;
      const parent = trigger.closest(".accordion-item");
      const isAlreadyOpen = parent?.classList.contains("is-open");

      accordionItems.forEach((item) => item.classList.remove("is-open"));

      if (!isAlreadyOpen) {
        parent?.classList.add("is-open");
      }
    });
  });
});
