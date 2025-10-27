(function clearRectsAndTags() {
  // Remove all overlay boxes
  document
    .querySelectorAll("[data-voyager-rect-index]")
    .forEach((el) => el.remove());

  // Remove the index attributes from real page elements
  document
    .querySelectorAll("[date-voyager-element-index]")
    .forEach((el) => el.removeAttribute("data-voyager-element-index"));
})();
