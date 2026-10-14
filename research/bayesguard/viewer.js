(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("bg-data").textContent);
  const $ = (id) => document.getElementById(id);
  const svgNS = "http://www.w3.org/2000/svg";
  const defaultNotes = {
    login_ok: "Successful sign-in. Common in ordinary sessions.",
    list_objects: "Lists cloud objects. Usually routine by itself.",
    read_object: "Reads one cloud object. Often normal activity.",
    logout: "Session ends or changes context.",
    list_users: "Enumerates identities. Can be administration or reconnaissance.",
    login_fail: "Failed sign-in. Repeated failures strengthen credential-abuse evidence.",
    assume_role: "Switches privileges. Could be authorized administration or escalation.",
    read_secret: "Accesses a secret. Sensitive, but sometimes legitimate.",
    bulk_download: "Downloads many objects. Could be backup work or exfiltration."
  };
  const defaultStateNames = {
    normal: "Normal", recon: "Recon", credential: "Credential",
    privilege: "Privilege", exfil: "Exfiltration"
  };
  const notes = data.notes || defaultNotes;
  const stateNames = data.state_names || defaultStateNames;
  const phaseLabel = data.phase_label || "attack";
  const eventFallback = data.event_fallback || "Cloud audit event";
  let scenarioIndex = Math.max(0, data.scenarios.findIndex(s => s.attack_start !== null));
  let step = 0;
  let threshold = data.threshold;
  let streak = data.streak;
  let timer = null;
  let plotLayout = null;

  function nice(name) { return name.replaceAll("_", " "); }
  function current() { return data.scenarios[scenarioIndex]; }
  function percent(value) { return (value * 100).toFixed(1) + "%"; }
  function alertFlags(events) {
    let count = 0;
    return events.map(event => {
      count = event.risk >= threshold ? count + 1 : 0;
      return count >= streak;
    });
  }
  function stop() {
    if (timer !== null) clearInterval(timer);
    timer = null;
    $("play").textContent = "▶ Play";
  }
  function svgElement(name, attributes, parent) {
    const element = document.createElementNS(svgNS, name);
    for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
    parent.appendChild(element);
    return element;
  }

  function drawPlot(scenario, flags) {
    const svg = $("risk-plot");
    const width = Math.max(320, Math.round(svg.clientWidth || 700));
    const height = 266;
    const left = 44, right = width - 15, top = 13, bottom = 215;
    const count = scenario.events.length;
    const x = i => left + (right - left) * i / Math.max(1, count - 1);
    const y = risk => bottom - (bottom - top) * risk;
    plotLayout = { left, right, count, width };
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("aria-label", `${scenario.id}: risk across ${count} events, with alert threshold ${percent(threshold)}`);
    svg.replaceChildren();

    if (scenario.attack_start !== null) {
      const attackX = x(scenario.attack_start);
      svgElement("rect", { x: attackX, y: top, width: Math.max(0, right - attackX),
        height: bottom - top, fill: "var(--attack-soft)" }, svg);
    }
    for (const value of [0, .5, 1]) {
      const yy = y(value);
      svgElement("line", { x1: left, x2: right, y1: yy, y2: yy,
        stroke: "var(--line)", "stroke-width": 1 }, svg);
      const label = svgElement("text", { x: 2, y: yy + 4,
        fill: "var(--muted)", "font-size": 11 }, svg);
      label.textContent = `${Math.round(value * 100)}%`;
    }
    const thresholdY = y(threshold);
    svgElement("line", { x1: left, x2: right, y1: thresholdY, y2: thresholdY,
      stroke: "var(--threshold)", "stroke-width": 2, "stroke-dasharray": "6 5" }, svg);
    const points = scenario.events.map((event, i) => `${x(i)},${y(event.risk)}`).join(" ");
    svgElement("polygon", { points: `${left},${bottom} ${points} ${right},${bottom}`,
      fill: "var(--risk-soft)" }, svg);
    svgElement("polyline", { points, fill: "none", stroke: "var(--risk)",
      "stroke-width": 3, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    if (scenario.attack_start !== null) {
      const attackX = x(scenario.attack_start);
      svgElement("line", { x1: attackX, x2: attackX, y1: top, y2: bottom,
        stroke: "var(--attack)", "stroke-width": 1.5, "stroke-dasharray": "3 4" }, svg);
      if (attackX > left + 65 && attackX < right - 65) {
        const label = svgElement("text", { x: attackX + 5, y: top + 12,
          fill: "var(--attack)", "font-size": 11 }, svg);
        label.textContent = `${phaseLabel} begins`;
      }
    }
    flags.forEach((flag, i) => {
      if (flag && (i === 0 || !flags[i - 1])) {
        svgElement("rect", { x: x(i) - 5, y: y(scenario.events[i].risk) - 5,
          width: 10, height: 10,
          transform: `rotate(45 ${x(i)} ${y(scenario.events[i].risk)})`,
          fill: "var(--bg)", stroke: "var(--alert)", "stroke-width": 2 }, svg);
      }
    });
    svgElement("line", { x1: x(step), x2: x(step), y1: top, y2: bottom,
      stroke: "var(--text)", "stroke-width": 1, "stroke-opacity": .45 }, svg);
    svgElement("circle", { cx: x(step), cy: y(scenario.events[step].risk), r: 6,
      fill: "var(--risk)", stroke: "var(--surface)", "stroke-width": 2 }, svg);
    const first = svgElement("text", { x: left, y: height - 10,
      fill: "var(--muted)", "font-size": 11, "text-anchor": "start" }, svg);
    first.textContent = "event 1";
    const last = svgElement("text", { x: right, y: height - 10,
      fill: "var(--muted)", "font-size": 11, "text-anchor": "end" }, svg);
    last.textContent = `event ${count}`;
  }

  function drawStates(posterior) {
    const list = $("stage-bars");
    list.replaceChildren();
    data.states.forEach((name, i) => {
      const row = document.createElement("div");
      row.className = "stage-row";
      const label = document.createElement("span");
      label.textContent = stateNames[name] || nice(name);
      const track = document.createElement("div");
      track.className = "bar-track";
      const fill = document.createElement("div");
      fill.className = "bar-fill";
      fill.style.width = percent(posterior[i]);
      track.appendChild(fill);
      const value = document.createElement("strong");
      value.textContent = `${Math.round(posterior[i] * 100)}%`;
      row.append(label, track, value);
      list.appendChild(row);
    });
  }

  function drawStream(scenario, flags) {
    const stream = $("event-stream");
    stream.replaceChildren();
    scenario.events.forEach((event, i) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "event-chip";
      if (scenario.attack_start !== null && i >= scenario.attack_start) button.classList.add("attack-phase");
      if (flags[i] && (i === 0 || !flags[i - 1])) button.classList.add("alert-phase");
      if (i === step) button.classList.add("selected");
      button.setAttribute("aria-label", `Event ${i + 1}: ${nice(event.kind)}, risk ${percent(event.risk)}${flags[i] ? ", alert" : ""}`);
      const number = document.createElement("small");
      number.textContent = `#${i + 1}`;
      button.append(number, document.createTextNode(nice(event.kind)));
      button.addEventListener("click", () => { stop(); step = i; render(); });
      stream.appendChild(button);
    });
  }

  function summary(scenario, flags) {
    const firstAlert = flags.findIndex(Boolean);
    const start = scenario.attack_start;
    if (scenario.label === "unlabeled") {
      return firstAlert < 0 ? "Imported session · no model alert under this rule; ground truth is unknown."
        : `Imported session · first model alert at event ${firstAlert + 1}; ground truth is unknown.`;
    }
    if (start === null) {
      return firstAlert < 0 ? "Benign session · no alert under this policy."
        : `Benign session · first alert at event ${firstAlert + 1} (a false positive).`;
    }
    if (firstAlert < 0) return `Simulated ${phaseLabel} begins at event ${start + 1} · no alert under this policy.`;
    if (firstAlert < start) return `Simulated ${phaseLabel} begins at event ${start + 1} · alert at event ${firstAlert + 1}, before the ${phaseLabel} starts.`;
    return `Simulated ${phaseLabel} begins at event ${start + 1} · first alert at event ${firstAlert + 1} (${firstAlert - start} events later).`;
  }

  function render() {
    const scenario = current();
    step = Math.max(0, Math.min(step, scenario.events.length - 1));
    const event = scenario.events[step];
    const flags = alertFlags(scenario.events);
    $("threshold").value = threshold;
    $("threshold-value").textContent = percent(threshold);
    $("streak").value = String(streak);
    $("step").max = String(scenario.events.length - 1);
    $("step").value = String(step);
    $("step-value").textContent = `${step + 1} / ${scenario.events.length}`;
    $("step-label").textContent = `${scenario.id} · ${scenario.label || (scenario.attack_start === null ? "benign" : phaseLabel)} session · event ${step + 1}`;
    $("event-name").textContent = nice(event.kind);
    $("event-note").textContent = notes[event.kind] || eventFallback;
    $("risk-value").textContent = percent(event.risk);
    const alert = $("alert-status");
    alert.textContent = flags[step] ? "ALERT" : "No alert";
    alert.className = flags[step] ? "is-alert" : "is-safe";
    $("session-summary").textContent = summary(scenario, flags);
    drawPlot(scenario, flags);
    drawStates(event.posterior);
    drawStream(scenario, flags);
  }

  const sessionSelect = $("session-select");
  data.scenarios.forEach((scenario, i) => {
    const option = document.createElement("option");
    option.value = String(i);
    option.textContent = `${scenario.id} · ${scenario.label || (scenario.attack_start === null ? "benign" : phaseLabel)}`;
    sessionSelect.appendChild(option);
  });
  sessionSelect.value = String(scenarioIndex);
  sessionSelect.addEventListener("change", () => {
    stop(); scenarioIndex = Number(sessionSelect.value); step = 0; render();
  });
  $("threshold").addEventListener("input", event => {
    threshold = Number(event.target.value); render();
  });
  $("streak").addEventListener("change", event => {
    streak = Number(event.target.value); render();
  });
  $("step").addEventListener("input", event => {
    stop(); step = Number(event.target.value); render();
  });
  $("play").addEventListener("click", () => {
    if (timer !== null) { stop(); return; }
    if (step >= current().events.length - 1) step = 0;
    $("play").textContent = "Ⅱ Pause";
    render();
    timer = setInterval(() => {
      if (step >= current().events.length - 1) { stop(); return; }
      step += 1;
      render();
    }, 700);
  });
  $("risk-plot").addEventListener("click", event => {
    if (!plotLayout) return;
    const box = event.currentTarget.getBoundingClientRect();
    const px = (event.clientX - box.left) * plotLayout.width / box.width;
    const fraction = (px - plotLayout.left) / (plotLayout.right - plotLayout.left);
    stop();
    step = Math.max(0, Math.min(plotLayout.count - 1, Math.round(fraction * (plotLayout.count - 1))));
    render();
  });
  new ResizeObserver(() => drawPlot(current(), alertFlags(current().events))).observe($("risk-plot"));
  render();
})();
