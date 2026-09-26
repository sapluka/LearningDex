export function createTaskSidebar(container, api, openTask) {
  let activeId = "";
  let revision = 0;

  function setActive(id) {
    activeId = id;
    for (const button of container.querySelectorAll("button[data-task-id]")) {
      if (button.dataset.taskId === id) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    }
  }

  async function refresh() {
    const request = ++revision;
    try {
      const result = await api.list_tasks();
      if (request !== revision) return;
      if (!result.ok) throw new Error(result.error || "加载失败");
      container.replaceChildren();
      for (const task of result.tasks || []) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "sidebar-task";
        button.dataset.taskId = task.id;
        button.title = task.title || task.id;
        button.disabled = !task.has_doc;
        const icon = document.createElement("img");
        icon.className = "icon";
        icon.src = "icons/file-24.svg";
        icon.alt = "";
        const text = document.createElement("span");
        text.className = "sidebar-task-text";
        const title = document.createElement("span");
        title.className = "sidebar-task-title";
        title.textContent = button.title;
        const date = document.createElement("span");
        date.className = "sidebar-task-date";
        date.textContent = !task.has_doc ? "尚未生成文档" : task.mtime
          ? new Date(task.mtime * 1000).toLocaleDateString("zh-CN") : "已保存";
        text.append(title, date);
        button.append(icon, text);
        button.onclick = () => openTask(task.id);
        container.append(button);
      }
      if (!container.childElementCount) container.textContent = "暂无历史任务";
      setActive(activeId);
    } catch (error) {
      if (request !== revision) return;
      container.textContent = "历史任务加载失败";
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "btn ghost";
      retry.textContent = "重试";
      retry.onclick = refresh;
      container.append(retry);
    }
  }

  return { refresh, setActive };
}
