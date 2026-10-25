// Small conveniences on top of plain HTML forms.
// No texts live here: they come from data- attributes in the templates.

// <form data-confirm="..."> asks before submitting (used for deletes). A submit button can have its
// own data-confirm, for a delete button inside an edit form.
document.addEventListener("submit", (event) => {
  const message = event.submitter?.dataset.confirm ?? event.target.dataset.confirm;
  if (message && !confirm(message)) {
    event.preventDefault();
  }
});

document.addEventListener("click", (event) => {
  // <button data-add-row="list-id" data-template="template-id"> appends a copy of the template.
  const add = event.target.closest("[data-add-row]");
  if (add) {
    const template = document.getElementById(add.dataset.template);
    const row = template.content.firstElementChild.cloneNode(true);
    document.getElementById(add.dataset.addRow).append(row);
    row.querySelector("input").focus();
    return;
  }

  // <button data-remove-row> inside a [data-row] removes that row.
  const remove = event.target.closest("[data-remove-row]");
  if (remove) {
    remove.closest("[data-row]").remove();
    return;
  }

  // <button data-print> opens the print dialog.
  if (event.target.closest("[data-print]")) {
    window.print();
  }
});

// <button data-drag-handle> inside a [data-row] drags that row up or down among its siblings, with the
// mouse or a finger; the form then sends the rows in their new order. Arrow up/down move it one place.
document.addEventListener("pointerdown", (event) => {
  const handle = event.target.closest("[data-drag-handle]");
  if (!handle || event.button !== 0) {
    return;
  }
  event.preventDefault();
  const row = handle.closest("[data-row]");
  const list = row.parentElement;
  const move = (e) => {
    // Put the row before the first other row whose middle is below the pointer, or last if there is none
    const before = [...list.children].find((other) => {
      const box = other.getBoundingClientRect();
      return other !== row && e.clientY < box.top + box.height / 2;
    }) ?? null;
    if (before !== row.nextElementSibling) {
      list.insertBefore(row, before);
    }
  };
  handle.setPointerCapture(event.pointerId);
  row.classList.add("dragging");
  handle.addEventListener("pointermove", move);
  handle.addEventListener("lostpointercapture", () => {
    row.classList.remove("dragging");
    handle.removeEventListener("pointermove", move);
  }, { once: true });
});

document.addEventListener("keydown", (event) => {
  const handle = event.target.closest("[data-drag-handle]");
  if (!handle || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) {
    return;
  }
  event.preventDefault();
  const row = handle.closest("[data-row]");
  if (event.key === "ArrowUp") {
    row.previousElementSibling?.before(row);
  } else {
    row.nextElementSibling?.after(row);
  }
  handle.focus();  // moving the row in the page drops the focus
});

// <form data-favourite> (the star on a recipe card) saves without reloading the page, then flips the star.
// If saving fails, the star stays as it was and data-favourite-error is shown.
document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (form.dataset.favourite === undefined || event.defaultPrevented) {
    return;
  }
  event.preventDefault();
  const button = form.querySelector("button[name=favourite]");
  if (button.disabled) {
    return;
  }
  const on = button.value === "1";
  button.disabled = true;
  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new URLSearchParams({ favourite: button.value }),
      headers: { "X-Requested-With": "fetch" },
    });
    if (!response.ok) {
      throw new Error(response.status);
    }
  } catch {
    alert(form.dataset.favouriteError);
    return;
  } finally {
    button.disabled = false;
  }
  const label = on ? button.dataset.labelOn : button.dataset.labelOff;
  button.value = on ? "0" : "1";
  button.classList.toggle("is-favourite", on);
  button.querySelector("svg").classList.toggle("filled", on);
  button.setAttribute("aria-pressed", on);
  button.title = label;
  button.setAttribute("aria-label", label);
});

// <select data-auto-submit> submits its form as soon as another option is chosen (items per page).
document.addEventListener("change", (event) => {
  if (event.target.dataset.autoSubmit !== undefined) {
    event.target.form.requestSubmit();
  }
});

// <input type="checkbox" data-toggle-url="..."> saves its tick without reloading the page.
// If saving fails, the tick is undone and the message from the nearest [data-toggle-error] is shown.
document.addEventListener("change", async (event) => {
  const box = event.target;
  const url = box.dataset.toggleUrl;
  if (!url) {
    return;
  }
  const body = new URLSearchParams({ checked: box.checked ? "1" : "0" });
  try {
    const response = await fetch(url, { method: "POST", body });
    if (!response.ok) {
      throw new Error(response.status);
    }
  } catch {
    box.checked = !box.checked;
    alert(box.closest("[data-toggle-error]").dataset.toggleError);
  }
});
