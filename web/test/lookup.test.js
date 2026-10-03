import { test } from "node:test";
import assert from "node:assert/strict";
import { pointInFeature, findFeature } from "../js/lookup.js";

const square = (x0, y0, x1, y1, props) => ({
  type: "Feature", properties: props,
  geometry: { type: "Polygon", coordinates: [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]] },
});

test("point in polygon with hole", () => {
  const f = { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [
    [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
    [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
  ] } };
  assert.equal(pointInFeature([1, 1], f), true);
  assert.equal(pointInFeature([5, 5], f), false);
});

test("point in multipolygon", () => {
  const f = { type: "Feature", properties: {}, geometry: { type: "MultiPolygon", coordinates: [
    [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    [[[5, 5], [6, 5], [6, 6], [5, 6], [5, 5]]],
  ] } };
  assert.equal(pointInFeature([5.5, 5.5], f), true);
  assert.equal(pointInFeature([3, 3], f), false);
});

test("findFeature returns first containing feature", () => {
  const fc = { type: "FeatureCollection", features: [square(0, 0, 1, 1, { lo: 0, hi: 5 }), square(1, 0, 2, 1, { lo: 5, hi: 10 })] };
  assert.deepEqual(findFeature(fc, [1.5, 0.5]).properties, { lo: 5, hi: 10 });
  assert.equal(findFeature(fc, [5, 5]), null);
});
