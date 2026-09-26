const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const entrance = new WeakMap();

export function cancelReveal(element) {
  entrance.get(element)?.cancel();
}

export function reveal(element, { slide = true, duration = 500 } = {}) {
  entrance.get(element)?.cancel();
  if (reducedMotion()) return;
  const animation = element.animate([
    { opacity: 0, transform: slide ? "translateY(24px)" : "none" },
    { opacity: 1, transform: "none" },
  ], { duration, easing: "cubic-bezier(0.22, 1, 0.36, 1)" });
  entrance.set(element, animation);
}

export function createSlogan(element) {
  const text = element.textContent;
  let timer;
  element.setAttribute("aria-label", text);
  element.style.minInlineSize = `${Array.from(text).length}em`;
  const letters = document.createElement("span");
  letters.setAttribute("aria-hidden", "true");
  element.replaceChildren(letters);

  function stop() {
    clearTimeout(timer);
    element.classList.remove("typing");
    letters.textContent = text;
  }

  function play() {
    stop();
    if (reducedMotion()) return;
    const characters = Array.from(text);
    let index = 0;
    letters.textContent = "";
    element.classList.add("typing");
    const next = () => {
      letters.textContent += characters[index++];
      if (index < characters.length) timer = setTimeout(next, 70);
      else element.classList.remove("typing");
    };
    timer = setTimeout(next, 160);
  }

  return { play, stop };
}

export function openModal(element) {
  const wasHidden = element.hidden;
  element.hidden = false;
  if (!wasHidden) return;
  reveal(element, { slide: false, duration: 200 });
  reveal(element.querySelector(".modal-box"), { duration: 400 });
}
