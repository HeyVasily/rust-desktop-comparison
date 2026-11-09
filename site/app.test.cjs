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
