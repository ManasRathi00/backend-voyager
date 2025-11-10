(function () {
  const MAX_ELEMENTS = 60;
  const MIN_AREA = 20;
  const LABEL_FONT_SIZE = 16;
  const LABEL_PADDING = 3;

  function markPage() {
    const vw = Math.max(
      document.documentElement.clientWidth || 0,
      window.innerWidth || 0
    );
    const vh = Math.max(
      document.documentElement.clientHeight || 0,
      window.innerHeight || 0
    );

    // Get all interactive elements
    let items = Array.from(document.querySelectorAll("*"))
      .map((element) => {
        // Check if element is interactive
        const isInteractive =
          element.tagName === "INPUT" ||
          element.tagName === "TEXTAREA" ||
          element.tagName === "SELECT" ||
          element.tagName === "BUTTON" ||
          element.tagName === "A" ||
          element.tagName === "IFRAME" ||
          element.tagName === "VIDEO" ||
          (element.hasAttribute("role") &&
            ["button", "link", "checkbox", "menuitem", "tab"].includes(
              element.getAttribute("role")
            ));

        if (!isInteractive) return null;

        // Get visible rectangles
        const rects = Array.from(element.getClientRects())
          .filter((bb) => {
            const center_x = bb.left + bb.width / 2;
            const center_y = bb.top + bb.height / 2;
            const elAtCenter = document.elementFromPoint(center_x, center_y);
            return elAtCenter === element || element.contains(elAtCenter);
          })
          .map((bb) => ({
            left: Math.max(0, bb.left),
            top: Math.max(0, bb.top),
            right: Math.min(vw, bb.right),
            bottom: Math.min(vh, bb.bottom),
          }))
          .map((rect) => ({
            ...rect,
            width: rect.right - rect.left,
            height: rect.bottom - rect.top,
          }))
          .filter((rect) => rect.width > 0 && rect.height > 0);

        if (rects.length === 0) return null;

        const area = rects.reduce(
          (acc, rect) => acc + rect.width * rect.height,
          0
        );

        if (area < MIN_AREA) return null;

        return {
          element,
          rects,
          area,
          text: element.textContent
            .trim()
            .replace(/\s{2,}/g, " ")
            .substring(0, 100),
          depth: getDepth(element),
        };
      })
      .filter(Boolean);

    // Remove nested elements (keep only outermost)
    items = items.filter(
      (x) =>
        !items.some(
          (y) => y.element.contains(x.element) && x.element !== y.element
        )
    );

    // If too many elements, prioritize by DOM depth (higher in tree = lower depth)
    if (items.length > MAX_ELEMENTS) {
      items.sort((a, b) => {
        // Sort by depth (lower depth = higher priority)
        if (a.depth !== b.depth) return a.depth - b.depth;
        // Then by area (larger = higher priority)
        return b.area - a.area;
      });
      items = items.slice(0, MAX_ELEMENTS);
    }

    // Create annotations
    const labels = [];
    items.forEach((item, index) => {
      item.element.setAttribute("data-voyager-element-index", index);

      item.rects.forEach((bbox) => {
        const container = document.createElement("div");
        container.style.cssText = `
          outline: 2px dashed #000;
          position: fixed;
          left: ${bbox.left}px;
          top: ${bbox.top}px;
          width: ${bbox.width}px;
          height: ${bbox.height}px;
          pointer-events: none;
          box-sizing: border-box;
          z-index: 2147483647;
        `;

        const label = document.createElement("span");
        label.textContent = index;

        // Smart label positioning - always outside the element
        let labelTop, labelLeft;
        const labelHeight = 20; // Approximate height of label

        // If element is at top of viewport (less than label height), place label below
        if (bbox.top < labelHeight) {
          labelTop = bbox.height + 2; // Place below the element
        } else {
          labelTop = -labelHeight; // Place above the element
        }

        labelLeft = 0;

        label.style.cssText = `
          position: absolute;
          top: ${labelTop}px;
          left: ${labelLeft}px;
          background: #000;
          color: #fff;
          padding: ${LABEL_PADDING}px;
          font-size: ${LABEL_FONT_SIZE}px;
          font-family: Arial, sans-serif;
          font-weight: bold;
          border-radius: 3px;
          line-height: 1;
          white-space: nowrap;
          box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        `;

        container.appendChild(label);
        container.setAttribute("data-voyager-rect-index", index);
        document.body.appendChild(container);
        labels.push(container);
      });
    });

    return items.map((_, index) => index);
  }

  function getDepth(element) {
    let depth = 0;
    let current = element;
    while (current.parentElement) {
      depth++;
      current = current.parentElement;
    }
    return depth;
  }

  return markPage();
})();
