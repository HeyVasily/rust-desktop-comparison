"use strict";

// Run with `node --test site/app.test.cjs`; no browser packages are required.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "app.js"), "utf8");
const bootstrap = source.indexOf("\ninitCodeTabs();");
assert.ok(bootstrap > 0, "site bootstrap must remain separate from data helpers");

function context(globals = {}) {
  const scope = vm.createContext(globals);
  vm.runInContext(source.slice(0, bootstrap), scope);
  return scope;
}

test("theme evidence distinguishes false from missing or unknown", () => {
  const scope = context();
  for (const [input, expected] of [["True", true], ["False", false], ["", null], ["None", null], [undefined, null]]) {
    scope.input = input;
    assert.equal(vm.runInContext("parseBoolean(input)", scope), expected);
  }
});

test("startup labels describe a scoped test, not theme capability", () => {
  const scope = context();
  for (const [input, expected] of [[true, "passed"], [false, "failed"], [null, "not tested"], [undefined, "not tested"]]) {
    scope.input = input;
    assert.equal(vm.runInContext("startupLabel(input)", scope), expected);
  }
});

test("historical loader preserves a not-tested startup value", async () => {
  const csv = [
    "phase,framework,os,primary_median_mib,follows_dark_mode",
    "comparison,egui,ubuntu-24.04,45,False",
    "comparison,gtk,ubuntu-24.04,60,",
    "comparison,slint,ubuntu-24.04,20,True",
    "warmup,egui,ubuntu-24.04,999,True",
  ].join("\n");
  const scope = context({
    fetch: async () => ({ ok: true, json: async () => ({ frameworks: [] }), text: async () => csv }),
  });
  const { memory } = await vm.runInContext("load()", scope);
  assert.equal(memory.egui.linux.dark, false);
  assert.equal(memory.gtk.linux.dark, null);
  assert.equal(memory.slint.linux.dark, true);
  assert.equal(memory.egui.linux.median, 45);
});

test("matrix separates historical test results from palette capability", () => {
  const data = JSON.parse(fs.readFileSync(path.join(__dirname, "../data/features.json"), "utf8"));
  const features = data.groups.flatMap((group) => group.features);
  const startup = features.find((feature) => feature.id === "dark-mode");
  const palette = features.find((feature) => feature.id === "color-palettes");
  assert.match(startup.title, /Historical.*startup/);
  for (const id of ["egui", "gtk"]) {
    assert.equal(palette.support[id].level, "yes");
  }
  for (const cell of Object.values(startup.support)) {
    for (const level of [cell.level, ...Object.values(cell.os ?? {})]) {
      assert.ok(["pass", "fail", "partial", "unknown"].includes(level), `not a test-outcome level: ${level}`);
    }
  }
  assert.ok(features.some((feature) => feature.id === "clipboard-text"));
  assert.match(data.frameworks.find((framework) => framework.id === "gtk").desktop_profile, /libadwaita/);
});

test("page supplies each selector used by the data-driven sections", () => {
  const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(new Set(ids).size, ids.length, "element IDs must be unique");
  for (const match of source.matchAll(/\$\("#([^" ]+)"\)/g)) {
    assert.ok(ids.includes(match[1]), `missing element #${match[1]}`);
  }
  for (const match of html.matchAll(/href="#([^"]+)"/g)) {
    assert.ok(ids.includes(match[1]), `missing navigation target #${match[1]}`);
  }
  assert.ok(ids.includes("desktop-evidence"), "current profile evidence must be prominent");
});

test("optional desktop data failures do not break the historical loader", async () => {
  const csv = "phase,framework,os,primary_median_mib,follows_dark_mode\ncomparison,egui,ubuntu-24.04,45,False";
  const scope = context({ fetch: async (url) => url.endsWith("desktop-results.json")
    ? { ok: false, status: 404 } : { ok: true, json: async () => ({ frameworks: [] }), text: async () => csv } });
  assert.equal(await vm.runInContext("loadDesktop()", scope), null);
  assert.equal((await vm.runInContext("load()", scope)).memory.egui.linux.median, 45);
  for (const fetch of [async () => { throw new Error("offline"); }, async () => ({ ok: true, json: async () => ({ schema_version: 999 }) })]) {
    assert.equal(await vm.runInContext("loadDesktop()", context({ fetch })), null);
  }
});

test("missing numeric evidence does not become zero", () => {
  const scope = context();
  for (const input of [undefined, null, "", " ", false, NaN, Infinity]) {
    scope.input = input;
    assert.equal(vm.runInContext("numberOrNull(input)", scope), null);
  }
  for (const input of [0, "0", "0.00000"]) {
    scope.input = input;
    assert.equal(vm.runInContext("numberOrNull(input)", scope), 0);
  }
});

test("full acceptance label requires separate dark startup and every check", () => {
  const scope = context({ acceptance: { status: "fully_verified", startup_light: "passed", startup_dark: "passed",
    live_theme: "passed", clipboard: "passed", cleanup: "passed", process_cleanup: "passed", evidence: "passed", provenance: "passed" } });
  assert.equal(vm.runInContext("acceptanceLabel(acceptance)", scope), "Fully verified");
  scope.acceptance.startup_dark = "not_run";
  assert.equal(vm.runInContext("acceptanceLabel(acceptance)", scope), "Incomplete evidence");
  scope.acceptance.startup_dark = "passed";
  delete scope.acceptance.process_cleanup;
  assert.equal(vm.runInContext("acceptanceLabel(acceptance)", scope), "Incomplete evidence");
  scope.acceptance.status = "environment_error";
  assert.equal(vm.runInContext("acceptanceLabel(acceptance)", scope), "Environment blocked");
});

function rendererContext(data) {
  class Node {
    constructor(tag) { this.tag = tag; this.children = []; this.attributes = {}; this.ownText = ""; }
    set textContent(value) { this.ownText = String(value); this.children = []; }
    get textContent() { return this.ownText + this.children.map((child) => typeof child === "string" ? child : child.textContent).join(" "); }
    setAttribute(key, value) { this.attributes[key] = value; }
    addEventListener() {}
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; this.ownText = ""; }
  }
  const host = new Node("div");
  host.textContent = "Static fallback";
  const scope = context({ data, document: { querySelector: () => host, createElement: (tag) => new Node(tag) } });
  return { scope, host };
}

function desktopFixture() {
  return { schema_version: 1, series: "synthetic-test-only", sources: [], limitations: [], paired_ab: [],
    platforms: [{ id: "linux", name: "Linux", candidates: [{ framework: "egui", name: "egui / eframe", experiments: [] }] }] };
}

test("renderer leaves static notice when optional data is absent", () => {
  const { scope, host } = rendererContext(null);
  vm.runInContext("renderDesktop(data)", scope);
  assert.equal(host.textContent, "Static fallback");
});

test("renderer keeps failed and missing candidates visible without zero MiB", () => {
  const data = desktopFixture();
  data.platforms[0].candidates.push({ framework: "gtk", name: "GTK4 + libadwaita", experiments: [{
    identity: { os: "ubuntu-24.04", run_id: "123", source_commit: "a".repeat(40) }, links: {}, measurements: [], invocations: [],
    acceptance: { status: "failed", clipboard: "failed" },
  }] });
  const { scope, host } = rendererContext(data);
  vm.runInContext("renderDesktop(data)", scope);
  assert.match(host.textContent, /egui \/ eframe/);
  assert.match(host.textContent, /GTK4 \+ libadwaita/);
  assert.match(host.textContent, /Failed invocation/);
  assert.match(host.textContent, /Not measured/);
  assert.match(host.textContent, /Not run/);
  assert.doesNotMatch(host.textContent, /0\.00 MiB/);
});

test("renderer distinguishes measured n from acceptance invocations and keeps metric names", () => {
  const data = desktopFixture();
  data.platforms[0].candidates[0].experiments = [{
    identity: { os: "ubuntu-24.04", run_id: "123", source_commit: "a".repeat(40) }, links: {}, invocations: [],
    measurements: [{ primary_metric: "Linux PSS", primary_median_mib: "123.45", primary_min_mib: "120.10",
      primary_max_mib: "126.09", repetitions: "3", cpu_median_percent: "0.00000" }],
    acceptance: { status: "incomplete", normal_invocations: 3, dark_invocations: 0 },
  }];
  const { scope, host } = rendererContext(data);
  vm.runInContext("renderDesktop(data)", scope);
  assert.match(host.textContent, /123\.45 MiB/);
  assert.match(host.textContent, /Linux PSS; 120\.10–126\.09 MiB/);
  assert.match(host.textContent, /0 recorded/);
  assert.match(host.textContent, /Acceptance invocations: 3 normal \/ 0 dark-startup/);
  assert.match(host.textContent, /not the memory sample count/);
  assert.match(host.textContent, /configured profile difference, not a clipboard-only/);
});
