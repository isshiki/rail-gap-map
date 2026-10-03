// Client-side search over places.json rows: [name, kana, lon, lat, kind].
// Names are published with either 一丁目 or １丁目, so query and names are normalized the same way.

const DIGIT = { 〇: 0, 一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9 };

function kanjiToNumber(s) {
  // handles 一..九十九 (enough for chome numbers)
  const i = s.indexOf("十");
  if (i < 0) return DIGIT[s];
  const tens = i === 0 ? 1 : DIGIT[s[0]];
  const ones = i === s.length - 1 ? 0 : DIGIT[s[i + 1]];
  return tens * 10 + ones;
}

function hiraganaToKatakana(s) {
  return s.replace(/[ぁ-ゖ]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 0x60));
}

export function normalize(s) {
  return hiraganaToKatakana(
    s.normalize("NFKC")
      .replace(/\s+/g, "")
      .replace(/([〇一二三四五六七八九十]+)丁目/g, (_, k) => `${kanjiToNumber(k)}丁目`),
  );
}

let cache = null;

function prepared(places) {
  if (cache?.places !== places) {
    cache = { places, rows: places.map((r) => ({ row: r, name: normalize(r[0]), kana: normalize(r[1] || "") })) };
  }
  return cache.rows;
}

export function search(places, query, limit = 10) {
  const q = normalize(query);
  if (!q) return [];
  const hits = [];
  for (const { row, name, kana } of prepared(places)) {
    const i = name.indexOf(q);
    const j = i < 0 && kana ? kana.indexOf(q) : -1;
    if (i >= 0 || j >= 0) hits.push({ row, score: (i >= 0 ? i : 50) + (row[4] === "s" ? 0 : 0.5) + name.length / 100 });
  }
  hits.sort((a, b) => a.score - b.score);
  return hits.slice(0, limit).map((h) => h.row);
}
