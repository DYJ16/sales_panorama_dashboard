const slides = Array.from(document.querySelectorAll(".slide"));
const progress = document.querySelector(".progress span");
const current = document.querySelector(".current");
const panel = document.querySelector(".index-panel");
const toggle = document.querySelector(".index-toggle");

function activeIndex() {
  const middle = window.scrollY + window.innerHeight * 0.5;
  let active = 0;
  slides.forEach((slide, index) => {
    if (slide.offsetTop <= middle) active = index;
  });
  return active;
}

function update() {
  const index = activeIndex();
  progress.style.width = `${((index + 1) / slides.length) * 100}%`;
  current.textContent = String(index + 1).padStart(2, "0");
  slides.forEach((slide, i) => slide.classList.toggle("is-active", i === index));
  document.querySelectorAll(".index-panel button").forEach((button, i) => {
    button.classList.toggle("is-current", i === index);
  });
}

function goTo(index) {
  const next = Math.max(0, Math.min(slides.length - 1, index));
  slides[next].scrollIntoView({ behavior: "smooth", block: "start" });
}

toggle.addEventListener("click", () => document.body.classList.toggle("index-open"));
panel.addEventListener("click", event => {
  const button = event.target.closest("button[data-target]");
  if (!button) return;
  document.body.classList.remove("index-open");
  document.getElementById(button.dataset.target)?.scrollIntoView({ behavior: "smooth", block: "start" });
});

document.addEventListener("keydown", event => {
  const index = activeIndex();
  if (["ArrowDown", "ArrowRight", "PageDown", " "].includes(event.key)) {
    event.preventDefault();
    goTo(index + 1);
  }
  if (["ArrowUp", "ArrowLeft", "PageUp"].includes(event.key)) {
    event.preventDefault();
    goTo(index - 1);
  }
  if (event.key === "Escape") document.body.classList.remove("index-open");
});

window.addEventListener("scroll", update, { passive: true });
window.addEventListener("resize", update);
update();
