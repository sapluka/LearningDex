export function renderTaskCards(container, tasks, { open, remove }) {
  container.replaceChildren();
  for (const task of tasks) {
    const card = document.createElement("div");
    card.className = "task-item";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "task-open";
    button.disabled = task.has_doc === false;
    const icon = document.createElement("img");
    icon.src = "icons/file-24.svg";
    icon.className = "icon";
    icon.alt = "";
    const info = document.createElement("span");
    info.className = "task-info";
    const title = document.createElement("span");
    title.className = "t-id";
    title.textContent = task.title || task.id;
    const subtitle = document.createElement("span");
    subtitle.className = "t-sub";
    subtitle.textContent = task.id + (task.mtime ? " · " + new Date(task.mtime * 1000).toLocaleString("zh-CN") : "");
    info.append(title, subtitle);
    button.append(icon, info);
    button.onclick = () => open(task.id);
    card.append(button);
    if (remove) {
      const deletion = document.createElement("button");
      deletion.type = "button";
      deletion.className = "task-delete";
      deletion.textContent = "删除";
      deletion.setAttribute("aria-label", "删除 " + (task.title || task.id));
      deletion.onclick = () => remove(task.id);
      card.append(deletion);
    }
    container.append(card);
  }
}
