import { test } from "node:test";
import assert from "node:assert/strict";
import { normalize, search } from "../js/search.js";

test("normalize unifies chome numerals, width and kana", () => {
  assert.equal(normalize("大泉学園町６丁目"), "大泉学園町6丁目");
  assert.equal(normalize("内幸町一丁目"), "内幸町1丁目");
  assert.equal(normalize("大泉学園町六丁目"), "大泉学園町6丁目");
  assert.equal(normalize("十二丁目"), "12丁目");
  assert.equal(normalize("二十三丁目"), "23丁目");
  assert.equal(normalize(" 光が丘 "), "光ガ丘"); // names are normalized the same way, so this still matches
  assert.equal(normalize("おおいずみ"), "オオイズミ");
});

const PLACES = [
  ["練馬区大泉学園町６丁目", "ネリマクオオイズミガクエンチョウ６チョウメ", 139.58, 35.77, "t"],
  ["練馬区大泉学園町７丁目", "ネリマクオオイズミガクエンチョウ７チョウメ", 139.57, 35.78, "t"],
  ["千代田区内幸町一丁目", "チヨダクウチサイワイチョウ１チョウメ", 139.75, 35.67, "t"],
  ["光が丘駅", "", 139.63, 35.76, "s"],
];

test("search matches either numeral style", () => {
  assert.deepEqual(search(PLACES, "大泉学園町6").map((r) => r[0]), ["練馬区大泉学園町６丁目"]);
  assert.deepEqual(search(PLACES, "大泉学園町六丁目").map((r) => r[0]), ["練馬区大泉学園町６丁目"]);
  assert.deepEqual(search(PLACES, "内幸町1").map((r) => r[0]), ["千代田区内幸町一丁目"]);
});

test("search by kana, stations and empty query", () => {
  assert.deepEqual(search(PLACES, "うちさいわい").map((r) => r[0]), ["千代田区内幸町一丁目"]);
  assert.deepEqual(search(PLACES, "光が丘").map((r) => r[0]), ["光が丘駅"]);
  assert.deepEqual(search(PLACES, ""), []);
  assert.equal(search(PLACES, "大泉学園町").length, 2);
});
