// Small conveniences on top of plain HTML forms.
// No texts live here: they come from data- attributes in the templates.

// <form data-confirm="..."> asks before submitting (used for deletes).
document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
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
