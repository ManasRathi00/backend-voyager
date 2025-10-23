(function clearRects() {
  console.log("Clearing Rects");
  document
    .querySelectorAll("[data-voyager-rect-index]")
    .forEach((el) => el.remove());
})();
