"use strict";

const REPO = "https://github.com/HeyVasily/rust-desktop-comparison";
const CSV_PATH = "measurements/native-matrix-2026-11-09/summary.csv";
const DESKTOP_PATH = "data/desktop-results.json";
const OS_RUNNER = { windows: "windows-2022", macos: "macos-15", linux: "ubuntu-24.04" };
const OS_ORDER = ["linux", "windows", "macos"];
const OS_NAME = { windows: "Windows", macos: "macOS", linux: "Linux" };

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c != null) node.append(c);
  return node;
};
const svgEl = (tag, attrs = {}) => {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
};
const repoLink = (path) => {
  if (/^https?:/.test(path)) return path;
  return `${REPO}/blob/main/${path}`;
};
const fmtSize = (bytes) => {
  const mib = bytes / 2 ** 20;
  return mib >= 1 ? `${fmt(mib)} MiB` : `${Math.round(bytes / 1024)} KiB`;
};
const fmt = (n, d = 1) => n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
// Missing or unrecognized evidence is not a failed test.
const parseBoolean = (value) => value === "True" ? true : value === "False" ? false : null;
const startupLabel = (value) => value === true ? "passed" : value === false ? "failed" : "not tested";
const numberOrNull = (value) => {
  if ((typeof value !== "number" && typeof value !== "string") || String(value).trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

function parseCsv(text) {
  const [head, ...rows] = text.trim().split(/\r?\n/);
  const cols = head.split(",");
  return rows.map((line) => {
    const cells = line.split(",");
    return Object.fromEntries(cols.map((c, i) => [c, cells[i]]));
  });
}

async function load() {
  const [features, csv] = await Promise.all([
    fetch("data/features.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    fetch(CSV_PATH).then((r) => { if (!r.ok) throw new Error(r.status); return r.text(); }),
  ]);
  const runnerToOs = Object.fromEntries(Object.entries(OS_RUNNER).map(([k, v]) => [v, k]));
  const memory = {};
  for (const row of parseCsv(csv)) {
    if (row.phase !== "comparison") continue;
    const os = runnerToOs[row.os];
    memory[row.framework] ??= {};
    memory[row.framework][os] = {
      median: Number(row.primary_median_mib),
      min: Number(row.primary_min_mib),
      max: Number(row.primary_max_mib),
      reps: Number(row.repetitions),
      outliers: row.outlier_repetitions,
      rss: Number(row.rss_median_mib),
      rssMetric: row.rss_metric,
      cpu: Number(row.cpu_median_percent),
      metric: row.primary_metric,
      bytes: Number(row.executable_bytes),
      dark: parseBoolean(row.follows_dark_mode),
      run: row.run_id,
      commit: row.source_commit,
      runner: row.os,
    };
  }
  return { features, memory };
}

/* ---------- Optional current desktop evidence (independent of history) ---------- */
async function loadDesktop() {
  try {
    const response = await fetch(DESKTOP_PATH);
    if (!response.ok) return null;
    const data = await response.json();
    if (data?.schema_version !== 1 || !Array.isArray(data.platforms)
        || !Array.isArray(data.paired_ab) || !Array.isArray(data.sources) || !Array.isArray(data.limitations)) return null;
    return data;
  } catch {
    // Missing, malformed or unavailable optional data must not affect history.
    return null;
  }
}

function acceptanceLabel(acceptance = {}) {
  if (acceptance.status === "fully_verified") {
    return ["startup_light", "startup_dark", "live_theme", "clipboard", "cleanup", "process_cleanup", "evidence", "provenance"].every((key) => acceptance[key] === "passed")
      ? "Fully verified" : "Incomplete evidence";
  }
  return { failed: "Failed invocation(s)", environment_error: "Environment blocked", incomplete: "Incomplete evidence", not_run: "Not run" }[acceptance.status] ?? "Not run";
}

function renderDesktop(data) {
  const host = $("#desktop-results");
  if (!data || !host) return;
  const link = (url, label) => typeof url === "string" && url.startsWith(`${REPO}/`)
    ? el("a", { href: url, text: label }) : el("span", { text: label });
  const value = (raw, digits = 2) => numberOrNull(raw) == null ? "—" : fmt(numberOrNull(raw), digits);
  const evidence = (experiment) => {
    const a = experiment?.acceptance ?? {};
    const detail = el("details", { class: "acceptance-details" }, el("summary", { text: acceptanceLabel(a) }));
    const labels = { startup_light: "Light startup", startup_dark: "Separate dark startup", live_theme: "Live transitions",
      clipboard: "External clipboard", cleanup: "Settings cleanup", process_cleanup: "Process cleanup",
      evidence: "Evidence", provenance: "Source/build provenance" };
    detail.append(el("ul", {}, Object.entries(labels).map(([key, label]) => el("li", { text: `${label}: ${a[key] ?? "not_run"}` }))));
    detail.append(el("p", { text: `Acceptance invocations: ${a.normal_invocations ?? 0} normal / ${a.dark_invocations ?? 0} dark-startup. These are not the memory sample count.` }));
    for (const invocation of experiment?.invocations ?? []) {
      const links = invocation.links ?? {};
      detail.append(el("p", { class: "invocation" },
        el("b", { text: `${invocation.case}, r${invocation.repetition}: ${invocation.status || "not_run"}` }),
        el("span", { text: `Startup ${invocation.startup_theme_status || "not_run"} · live ${invocation.live_theme_status || "not_run"} · clipboard ${invocation.clipboard_status || "not_run"}` }),
        invocation.reason || invocation.evidence_errors ? el("span", { text: invocation.reason || invocation.evidence_errors }) : null,
        el("span", { class: "evidence-links" },
          links.outcome ? link(links.outcome, "Outcome") : null,
          links.desktop ? link(links.desktop, "Checks") : null,
          (links.screenshots ?? []).map((shot) => link(shot.url, shot.label))),
      ));
    }
    return detail;
  };
  const panels = data.platforms.map((platform) => {
    const rows = platform.candidates.flatMap((candidate) => {
      const experiments = candidate.experiments.length ? candidate.experiments : [null];
      return experiments.flatMap((experiment) => {
        const measurements = experiment?.measurements?.length ? experiment.measurements : [null];
        return measurements.map((m) => el("tr", {},
          el("th", { scope: "row" }, candidate.name,
            experiment ? el("small", {}, experiment.identity.os, " · ",
              link(experiment.links.commit, experiment.identity.source_commit?.slice(0, 8) || "unknown commit"), " · ",
              link(experiment.links.run, `run ${experiment.identity.run_id || "unknown"}`)) : null),
          el("td", {}, m ? el("b", { text: `${value(m.primary_median_mib)} MiB` }) : el("span", { text: "Not measured" }),
            el("small", { text: m ? `${m.primary_metric}; ${value(m.primary_min_mib)}–${value(m.primary_max_mib)} MiB` : "No eligible comparison result" })),
          el("td", { class: "num", text: m ? value(m.repetitions, 0) : "—" }),
          el("td", { class: "num", text: m ? numberOrNull(m.cpu_median_percent) === 0 ? "0 recorded" : value(m.cpu_median_percent, 5) : "—" }),
          el("td", {}, evidence(experiment)),
        ));
      });
    });
    return el("article", { class: "desktop-panel" }, el("h3", { text: platform.name }),
      el("div", { class: "scroll-x" }, el("table", { class: "data desktop-table" },
        el("thead", {}, el("tr", {}, ["Desktop profile / source", "Memory median; repetition range", "n", "Idle CPU, % of one core", "Acceptance and snapshots"].map((text) => el("th", { text })))),
        el("tbody", {}, rows))));
  });
  const abRows = OS_ORDER.flatMap((os) => {
    const summaries = data.paired_ab.filter((row) => row.platform === os);
    return (summaries.length ? summaries : [null]).map((row) => el("tr", {},
      el("th", { scope: "row", text: OS_NAME[os] }),
      el("td", { text: row?.primary_metric ?? "—" }),
      el("td", { class: "num", text: row ? `${numberOrNull(row.primary_delta_median_mib) > 0 ? "+" : ""}${value(row.primary_delta_median_mib, 3)}` : "Not measured" }),
      el("td", { class: "num", text: row ? `${value(row.primary_delta_min_mib, 3)}–${value(row.primary_delta_max_mib, 3)}` : "—" }),
      el("td", { class: "num", text: row ? value(row.paired_repetitions, 0) : "—" }),
      el("td", {}, row ? link(row.source_url, `Run ${row.run_id} · ${(row.source_commit ?? "").slice(0, 8)} · paired raw data`) : "No eligible same-run pairs"),
    ));
  });
  host.replaceChildren(el("h3", { text: "Current desktop evidence" }),
    el("p", { class: "section-lede", text: `Imported series: ${data.series}. Eligible measured invocations are separate from acceptance checks. A separate dark-startup failure remains visible even when a light-start measured invocation passed.` }),
    ...panels,
    el("h3", { text: "egui matched profile difference" }),
    el("p", { text: "Desktop-integrated after use minus diagnostic-reduced, paired on the same runner/repetition/source. This is the configured profile difference, not a clipboard-only or theme-only allocation. A small sample does not establish statistical significance." }),
    el("div", { class: "scroll-x" }, el("table", { class: "data" },
      el("thead", {}, el("tr", {}, ["OS", "Metric", "Median Δ, MiB", "Paired Δ range, MiB", "Pairs", "Evidence"].map((text) => el("th", { text })))),
      el("tbody", {}, abRows))),
    el("ul", { class: "desktop-limits" }, data.limitations.map((text) => el("li", { text }))),
    el("p", { class: "evidence-links" }, data.sources.map((source) => link(source.url, source.label))),
  );
}

/* ---------- Overview ---------- */
function renderOverview({ features, memory }) {
  const palettes = features.groups.flatMap((group) => group.features).find((feature) => feature.id === "color-palettes");
  const best = {};
  for (const os of OS_ORDER) {
    best[os] = Math.min(...features.frameworks.map((fw) => memory[fw.id]?.[os]?.median ?? Infinity));
  }
  const cards = features.frameworks.map((fw) => {
    const paletteLevel = palettes?.support[fw.id]?.level ?? "unknown";
    const paletteLabel = paletteLevel === "yes" ? "Supported" : features.levels[paletteLevel].label;
    const strip = el("div", { class: "mem-strip", "aria-label": "Historical UI-only idle memory in MiB" },
      OS_ORDER.map((os) => {
        const m = memory[fw.id]?.[os];
        const value = m ? fmt(m.median) : "—";
        const isBest = m && m.median === best[os];
        return el("div", { class: isBest ? "best" : null },
          el("span", { text: isBest ? `${OS_NAME[os]} · lowest` : OS_NAME[os] }),
          el("b", { text: value }), el("small", { text: " MiB" }),
        );
      }));
    return el("article", { class: "card fw" },
      el("header", {}, el("h3", { text: fw.name }), el("span", { class: "ver", title: "Versions in the historical matrix", text: fw.version })),
      el("p", { class: "model", text: fw.model }),
      el("p", { class: "profile-label", text: "Historical UI-only profile · 2026-11-09" }),
      strip,
      el("dl", {},
        el("dt", { text: "Language" }), el("dd", { text: fw.language }),
        el("dt", { text: "Licence" }), el("dd", { text: fw.license }),
        fw.desktop_profile ? el("dt", { text: "Default build" }) : null,
        fw.desktop_profile ? el("dd", { text: fw.desktop_profile }) : null,
        el("dt", { text: "Executable (old)" }), el("dd", { text: OS_ORDER.map((os) => {
          const b = memory[fw.id]?.[os]?.bytes;
          return b ? `${fmtSize(b)} ${OS_NAME[os]}` : null;
        }).filter(Boolean).join(" · ") }),
        el("dt", { text: "Light/dark palette" }), el("dd", { text: paletteLabel }),
        el("dt", { text: "Startup test (old)" }), el("dd", { text: OS_ORDER.map((os) =>
          `${OS_NAME[os]} ${startupLabel(memory[fw.id]?.[os]?.dark)}`).join(" · ") }),
      ),
      el("ul", { class: "pros", "aria-label": "Strengths" }, fw.strengths.map((s) => el("li", { text: s }))),
      el("ul", { class: "cons", "aria-label": "Limits" }, fw.limits.map((s) => el("li", { text: s }))),
      el("p", { class: "src" },
        el("a", { href: repoLink(fw.source), text: "Example source" }), " · ",
        el("a", { href: fw.home, text: "Project site" })),
    );
  });
  $("#overview-cards").replaceChildren(...cards);
}

/* ---------- Memory chart (small multiples, shared scale) ---------- */
function niceMax(v) {
  const step = v > 300 ? 100 : 50;
  return Math.ceil(v / step) * step;
}

function renderMemory({ features, memory }) {
  const fws = features.frameworks;
  const all = fws.flatMap((fw) => OS_ORDER.map((os) => memory[fw.id]?.[os]?.max ?? 0));
  const max = niceMax(Math.max(...all));
  const ticks = [];
  const step = max > 300 ? 100 : 50;
  for (let t = 0; t <= max; t += step) ticks.push(t);

  const W = 360, labelW = 104, valueW = 52, rowH = 34, top = 6, axisH = 22;
  const plotW = W - labelW - valueW;
  const H = top + fws.length * rowH + axisH;
  const x = (v) => labelW + (v / max) * plotW;

  const container = $("#memory-charts");
  container.replaceChildren();

  for (const os of OS_ORDER) {
    const metric = memory[fws[0].id]?.[os]?.metric ?? "";
    const best = Math.min(...fws.map((fw) => memory[fw.id]?.[os]?.median ?? Infinity));
    const panel = el("div", { class: "card panel" },
      el("h3", {}, OS_NAME[os], el("small", { text: `${metric}, MiB` })));
    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${OS_NAME[os]} historical UI-only idle memory by toolkit` });

    for (const t of ticks) {
      svg.append(svgEl("line", { class: t === 0 ? "baseline" : "gridline", x1: x(t), x2: x(t), y1: top - 2, y2: top + fws.length * rowH }));
      const tx = svgEl("text", { class: "tick", x: x(t), y: H - 6, "text-anchor": "middle" });
      tx.textContent = t;
      svg.append(tx);
    }

    const tip = el("div", { class: "tooltip", hidden: true, role: "tooltip" });

    fws.forEach((fw, i) => {
      const m = memory[fw.id]?.[os];
      if (!m) return;
      const y = top + i * rowH;
      const barH = 16;
      const by = y + (rowH - barH) / 2;
      const x0 = x(0), x1 = Math.max(x(m.median), x0 + 2);
      const r = Math.min(4, x1 - x0);
      const g = svgEl("g", { class: "row" });
      const label = svgEl("text", { class: "lbl", x: 0, y: y + rowH / 2 + 4.5 });
      label.textContent = fw.name.replace(" / eframe", "");
      // Square at the baseline, 4px rounded at the data end.
      const path = `M${x0},${by} H${x1 - r} Q${x1},${by} ${x1},${by + r} V${by + barH - r} Q${x1},${by + barH} ${x1 - r},${by + barH} H${x0} Z`;
      const bar = svgEl("path", { class: "bar", d: path });
      // Range of the repetition medians, drawn as a thin line through the bar end.
      const range = svgEl("line", { class: "range", x1: x(m.min), x2: x(m.max), y1: y + rowH / 2, y2: y + rowH / 2 });
      const val = svgEl("text", { class: `val${m.median === best ? " best" : ""}`, x: Math.max(x1, x(m.max)) + 6, y: y + rowH / 2 + 4 });
      val.textContent = fmt(m.median);
      const hit = svgEl("rect", {
        class: "bar-hit", x: 0, y, width: W, height: rowH, tabindex: 0,
        "aria-label": `${fw.name}: ${fmt(m.median, 2)} MiB on ${OS_NAME[os]}`,
      });
      const show = (evt) => {
        tip.replaceChildren(
          el("b", { text: fw.name }),
          el("dl", {},
            el("dt", { text: "Median" }), el("dd", { text: `${fmt(m.median, 2)} MiB` }),
            el("dt", { text: `${m.reps} runs` }), el("dd", { text: `${fmt(m.min, 2)}–${fmt(m.max, 2)}` }),
            el("dt", { text: m.rssMetric }), el("dd", { text: `${fmt(m.rss, 2)} MiB` }),
            el("dt", { text: "Idle CPU" }), el("dd", { text: m.cpu === 0 ? "0 recorded" : `${m.cpu.toFixed(4)} %` }),
            m.outliers ? el("dt", { text: "Outlier runs" }) : null, m.outliers ? el("dd", { text: m.outliers }) : null,
          ));
        tip.hidden = false;
        const pr = panel.getBoundingClientRect();
        const box = evt && evt.clientX ? { x: evt.clientX - pr.left, y: evt.clientY - pr.top }
          : { x: (x1 / W) * panel.clientWidth, y: ((y + rowH) / H) * svg.clientHeight + 40 };
        const left = Math.min(Math.max(8, box.x + 12), panel.clientWidth - tip.offsetWidth - 8);
        tip.style.left = `${left}px`;
        tip.style.top = `${box.y + 16}px`;
      };
      const hide = () => { tip.hidden = true; };
      hit.addEventListener("mousemove", show);
      hit.addEventListener("mouseleave", hide);
      hit.addEventListener("focus", () => show(null));
      hit.addEventListener("blur", hide);
      g.append(label, bar, range, val, hit);
      svg.append(g);
    });

    panel.append(svg, tip);
    container.append(panel);
  }

  // Table view, including CPU.
  const table = el("table", { class: "data" },
    el("thead", {}, el("tr", {},
      el("th", { text: "Toolkit" }),
      OS_ORDER.flatMap((os) => [
        el("th", { class: "num", text: `${OS_NAME[os]}, MiB` }),
        el("th", { class: "num", text: "range" }),
        el("th", { class: "num", text: "RSS" }),
        el("th", { class: "num", text: "CPU, %" }),
      ]))),
    el("tbody", {}, fws.map((fw) => el("tr", {},
      el("th", { scope: "row", text: fw.name }),
      OS_ORDER.flatMap((os) => {
        const m = memory[fw.id]?.[os];
        return [
          el("td", { class: "num", text: m ? fmt(m.median, 2) : "—" }),
          el("td", { class: "num", text: m ? `${fmt(m.min, 1)}–${fmt(m.max, 1)}` : "—" }),
          el("td", { class: "num", text: m ? fmt(m.rss, 1) : "—" }),
          el("td", { class: "num", text: m ? (m.cpu === 0 ? "0 recorded" : m.cpu.toFixed(5)) : "—" }),
        ];
      })))),
  );
  $("#memory-table").replaceChildren(table,
    el("p", { style: "font-size:.875rem;color:var(--muted)" },
      "Source: ", el("a", { href: repoLink(CSV_PATH), text: "summary.csv" }),
      ". Historical UI-only profile, 2026-11-09; medians of five runs on fresh VMs. RSS is the summed resident set or Working Set. Per-run rows are in runs.csv. These are not measurements of the current desktop-integrated builds."));
}

/* ---------- Screenshots ---------- */
function segmented(container, options, initial, onChange) {
  const buttons = options.map(([value, label]) => el("button", {
    type: "button", "aria-pressed": String(value === initial), "data-value": value, text: label,
    onclick: () => {
      for (const b of buttons) b.setAttribute("aria-pressed", String(b === buttons.find((x) => x.dataset.value === value)));
      onChange(value);
    },
  }));
  container.replaceChildren(...buttons);
}

function renderScreenshots({ features, memory }) {
  const gallery = $("#gallery");
  const dialog = $("#lightbox");
  let current = [];
  let index = 0;

  let scheme = "light";
  let currentOs = "linux";
  const shotPath = (fw, os) => {
    const m = memory[fw]?.[os];
    return m ? `screenshots/native-${m.run}/${m.runner}/${fw}${scheme === "dark" ? "-dark" : ""}.png` : null;
  };

  const open = (i) => {
    index = (i + current.length) % current.length;
    const s = current[index];
    $("#lightbox-img").src = s.src;
    $("#lightbox-img").alt = s.alt;
    $("#lightbox-caption").textContent = s.alt;
    if (!dialog.open) dialog.showModal();
  };
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close(); });
  dialog.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") open(index + 1);
    if (e.key === "ArrowLeft") open(index - 1);
  });
  for (const b of dialog.querySelectorAll("[data-step]")) b.addEventListener("click", () => open(index + Number(b.dataset.step)));
  $("#lightbox-close").addEventListener("click", () => dialog.close());

  const show = (os) => {
    current = features.frameworks.map((fw) => ({
      src: shotPath(fw.id, os),
      alt: `${fw.name} on ${OS_NAME[os]}, historical UI-only build${scheme === "dark" ? " relaunched with the system in dark mode" : " in the light run"}`,
      name: fw.name,
      mem: memory[fw.id]?.[os],
    })).filter((s) => s.src);
    gallery.replaceChildren(...current.map((s, i) => el("figure", { class: "card shot" },
      el("button", { type: "button", "aria-label": `Open ${s.alt} at full size`, onclick: () => open(i) },
        el("img", { src: s.src, alt: s.alt, loading: "lazy", width: 960, height: 640 })),
      el("figcaption", {}, s.name, el("span", { text: !s.mem ? "" : scheme === "dark"
        ? `Startup test: ${startupLabel(s.mem.dark)}` : `${fmt(s.mem.median)} MiB · old profile` })),
    )));
  };
  const redraw = () => show(currentOs);
  segmented($("#shot-os"), OS_ORDER.map((os) => [os, OS_NAME[os]]), "linux", (os) => { currentOs = os; redraw(); });
  segmented($("#shot-scheme"), [["light", "Light run"], ["dark", "Relaunched in dark mode"]], "light", (v) => { scheme = v; redraw(); });
  show("linux");
}

/* ---------- Feature matrix ---------- */
function levelDot(level, levels, withLabel = false) {
  const info = levels[level];
  const dot = el("span", { class: `dot ${level}`, "aria-hidden": "true" });
  if (!withLabel) return el("span", { class: "lvl", title: info.label }, dot, el("span", { class: "sr-only", text: info.label }));
  return el("span", { class: "lvl" }, dot, el("span", { class: "lbl", text: info.label }));
}

function levelFor(cell, os) {
  if (os === "all") return cell.level;
  return cell.os?.[os] ?? cell.level;
}

function renderFeatures({ features }) {
  const { levels, frameworks, groups } = features;
  const matrix = $("#matrix");
  const detail = $("#detail");
  let osFilter = "all";
  let selected = null;

  $("#features-lede").textContent += ` Checked ${features.checked}.`;
  $("#capability-count").textContent = groups.reduce((sum, group) => sum + group.features.filter((feat) => feat.kind !== "text").length, 0);
  $("#legend").replaceChildren(...Object.keys(levels).map((k) => el("li", {}, levelDot(k, levels, true))));

  const showDetail = (fw, feat) => {
    const cell = feat.support[fw.id];
    const perOs = cell.os
      ? el("ul", { class: "per-os" }, ["windows", "macos", "linux"].filter((os) => cell.os[os]).map((os) =>
        el("li", {}, el("b", { text: `${OS_NAME[os]}: ` }), levelDot(cell.os[os], levels, true))))
      : el("ul", { class: "per-os" }, el("li", {}, el("b", { text: "All systems: " }), levelDot(cell.level, levels, true)));
    const ev = cell.evidence === "repo" ? "This repository" : "Upstream documentation";
    detail.replaceChildren(
      el("h3", { text: `${fw.name} — ${feat.title}` }),
      el("p", { text: feat.description }),
      perOs,
      el("p", { text: cell.note }),
      el("p", { class: "ev" }, `Evidence: ${ev} · `, el("a", { href: repoLink(cell.source), text: "source" })),
    );
  };

  const draw = () => {
    const head = el("thead", {}, el("tr", {},
      el("th", { scope: "col", text: "Capability or scoped check" }),
      frameworks.map((fw) => el("th", { scope: "col", text: fw.name }))));
    const body = el("tbody");
    for (const group of groups) {
      body.append(el("tr", { class: "group" }, el("th", { colspan: frameworks.length + 1, scope: "colgroup", text: group.title })));
      for (const feat of group.features) {
        const row = el("tr", {}, el("th", { scope: "row" }, feat.title, el("small", { text: feat.description })));
        for (const fw of frameworks) {
          const cell = feat.support[fw.id];
          const key = `${feat.id}/${fw.id}`;
          let content;
          let aria;
          if (feat.kind === "text") {
            content = el("span", { class: "txt", text: cell.text });
            aria = `${fw.name}, ${feat.title}: ${cell.text}`;
          } else if (osFilter === "all" && cell.os && new Set(Object.values(cell.os)).size > 1) {
            content = el("span", { class: "os-marks" }, ["windows", "macos", "linux"].filter((os) => cell.os[os]).map((os) =>
              el("span", { class: "os-mark" }, levelDot(cell.os[os], levels), { windows: "Win", macos: "mac", linux: "Linux" }[os])));
            aria = `${fw.name}, ${feat.title}: ` + Object.entries(cell.os).map(([os, lv]) => `${OS_NAME[os]} ${levels[lv].label}`).join(", ");
          } else {
            const lv = levelFor(cell, osFilter);
            content = levelDot(lv, levels, true);
            aria = `${fw.name}, ${feat.title}: ${levels[lv].label}`;
          }
          const btn = el("button", {
            type: "button", class: "cell", "aria-label": `${aria}. Show details`, "aria-expanded": String(selected === key),
            onclick: () => {
              if (feat.kind === "text") {
                detail.replaceChildren(el("h3", { text: `${fw.name} — ${feat.title}` }), el("p", { text: cell.text }),
                  el("p", { class: "ev" }, el("a", { href: repoLink(cell.source), text: "source" })));
              } else showDetail(fw, feat);
              selected = key;
              detail.scrollIntoView({ block: "nearest", behavior: "smooth" });
              for (const b of matrix.querySelectorAll(".cell")) b.setAttribute("aria-expanded", "false");
              btn.setAttribute("aria-expanded", "true");
            },
          }, content);
          row.append(el("td", {}, btn));
        }
        body.append(row);
      }
    }
    const cols = el("colgroup", {}, el("col", { class: "cap" }), frameworks.map(() => el("col")));
    matrix.replaceChildren(cols, head, body);
  };

  segmented($("#feature-os"), [["all", "All systems"], ["windows", "Windows"], ["macos", "macOS"], ["linux", "Linux"]], "all", (v) => { osFilter = v; draw(); });
  draw();
}

/* ---------- Code tabs ---------- */
function initCodeTabs() {
  const tabs = [...document.querySelectorAll("#code-tabs [data-code]")];
  const panels = [...document.querySelectorAll("[data-panel]")];
  for (const tab of tabs) {
    tab.addEventListener("click", () => {
      for (const t of tabs) {
        const on = t === tab;
        t.setAttribute("aria-pressed", String(on));
        t.setAttribute("aria-selected", String(on));
      }
      for (const p of panels) p.hidden = p.dataset.panel !== tab.dataset.code;
    });
  }
}

/* ---------- Nav highlight ---------- */
function initNav() {
  const links = [...document.querySelectorAll(".nav a")];
  const map = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
  const obs = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      for (const a of links) a.removeAttribute("aria-current");
      map.get(e.target.id)?.setAttribute("aria-current", "true");
    }
  }, { rootMargin: "-40% 0px -55% 0px" });
  for (const id of map.keys()) { const s = document.getElementById(id); if (s) obs.observe(s); }
}

initCodeTabs();
initNav();
load().then((data) => {
  renderOverview(data);
  renderMemory(data);
  renderScreenshots(data);
  renderFeatures(data);
}).catch((err) => {
  const msg = el("p", { class: "error" }, `Could not load data (${err.message}). Browse it on `, el("a", { href: REPO, text: "GitHub" }), ".");
  $("#overview-cards").replaceChildren(msg);
});
// Fetch/render separately: optional fresh results never block the historical page.
loadDesktop().then(renderDesktop).catch(() => {});
