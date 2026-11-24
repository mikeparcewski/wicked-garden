// Keep pointer labels off app text while preserving side order (wicked-garden#1514).
export function placeLabel({ box, pad = 0, label, texts, frame }, preferred = "above") {
  const gap = 9, room = 44;
  const padded = { x: box.x - pad, y: box.y - pad, width: box.width + 2 * pad, height: box.height + 2 * pad };
  const positions = [
    { side: "above", x: padded.x - 3, y: padded.y - gap - label.height, room: box.y - frame.top },
    { side: "below", x: padded.x - 3, y: padded.y + padded.height + gap, room: frame.bottom - box.y - box.height },
    { side: "right", x: padded.x + padded.width + gap, y: padded.y + (padded.height - label.height) / 2, room: Infinity },
  ].map((p) => {
    const fits = p.room >= room && p.x >= frame.left && p.y >= frame.top &&
      p.x + label.width <= frame.right && p.y + label.height <= frame.bottom;
    const area = fits ? texts.reduce((sum, t) => sum +
      Math.max(0, Math.min(p.x + label.width, t.x + t.width) - Math.max(p.x, t.x)) *
      Math.max(0, Math.min(p.y + label.height, t.y + t.height) - Math.max(p.y, t.y)), 0) : Infinity;
    return { ...p, fits, area };
  });
  if (preferred === "below" && positions[1].fits) return "below";
  return positions.reduce((best, p) => p.area < best.area ? p : best).side;
}
