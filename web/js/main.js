import * as maplibregl from "https://unpkg.com/maplibre-gl@6.11.2/dist/maplibre-gl.mjs";
import { findFeature } from "./lookup.js";
import { search } from "./search.js";

// ?region=oizumi-test opens the small trial build; the map position is never written to the URL
const REGIONS = { tokyo: "東京", osaka: "大阪" };  // regions with data under web/data/
const REGION = new URLSearchParams(location.search).get("region") ?? "tokyo";
const BASE = `data/${encodeURIComponent(REGION)}`;
const EMPTY = { type: "FeatureCollection", features: [] };
// station walking-area colours: neighbours never share one, and orange/yellow never touch (validated categorical set)
const PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7", "#eda100"];
const COLOR = ["match", ["get", "color"], 0, PAL[0], 1, PAL[1], 2, PAL[2], 3, PAL[3], 4, PAL[4], "#999"];
const TIER = { bus: "#8f8f8f", deep: "#4d4d4d" };
const KSJ = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-";
const mobile = () => matchMedia("(max-width: 760px)").matches;

const data = {};
const pending = {};
let meta, summary;
let ext = null;     // the planned-line scenario of this region, if any
let featured = [];  // current blanks the planned line changes (shown in the feature card)
let scenario = "base";
let marker = null;
let selection = null;  // {no, scenario}
let markReady;
const mapReady = new Promise((r) => { markReady = r; });  // map sources exist after style.load

async function getJSON(path) {
  const r = await fetch(`${BASE}/${path}`);
  if (!r.ok) throw new Error(`地図データ ${path} を読めませんでした (${r.status})`);
  return r.json();
}

// Each file is fetched once; data[key] is filled when it arrives (key = file name without extension).
function ensure(file) {
  const key = file.replace(/\.(geo)?json$/, "");
  pending[key] ??= getJSON(file).then((d) => (data[key] = d));
  return pending[key];
}

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const people = (n) => (n >= 10000 ? `${(n / 10000).toFixed(1)} 万人` : `${n.toLocaleString()} 人`);
const stName = (s) => (s.planned ? s.name : `${s.name}駅`);
const ride = (s) => (s.planned ? "予定駅" : s.ridership ? `乗降 ${(s.ridership / 10000).toFixed(1)} 万人/日` : "乗降 非公表");
const title = (b) => `${esc(b.muni)} ― ${esc(b.name)}`;

function showError(msg) {
  $("error").textContent = msg;
  $("error").hidden = false;
}

function badge(b) {
  const a = ext && b.after?.[ext.name];
  if (!a?.status) return "";
  if (scenario === "base") return `<span class="badge plan">${ext.verb}計画あり</span>`;  // only blanks the plan changes reach here
  return a.status === "解消" ? `<span class="badge">${ext.verb}で解消</span>`
    : `<span class="badge part">${ext.verb}で縮小 (${Math.round(a.left * 100)}% が残る)</span>`;
}

// what the planned line does to a current blank, in one line
function outcome(b) {
  const a = b.after[ext.name];
  const gone = Math.round((1 - a.left) * 100);
  return `${ext.verb}後: 空白の ${gone}% が予定駅の徒歩圏に入り、${a.status === "解消" ? "空白地帯としては解消" : "空白地帯が縮小"}`;
}

// 現在 / 延伸後 (開業後), placed next to the blanks it concerns (the feature card and the info box)
function toggleHTML() {
  const on = (sc) => `aria-pressed="${scenario === sc}"`;
  return `<div class="toggle" role="group" aria-label="${esc(ext.label)}との比較">
    <button type="button" data-scenario="base" ${on("base")}>現在</button>
    <button type="button" data-scenario="${esc(ext.name)}" ${on(ext.name)}>${ext.verb}後</button></div>`;
}

// the planned stations and how far each is from today's stations
const plannedStations = () => summary.planned?.[ext.name] ?? [];
const km = (m) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${m} m`);

// when no blank changes: say so, with the farthest planned station as the evidence
function noChangeText() {
  const ps = plannedStations();
  const walk = summary.blank_min * 80;
  const inside = ps.filter((s) => s.walk_m != null && s.walk_m < walk);
  const far = inside.reduce((a, s) => (s.walk_m > (a?.walk_m ?? -1) ? s : a), null);
  const people = (k) => summary.blanks[k].reduce((n, b) => n + b.population, 0);
  const diff = people("base") - people(ext.name);
  return `新しい駅 ${ps.length} か所のうち ${inside.length} か所は、今の駅から歩いて ${summary.blank_min} 分以内${far ? ` (最も遠い${esc(far.name)}で道のり約 ${km(far.walk_m)})` : ""}にあります。
    ${ext.verb}しても、空白地帯はほとんど変わりません${diff > 0 ? ` (空白に住む人で約 ${diff.toLocaleString()} 人分)` : ""}。`;
}

function renderFeature() {
  $("feature").innerHTML = `<h2>特集: ${esc(ext.title)}</h2>
    ${featured.length ? "" : `<p class="fbody">${noChangeText()}</p>`}
    ${featured.map((b) => `<div class="fcard" tabindex="0" data-no="${b.no}">
      <span class="no">${b.no}</span>
      <span class="nm">${title(b)}</span>
      <span class="meta">住む人 約 ${people(b.population)} ・ 空白 ${b.area_km2} km² ・ 人口密度の順位 ${b.no} 位<br>${outcome(b)}</span></div>`).join("")}
    ${toggleHTML()}
    <p class="fnote">予定駅は概略位置${ext.opening ? `で、開業は${esc(ext.opening)}の予定` : ""}です。</p>`;
  $("feature").hidden = false;
}

function areaText(b) {
  const parts = [`空白 ${b.area_km2} km²`];
  if (b.deep_km2 > 0) parts.push(`(バス圏 ${b.bus_km2} ・ 奥地 ${b.deep_km2})`);
  return `人口密度 ${b.density.toLocaleString()} 人/km² ・ 住む人 約 ${people(b.population)} ・ ${parts.join(" ")}${b.max_km ? ` ・ 駅まで最大 ${b.max_km} km` : ""}`;
}

function row(b, sc, gone = false) {
  return `<li tabindex="0" data-no="${b.no}" data-sc="${sc}" class="${gone ? "gone" : ""}">
    <span class="no">${b.no}</span>
    <span class="nm"><span class="t">${title(b)}</span>${sc === "base" ? badge(b) : ""}</span>
    <span class="meta">${areaText(b)}<br>
      住む人の最寄り駅: ${b.stations.map((s) => `${esc(s.name)} ${Math.round(s.share * 100)}%`).join("、")}</span></li>`;
}

function renderList() {
  let html;
  if (scenario === "base") {
    html = summary.blanks.base.map((b) => row(b, "base")).join("");
  } else {
    // same order and numbers as now: a changed blank stays in its place, struck through when resolved
    const after = new Map(summary.blanks[scenario].map((b) => [b.no, b]));
    html = summary.blanks.base.map((b) => (b.after?.[scenario]?.status ? row(b, "base", b.after[scenario].status === "解消")
      : after.has(b.no) ? row(after.get(b.no), scenario) : "")).join("");
    const known = new Set(summary.blanks.base.map((b) => b.no));
    const left = summary.blanks[scenario].filter((b) => !known.has(b.no));
    if (left.length) html += `<li class="group">${ext.verb}後に残る所 (新しい番号)</li>${left.map((b) => row(b, scenario)).join("")}`;
  }
  $("list").innerHTML = html;
  markSelected();
}

function markSelected() {
  for (const li of document.querySelectorAll("#list li[data-no]")) {
    const on = selection && Number(li.dataset.no) === selection.no && li.dataset.sc === selection.scenario;
    li.classList.toggle("sel", Boolean(on));
    if (on) li.scrollIntoView({ block: "nearest" });
  }
}

function buildLegend() {
  $("legend").innerHTML = `
    <div class="row"><span class="sw" style="background:${PAL[0]};opacity:.4"></span>駅の徒歩圏 (${summary.blank_min} 分以内。駅ごとに色分け)</div>
    <div class="row"><span class="sw" style="background:${TIER.bus};opacity:.5"></span>空白 (バス圏): 駅まで ${summary.blank_min * 80 / 1000}〜${summary.bus_km} km</div>
    <div class="row"><span class="sw" style="background:${TIER.deep};opacity:.65"></span>空白 (奥地): ${summary.bus_km} km 超・道のない山林</div>
    <div class="row"><span class="sw" style="background:transparent;border:2px solid var(--fg)"></span>空白地帯の区切り (区市町村ごと)</div>
    ${ext && featured.length ? `<div class="row"><span class="sw" style="background:transparent;border:2px dashed var(--fg)"></span>${ext.verb}計画のある空白地帯</div>` : ""}
    ${ext ? `
    <div class="row"><span class="sw dot"></span>予定駅 (概略位置)</div>` : ""}
    <div class="note">${esc(meta.place_name)}の外は薄く表示しています。</div>`;
}

function buildNotes() {
  const planned = meta.scenarios.find((s) => s.name !== "base");
  const src = meta.sources ?? {};
  const got = (k) => (src[k] ? ` (取得 ${src[k].retrieved_utc.slice(0, 10)})` : "");
  // 国土数値情報: the terms ask for the dataset page URL and a note that it was processed
  const ksj = (name, page) => `「国土数値情報（${name}）」（国土交通省）（<a href="${KSJ}${page}.html">${KSJ}${page}.html</a>）を加工して作成`;
  const walkKm = summary.blank_min * 80 / 1000;
  $("notes").innerHTML = `
    <h2>この地図の考え方</h2>
    <ul>
      <li>「駅の徒歩圏」は、駅まで道のりで歩いて ${summary.blank_min} 分 (80 m/分で ${walkKm} km) 以内の所です。いちばん近い駅ごとに色分けしています (色そのものに意味はありません)。</li>
      <li>「鉄道空白地帯」は、どの駅の徒歩圏にも入らない所です。道のない山林も含みます。人が住んでいるかどうかは定義に入れていません。駅まで ${walkKm}〜${summary.bus_km} km の所は「バス圏」(バスならおよそ 30 分で駅に出られる目安)、それより遠い所と道のない山林は「奥地」です。</li>
      <li>空白地帯は区市町村の境で区切り、0.3 km² 以上のまとまりに番号を付けています。番号は人口密度 (空白地帯の面積あたりの住む人の数) の高い順です。市街地の中の空白ほど上に来ます。一覧は${esc(meta.label)}の部分だけですが、地図はその外も薄く表示しています。</li>
      <li>「住む人」は 2020 年国勢調査の 250 m メッシュ人口を面積の割合で配った概数、「住む人の最寄り駅」は住む人の数で重み付けした割合 (人がいない所は面積の割合) です。乗降客数は参考です。</li>
    </ul>
    <h2>この地図の限界</h2>
    <ul>
      <li>駅の位置はホームの中心線で、出口ではありません。信号・坂・階段・混雑は入れていません。</li>
      <li>「バス圏」は道のりの距離による目安で、実際のバス路線・本数は使っていません。</li>
      <li>OpenStreetMap に載っていない道は通れない扱いです。道から 300 m 以上離れた所は「道のない所」として奥地に含めています。</li>
      ${planned ? `<li>${planned.verb}後の予定駅 (仮称) は、${esc(planned.note)}</li>` : ""}
    </ul>
    <h2>出典</h2>
    <ul>
      <li>道路・水域: © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> (ODbL)${got(meta.osm_source)}</li>
      <li>駅: ${ksj("鉄道データ", "N02-2025")} (2025年12月31日時点)${got("n02")}</li>
      <li>乗降客数: ${ksj("駅別乗降客数データ", "S12-2024")} (${summary.ridership_year} 年、各社の合計)${got("s12")}</li>
      <li>行政区域: ${ksj("行政区域データ", "N03-2026")} (2026年1月1日時点)</li>
      <li>人口: 「令和2年国勢調査に関する地域メッシュ統計」（総務省統計局）を加工して作成 (出典: 政府統計の総合窓口 <a href="https://www.e-stat.go.jp/">e-Stat</a>)</li>
      <li>町丁目の名前と位置: 「アドレス・ベース・レジストリ」（デジタル庁）（<a href="https://dataset.address-br.digital.go.jp/">https://dataset.address-br.digital.go.jp/</a>）を加工して作成</li>
      <li>この地図のデータのライセンスは<a href="https://github.com/isshiki/rail-gap-map/blob/main/docs/data-policy.md">データポリシー</a>のとおりです (道路から計算した徒歩圏・空白地帯は OpenStreetMap の派生データベースとして ODbL 1.0)。国や各機関が作成したものではありません。</li>
      <li>背景地図: <a href="https://maps.gsi.go.jp/development/ichiran.html">地理院タイル</a> (表示範囲のタイルは国土地理院のサーバーから読み込みます)</li>
      ${planned?.sources?.length ? `<li>${esc(planned.label.replace(/後$/, ""))}: ${planned.sources.map((s) => `<a href="${esc(s.url)}">${esc(s.name)}</a>`).join("、")}</li>` : ""}
    </ul>
    <p>データ作成: ${meta.built_utc.slice(0, 10)} / <a href="https://github.com/isshiki/rail-gap-map">ソースコード</a></p>`;
}

function labelPoints(sc) {
  return { type: "FeatureCollection", features: summary.blanks[sc].map((b) => ({
    type: "Feature", properties: { no: b.no }, geometry: { type: "Point", coordinates: b.label } })) };
}

function addLayers(map) {
  map.addSource("walk", { type: "geojson", data: data["walk-base"] });
  map.addSource("tiers", { type: "geojson", data: data["tiers-base"] });
  map.addSource("blanks", { type: "geojson", data: data["blanks-base"] });
  map.addSource("blank-pts", { type: "geojson", data: labelPoints("base") });
  map.addSource("veil", { type: "geojson", data: data.veil });
  map.addSource("outline", { type: "geojson", data: data.outline });
  map.addSource("links", { type: "geojson", data: EMPTY });
  map.addSource("pins", { type: "geojson", data: EMPTY });
  map.addSource("ghost", { type: "geojson", data: EMPTY });  // a resolved area, drawn while viewing the extension
  map.addSource("stations", { type: "geojson", data: data.stations });

  map.addLayer({ id: "walk", type: "fill", source: "walk", paint: { "fill-color": COLOR, "fill-opacity": 0.3 } });
  map.addLayer({ id: "walk-line", type: "line", source: "walk", paint: { "line-color": "#555", "line-width": 0.6, "line-opacity": 0.6 } });
  map.addLayer({ id: "tier", type: "fill", source: "tiers",
    paint: { "fill-color": ["match", ["get", "tier"], "bus", TIER.bus, TIER.deep], "fill-opacity": ["match", ["get", "tier"], "bus", 0.35, 0.5] } });
  map.addLayer({ id: "veil", type: "fill", source: "veil", paint: { "fill-color": "#ffffff", "fill-opacity": 0.5 } });
  map.addLayer({ id: "outline", type: "line", source: "outline", paint: { "line-color": "#333", "line-width": 1.2, "line-dasharray": [4, 2] } });
  const sel = ["==", ["get", "no"], ["coalesce", ["global-state", "sel"], -1]];
  const after = ["==", ["global-state", "after"], true];
  // blanks the planned line changes get a dashed edge in the current view
  const plan = ["all", ["!", after], ["in", ["get", "no"], ["literal", featured.map((b) => b.no)]]];
  map.setGlobalStateProperty("after", false);
  map.addLayer({ id: "blank-line", type: "line", source: "blanks", filter: ["!", plan],
    paint: { "line-color": "#111", "line-width": ["case", sel, 3.5, 1.3] } });
  map.addLayer({ id: "blank-plan", type: "line", source: "blanks", filter: plan,
    paint: { "line-color": "#111", "line-width": ["case", sel, 3.5, 2.2], "line-dasharray": [2, 1.2] } });
  map.addLayer({ id: "ghost", type: "line", source: "ghost", paint: { "line-color": "#111", "line-width": 2, "line-dasharray": [1, 1.5] } });
  map.addLayer({ id: "links", type: "line", source: "links", paint: { "line-color": "#111", "line-width": 1.6, "line-dasharray": [2, 2] } });
  const planned = ["==", ["get", "planned"], true];
  map.addLayer({ id: "stations", type: "circle", source: "stations", minzoom: 11, filter: ["!", planned],
    paint: { "circle-radius": 3.5, "circle-color": "#222", "circle-stroke-color": "#fff", "circle-stroke-width": 1 } });
  map.addLayer({ id: "station-labels", type: "symbol", source: "stations", minzoom: 12.5, filter: ["!", planned],
    layout: { "text-field": ["get", "name"], "text-size": 12, "text-offset": [0, 0.9], "text-anchor": "top", "text-font": ["Noto Sans Regular"] },
    paint: { "text-color": "#111", "text-halo-color": "#fff", "text-halo-width": 1.6 } });
  // planned stations: faint white rings now, solid after the extension
  map.addLayer({ id: "plan-stations", type: "circle", source: "stations", minzoom: 10, filter: planned,
    paint: { "circle-radius": 6, "circle-color": "#fff", "circle-stroke-color": "#111", "circle-stroke-width": 2,
      "circle-opacity": ["case", after, 0.85, 0.5], "circle-stroke-opacity": ["case", after, 1, 0.55] } });
  map.addLayer({ id: "plan-labels", type: "symbol", source: "stations", minzoom: 11.5, filter: planned,
    layout: { "text-field": ["concat", ["get", "name"], "\n(予定駅・概略位置)"], "text-size": 12, "text-offset": [0, 0.9],
      "text-anchor": "top", "text-font": ["Noto Sans Regular"] },
    paint: { "text-color": "#111", "text-halo-color": "#fff", "text-halo-width": 1.6, "text-opacity": ["case", after, 1, 0.65] } });
  map.addLayer({ id: "pins", type: "circle", source: "pins",
    paint: { "circle-radius": 8, "circle-color": "#fff", "circle-stroke-color": "#111", "circle-stroke-width": 3 } });
  map.addLayer({ id: "pin-label", type: "symbol", source: "pins",
    layout: { "text-field": ["get", "label"], "text-size": 13, "text-offset": [0, -1.4], "text-anchor": "bottom",
      "text-font": ["Noto Sans Regular"], "text-allow-overlap": true },
    paint: { "text-color": "#111", "text-halo-color": "#fff", "text-halo-width": 2 } });
  map.addLayer({ id: "blank-no-bg", type: "circle", source: "blank-pts",
    paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 8, 13, 12], "circle-color": ["case", sel, "#111", "#3a3f4a"],
      "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
  map.addLayer({ id: "blank-no", type: "symbol", source: "blank-pts",
    layout: { "text-field": ["to-string", ["get", "no"]], "text-size": ["interpolate", ["linear"], ["zoom"], 9, 10, 13, 13],
      "text-font": ["Noto Sans Regular"], "text-allow-overlap": true },
    paint: { "text-color": "#fff" } });
}

function info(html) {
  $("info").innerHTML = `<button class="close" type="button" aria-label="閉じる">×</button>${html}`;
  $("info").hidden = false;
}

function clearPins(map) {
  map.getSource("pins").setData(EMPTY);
  map.getSource("links").setData(EMPTY);
}

async function selectBlank(map, no, sc, fly = true) {
  await mapReady;
  const b = summary.blanks[sc].find((x) => x.no === no);
  if (!b) return;
  selection = { no, scenario: sc };
  markSelected();
  map.setGlobalStateProperty("sel", sc === scenario ? no : null);
  const ghost = sc === scenario ? [] : data[`blanks-${sc}`].features.filter((f) => f.properties.no === no);
  map.getSource("ghost").setData({ type: "FeatureCollection", features: ghost });
  const plan = Boolean(ext && b.after?.[ext.name]?.status);  // a blank the planned line changes
  const afterView = plan && scenario !== "base";
  // the stations its residents walk to now: a pin each, with a dotted line from the area (not after the extension)
  const stations = afterView ? [] : b.stations;
  map.getSource("pins").setData({ type: "FeatureCollection", features: stations.map((s) => ({ type: "Feature",
    properties: { label: `${stName(s)} (${Math.round(s.share * 100)}%)` }, geometry: { type: "Point", coordinates: [s.lon, s.lat] } })) });
  map.getSource("links").setData({ type: "FeatureCollection", features: stations.map((s) => ({ type: "Feature", properties: {},
    geometry: { type: "LineString", coordinates: [b.label, [s.lon, s.lat]] } })) });
  info(`<strong>空白地帯 #${b.no} ${title(b)}</strong>${sc === "base" ? badge(b) : ""}<br>
    ${areaText(b)}<br>
    ${afterView ? `${outcome(b)}<br>
      <span style="color:var(--muted)">点線 = ${ext.verb}前の空白地帯の区切り、白丸 = 予定駅 (概略位置)</span>`
    : `住む人の最寄り駅: ${b.stations.map((s) => `${esc(stName(s))} ${Math.round(s.share * 100)}% (${ride(s)})`).join("、")}<br>
      <span style="color:var(--muted)">点線の先 = 住む人の最寄り駅${sc !== scenario ? ` (${ext.verb}前)` : ""}</span>`}
    ${plan ? toggleHTML() : ""}`);
  // keep the area clear of the info box: beside it on wide screens, below it on phones
  if (fly) {
    const box = $("info").getBoundingClientRect(), top = map.getContainer().getBoundingClientRect().top;
    const pts = afterView ? [...ghost.flatMap((f) => points(f.geometry.coordinates)), ...ext.planned.map((s) => [s.lon, s.lat])]
      : [b.label, ...b.stations.map((s) => [s.lon, s.lat])];
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]],
      { padding: mobile() ? { top: box.bottom - top + 24, bottom: 130, left: 40, right: 40 }
        : { top: 60, bottom: 60, left: 60, right: box.width + 100 }, maxZoom: 14 });
  }
  if (mobile()) $("sheet").classList.add("collapsed");
}

// a plan that changes no blank: frame the planned stations and list how far each is from today's stations
async function showPlanned(map) {
  await mapReady;
  selection = null;
  markSelected();
  map.setGlobalStateProperty("sel", null);
  map.getSource("ghost").setData(EMPTY);
  clearPins(map);
  const ps = plannedStations();
  info(`<strong>${esc(ext.title.replace(/で空白地帯.*$/, ""))}の予定駅</strong><br>
    ${ps.map((s) => `${esc(s.name)}: 今の駅から道のり ${s.walk_m == null ? "?" : km(s.walk_m)}`).join("<br>")}<br>
    <span style="color:var(--muted)">白丸 = 予定駅 (概略位置)。どれも今の駅の徒歩圏 (${summary.blank_min} 分 = ${summary.blank_min * 80 / 1000} km) の中です</span>
    ${toggleHTML()}`);
  const xs = ps.map((s) => s.lon), ys = ps.map((s) => s.lat);
  const box = $("info").getBoundingClientRect(), top = map.getContainer().getBoundingClientRect().top;
  map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]],
    { padding: mobile() ? { top: box.bottom - top + 24, bottom: 130, left: 40, right: 40 }
      : { top: 60, bottom: 60, left: 60, right: box.width + 100 }, maxZoom: 14 });
  if (mobile()) $("sheet").classList.add("collapsed");
}

// every [lon, lat] in a GeoJSON coordinate array
const points = (c) => (typeof c[0] === "number" ? [c] : c.flatMap(points));

async function pointInfo(map, ll, heading = "") {
  await mapReady;
  if (!marker) marker = new maplibregl.Marker({ color: "#111" });
  marker.setLngLat(ll).addTo(map);
  map.getSource("ghost").setData(EMPTY);
  clearPins(map);
  const walk = findFeature(data[`walk-${scenario}`], ll);
  const tier = findFeature(data[`tiers-${scenario}`], ll);
  const blank = findFeature(data[`blanks-${scenario}`], ll);
  let text;
  if (walk) text = `${esc(stName(walk.properties))}の徒歩圏 (歩いて ${summary.blank_min} 分以内)`;
  else if (tier) text = tier.properties.tier === "bus" ? `鉄道空白地帯 (バス圏: 駅まで ${summary.blank_min * 80 / 1000}〜${summary.bus_km} km)` : `鉄道空白地帯 (奥地: 駅まで ${summary.bus_km} km 超、または道のない所)`;
  else text = "計算していない所 (水面など)";
  info(`${heading ? `<strong>${esc(heading)}</strong><br>` : ""}${text}${blank ? `<br>空白地帯 #${blank.properties.no} に入っています` : ""}`);
  map.setGlobalStateProperty("sel", blank ? blank.properties.no : null);
}

async function setScenario(map, name) {
  scenario = name;
  for (const b of document.querySelectorAll(".toggle button[data-scenario]")) b.setAttribute("aria-pressed", String(b.dataset.scenario === name));
  await Promise.all([mapReady, ...["walk", "tiers", "blanks"].map((k) => ensure(`${k}-${name}.geojson`))]);
  if (scenario !== name) return;  // switched again while loading
  map.getSource("walk").setData(data[`walk-${name}`]);
  map.getSource("tiers").setData(data[`tiers-${name}`]);
  map.getSource("blanks").setData(data[`blanks-${name}`]);
  map.getSource("blank-pts").setData(labelPoints(name));
  map.setGlobalStateProperty("after", name !== "base");
  map.setGlobalStateProperty("sel", null);
  map.getSource("ghost").setData(EMPTY);
  clearPins(map);
  selection = null;
  $("info").hidden = true;
  renderList();
}

function setupSearch(map) {
  const input = $("search");
  const list = $("search-results");
  let rows = [];
  const render = () => {
    if (!data.places) {
      ensure("places.json").then(render);
      return;
    }
    rows = search(data.places, input.value);
    list.innerHTML = rows.map((r, i) => `<li role="option" tabindex="0" data-i="${i}">${esc(r[0])}</li>`).join("");
  };
  const choose = (r) => {
    list.innerHTML = "";
    input.value = r[0];
    input.blur();
    map.flyTo({ center: [r[2], r[3]], zoom: 14 });
    pointInfo(map, [r[2], r[3]], r[0]);
    if (mobile()) $("sheet").classList.add("collapsed");
  };
  input.addEventListener("input", render);
  list.addEventListener("click", (e) => { const li = e.target.closest("li"); if (li) choose(rows[Number(li.dataset.i)]); });
  list.addEventListener("keydown", (e) => { const li = e.target.closest("li"); if (li && e.key === "Enter") choose(rows[Number(li.dataset.i)]); });
  $("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    if (rows[0]) choose(rows[0]);
    else if (input.value.trim()) info("見つかりませんでした。町丁目名 (例: 大泉学園町6丁目) か駅名で探してください。");
  });
  $("locate").addEventListener("click", () => {
    if (!navigator.geolocation) {
      info("このブラウザでは現在地を使えません。検索で探してください。");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const ll = [pos.coords.longitude, pos.coords.latitude];
        map.flyTo({ center: ll, zoom: 14 });
        pointInfo(map, ll, "現在地");
      },
      () => info("現在地を取得できませんでした。検索で探してください。"),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 },
    );
  });
}

async function main() {
  [meta, summary] = await Promise.all([getJSON("meta.json"), getJSON("summary.json")]);
  ext = meta.scenarios.find((s) => s.name !== "base") ?? null;
  featured = ext ? summary.blanks.base.filter((b) => b.after?.[ext.name]?.status) : [];
  // the page names its region (東京 / 大阪 …)
  const heading = `${meta.place_name}の鉄道空白地帯`;
  document.title = heading;
  for (const id of ["page-title", "sheet-title"]) $(id).textContent = heading;
  $("regions").innerHTML = Object.entries(REGIONS).map(([k, v]) =>
    k === REGION ? `<a aria-current="page">${v}</a>` : `<a href="?region=${k}">${v}</a>`).join("");
  // draw the current view first; the other scenario and the search index follow
  await Promise.all(["walk-base", "tiers-base", "blanks-base", "veil", "outline", "stations"].map((f) => ensure(`${f}.geojson`)));
  buildLegend();
  buildNotes();
  renderList();
  if (ext) renderFeature();

  const map = new maplibregl.Map({
    container: "map", hash: false, center: meta.home_view.center, zoom: meta.home_view.zoom - (mobile() ? 0.9 : 0),
    minZoom: 8, maxZoom: 17.5,
    style: {
      version: 8,
      // Noto Sans (SIL OFL 1.1, web/fonts/OFL.txt) served with the page; Japanese text uses the device fonts
      glyphs: `${new URL("fonts/", location.href).href}{fontstack}/{range}.pbf`,
      sources: { gsi: { type: "raster", tiles: ["https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png"], tileSize: 256,
        minzoom: 2, maxzoom: 18, attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html">地理院タイル</a>' } },
      layers: [{ id: "gsi", type: "raster", source: "gsi", paint: { "raster-saturation": -0.9 } }],
    },
    attributionControl: { compact: true,
      customAttribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> / 国土数値情報 / 国勢調査 (e-Stat) / アドレス・ベース・レジストリ' },
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
  // style.load fires before the background tiles finish, so the areas appear without waiting for them
  map.once("style.load", () => {
    addLayers(map);
    markReady();
    map.on("click", (e) => {
      const hit = map.queryRenderedFeatures(e.point, { layers: ["blank-no-bg"] })[0];
      if (hit) selectBlank(map, hit.properties.no, scenario, false);
      else pointInfo(map, e.lngLat.toArray());
    });
    map.on("mouseenter", "blank-no-bg", () => { map.getCanvas().style.cursor = "pointer"; });
    map.on("mouseleave", "blank-no-bg", () => { map.getCanvas().style.cursor = ""; });
    const later = ["places.json", ...(ext ? ["walk", "tiers", "blanks"].map((k) => `${k}-${ext.name}.geojson`) : [])];
    Promise.all(later.map(ensure)).catch((e) => showError(e.message));
  });

  $("list").addEventListener("click", (e) => {
    const li = e.target.closest("li[data-no]");
    if (li) selectBlank(map, Number(li.dataset.no), li.dataset.sc);
  });
  $("list").addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.closest("li[data-no]")?.click(); });
  // 現在 / 延伸後 (feature card or info box): switch, then show the changed blank
  document.addEventListener("click", async (e) => {
    const b = e.target.closest(".toggle button[data-scenario]");
    if (!b) return;
    if (b.dataset.scenario !== scenario) await setScenario(map, b.dataset.scenario);
    if (featured[0]) selectBlank(map, featured[0].no, "base");
    else showPlanned(map);
  });
  $("feature").addEventListener("click", (e) => {
    const card = e.target.closest(".fcard");
    if (card) selectBlank(map, Number(card.dataset.no), "base");
  });
  $("feature").addEventListener("keydown", (e) => { if (e.key === "Enter") e.target.closest(".fcard")?.click(); });
  $("info").addEventListener("click", (e) => { if (e.target.closest(".close")) $("info").hidden = true; });
  $("sheet-handle").addEventListener("click", () => {
    const collapsed = $("sheet").classList.toggle("collapsed");
    $("sheet-handle").setAttribute("aria-expanded", String(!collapsed));
  });
  $("ctl").addEventListener("click", (e) => { if (!e.target.closest("button")) $("ctl").classList.toggle("open"); });
  if (mobile()) $("sheet").classList.add("collapsed");
  setupSearch(map);
}

main().catch((e) => showError(e.message));
