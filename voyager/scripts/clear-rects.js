(function clearRects() {
  // Remove all overlay boxes
  document
    .querySelectorAll("[data-voyager-rect-index]")
    .forEach((el) => el.remove());
})();
