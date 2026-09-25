export function initPanelDivider(onResize = () => {}) {
  const divider = document.getElementById("panelDivider");
  const center = document.querySelector(".center");
  const app = document.querySelector(".app");
  const sidebar = document.querySelector(".sidebar");
  const available = () => app.clientWidth - sidebar.offsetWidth - divider.offsetWidth;
  let share = Number(localStorage.getItem("editorShare")) || 0.5;

  function apply(next) {
    const space = available();
    if (space <= 0) return;
    const minCenter = Math.min(340, space * 0.4);
    const minChat = Math.min(280, space * 0.4);
    const width = Math.max(minCenter, Math.min(space - minChat, space * next));
    share = width / space;
    center.style.flexBasis = `${width}px`;
    onResize();
  }

  apply(share);
  divider.addEventListener("pointerdown", (event) => {
    divider.setPointerCapture(event.pointerId);
    divider.classList.add("dragging");
    event.preventDefault();
  });
  divider.addEventListener("pointermove", (event) => {
    if (divider.hasPointerCapture(event.pointerId)) {
      apply((event.clientX - sidebar.offsetWidth) / available());
    }
  });
  function finish(event) {
    if (!divider.hasPointerCapture(event.pointerId)) return;
    divider.releasePointerCapture(event.pointerId);
    divider.classList.remove("dragging");
    localStorage.setItem("editorShare", String(share));
  }
  divider.addEventListener("pointerup", finish);
  divider.addEventListener("pointercancel", finish);
  divider.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    apply(share + (event.key === "ArrowRight" ? 0.03 : -0.03));
    localStorage.setItem("editorShare", String(share));
    event.preventDefault();
  });
  window.addEventListener("resize", () => apply(share));
}
