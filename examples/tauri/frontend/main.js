// Synthetic UI only: persistent DOM, in-memory fixture, no timers or network.
"use strict";

const state = { yard: 0, project: 0, refreshes: 0 };
const projectName = (project) => `project-${String(project + 1).padStart(3, "0")}`;
const yardName = (yard) => `yard-${String(yard).padStart(2, "0")}`;
const filter = document.getElementById("filter");
const projectRows = [];
const yardButtons = [];

function selectProject(project) {
  state.project = project;
  document.getElementById("project-name").textContent = projectName(project);
  document.getElementById("project-yard").textContent = yardName(Math.floor(project / 10) + 1);
  projectRows.forEach((row, index) => row.setAttribute("aria-pressed", String(index === project)));
}

function updateFilter() {
  projectRows.forEach((row, project) => {
    row.hidden = (state.yard !== 0 && Math.floor(project / 10) + 1 !== state.yard)
      || !projectName(project).includes(filter.value);
  });
}

function selectYard(yard) {
  state.yard = yard;
  document.getElementById("list-title").textContent = yard === 0 ? "All projects" : yardName(yard);
  document.getElementById("all-projects").setAttribute("aria-pressed", String(yard === 0));
  yardButtons.forEach((button, index) => button.setAttribute("aria-pressed", String(index + 1 === yard)));
  if (yard > 0) selectProject((yard - 1) * 10);
  updateFilter();
  document.getElementById("projects").scrollTop = 0;
}

for (let yard = 1; yard <= 10; yard += 1) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = `${yardName(yard)}     10 projects`;
  button.setAttribute("aria-pressed", "false");
  button.addEventListener("click", () => selectYard(yard));
  document.getElementById("yards").append(button);
  yardButtons.push(button);
}

for (let project = 0; project < 100; project += 1) {
  const row = document.createElement("button");
  row.type = "button";
  row.className = "project";
  const name = document.createElement("span");
  name.textContent = projectName(project);
  const status = document.createElement("span");
  status.textContent = "NOT_CREATED";
  row.append(name, status);
  row.addEventListener("click", () => selectProject(project));
  document.getElementById("projects").append(row);
  projectRows.push(row);
}

filter.addEventListener("input", updateFilter);
document.getElementById("all-projects").addEventListener("click", () => selectYard(0));
document.getElementById("refresh").addEventListener("click", () => {
  state.refreshes += 1;
  document.getElementById("snapshot").textContent = `Snapshot ${state.refreshes} · local fixture`;
});
selectProject(0);
document.getElementById("refresh").focus();
