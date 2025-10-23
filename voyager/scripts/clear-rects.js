(function clearRects() {
  document
    .querySelectorAll("[data-voyager-rect-index]")
    .forEach((el) => el.remove());
})();
