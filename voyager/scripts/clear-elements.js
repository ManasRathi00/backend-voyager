(function clearElements() {
  // clear all element tags
  document
    .querySelectorAll("[data-voyager-element-index]")
    .forEach((el) => el.removeAttribute("data-voyager-element-index"));
})();
