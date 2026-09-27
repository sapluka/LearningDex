export async function initWindowChrome(api, onError) {
  const bar = document.getElementById("windowTitlebar");
  const maximize = document.getElementById("windowMaximize");
  const setState = (state) => {
    bar.hidden = !state.custom_titlebar;
    maximize.setAttribute("aria-label", state.maximized ? "还原" : "最大化");
    maximize.title = state.maximized ? "还原" : "最大化";
    maximize.classList.toggle("is-maximized", state.maximized);
  };
  window.__setWindowState = setState;
  const act = async (action) => {
    try {
      const result = await api.control_window(action);
      if (!result.ok) throw new Error(result.error || "操作失败");
      if (action !== "close") setState(result);
    } catch (error) { onError("窗口操作失败：" + error.message); }
  };
  for (const button of bar.querySelectorAll("button[data-window-action]")) {
    button.addEventListener("click", () => act(button.dataset.windowAction));
  }
  bar.addEventListener("dblclick", (event) => {
    if (!event.target.closest("button")) act("toggle_maximize");
  });
  let dragStart = null;
  bar.addEventListener("pointerdown", (event) => {
    if (event.button === 0 && !event.target.closest("button")) {
      dragStart = {x: event.screenX, y: event.screenY};
    }
  });
  window.addEventListener("pointermove", (event) => {
    if (!dragStart) return;
    if (!(event.buttons & 1)) { dragStart = null; return; }
    if (Math.hypot(event.screenX - dragStart.x, event.screenY - dragStart.y) >= 4) {
      dragStart = null;
      act("drag");
    }
  });
  window.addEventListener("pointerup", () => { dragStart = null; });
  window.addEventListener("blur", () => { dragStart = null; });
  if (typeof api.get_window_state === "function") setState(await api.get_window_state());
}
