// Which polygon feature contains a [lon, lat] point (ray casting with a bbox prefilter).

function ringContains(ring, [x, y]) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

function polygonContains(rings, pt) {
  if (!ringContains(rings[0], pt)) return false;
  for (let k = 1; k < rings.length; k++) if (ringContains(rings[k], pt)) return false;
  return true;
}

function bbox(geom) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
  for (const p of polys) {
    for (const [x, y] of p[0]) {
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    }
  }
  return [minX, minY, maxX, maxY];
}

const bboxCache = new WeakMap();

export function pointInFeature(pt, feature) {
  const g = feature.geometry;
  if (!g || (g.type !== "Polygon" && g.type !== "MultiPolygon")) return false;
  let b = bboxCache.get(feature);
  if (!b) bboxCache.set(feature, (b = bbox(g)));
  if (pt[0] < b[0] || pt[0] > b[2] || pt[1] < b[1] || pt[1] > b[3]) return false;
  if (g.type === "Polygon") return polygonContains(g.coordinates, pt);
  return g.coordinates.some((rings) => polygonContains(rings, pt));
}

export function findFeature(fc, pt) {
  return fc.features.find((f) => pointInFeature(pt, f)) ?? null;
}
