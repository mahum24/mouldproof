const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });

const EXAMPLE_STORY = "I rent a flat from Clarion Housing. I first reported black mould in my son's bedroom and around the windows by phone on 14 September, and chased it by email on 1 October. Nobody has come to inspect yet. My son is 4 and has asthma and has been coughing at night. I also have a 9-month-old baby.";
const EXAMPLE_PHOTOS = ["wall", "window", "corner"];

let photos = [], letters = { letter: "", complaint: "" }, tab = "letter", started;

function renderThumbs() {
  $("#thumbs").innerHTML = photos.map((f, i) =>
    `<figure><img src="${URL.createObjectURL(f)}" alt="Photo ${i + 1}"><figcaption>${i + 1}</figcaption><button type="button" data-rm="${i}" aria-label="Remove">×</button></figure>`).join("");
}
function addFiles(files) {
  photos = [...photos, ...[...files].filter((f) => f.type.startsWith("image/"))].slice(0, 4);
  renderThumbs();
}
$("#file").addEventListener("change", (e) => addFiles(e.target.files));
$("#thumbs").addEventListener("click", (e) => {
  if (e.target.dataset.rm) { photos.splice(+e.target.dataset.rm, 1); renderThumbs(); }
});
const drop = $("#drop");
["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => addFiles(e.dataTransfer.files));

$("#example").addEventListener("click", async () => {
  photos = await Promise.all(EXAMPLE_PHOTOS.map(async (n) =>
    new File([await (await fetch(`/static/samples/${n}.jpg`)).blob()], `${n}.jpg`, { type: "image/jpeg" })));
  renderThumbs();
  $("#story").value = EXAMPLE_STORY;
});

$("#form").addEventListener("submit", async (e) => {
  e.preventDefault();
  reset();
  $("#go").disabled = true; $("#go").textContent = "Building your case…";
  started = performance.now();
  const fd = new FormData();
  fd.append("story", $("#story").value);
  photos.forEach((p) => fd.append("photos", p));
  if (!photos.length) document.querySelector('[data-step="inspect"]').className = "skipped";
  try {
    const res = await fetch("/api/analyze", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || `Error ${res.status}`);
    const reader = res.body.getReader(), dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, i).replace(/^data: /, ""); buf = buf.slice(i + 2);
        if (line.trim()) handle(JSON.parse(line));
      }
    }
  } catch (err) { showError(err.message); }
  $("#go").disabled = false; $("#go").textContent = "Build my case";
});

const state = {};
function reset() {
  Object.keys(state).forEach((k) => delete state[k]);
  document.querySelectorAll("#steps li").forEach((li) => { li.className = ""; li.querySelector(".t")?.remove(); });
  ["#error", "#results", "#routing"].forEach((s) => $(s).classList.add("hidden"));
}
function showError(m) { $("#error").textContent = m; $("#error").classList.remove("hidden"); }

function handle(ev) {
  const li = document.querySelector(`#steps li[data-step="${ev.step}"]`);
  if (li) {
    li.className = ev.status;
    if (ev.status === "running") li.dataset.t0 = performance.now();
    if (ev.status === "done") {
      const t = document.createElement("span"); t.className = "t";
      t.textContent = `${((performance.now() - li.dataset.t0) / 1000).toFixed(1)}s`; li.appendChild(t);
    }
  }
  if (ev.status === "error") return showError(ev.message);
  if (ev.status !== "done") return;
  state[ev.step] = ev.result;
  if (ev.step === "complete") render(ev.result);
}

const SEV = {
  emergency: ["Emergency", "24-hour duty"],
  significant: ["Significant hazard", "Awaab's Law applies"],
  not_significant: ["Lower risk", "still report it"],
  unclear: ["Unclear", "more evidence needed"],
};

function render(done) {
  ["facts", "record", "verify", "letters"].forEach((s) => {
    if (!state[s]) document.querySelector(`#steps li[data-step="${s}"]`)?.classList.add("skipped");
  });
  const a = state.assess, c = state.clock, sev = SEV[a.classification] || SEV.unclear;
  $("#vBadge").className = `badge-big sev-${a.classification}`;
  $("#vBadge").innerHTML = `${sev[0]}<small>${sev[1]} · ${esc(a.confidence)} confidence</small>`;
  $("#vHead").textContent = a.headline;
  $("#vScope").textContent = c.scope.why;

  $("#guidance").href = c.guidance_url;
  if (c.items.length) {
    const overdue = c.items.filter((i) => i.status === "overdue").length;
    $("#clockSince").textContent = `Reported ${fmt(c.reported)} · ${c.working_days_since_report} working days ago${overdue ? ` · ${overdue} deadline${overdue > 1 ? "s" : ""} missed` : ""}`;
    $("#timeline").innerHTML = c.items.map((i) => `<li class="${i.status}">
      <div class="st">${i.status === "overdue" ? `Overdue · ${i.days_overdue} working days` : i.status}</div>
      <b>${esc(i.label)}</b><div class="due">${fmt(i.due)}</div><div class="rule">${esc(i.rule)}</div></li>`).join("");
  } else {
    $("#clockSince").textContent = "";
    $("#timeline").innerHTML = `<p class="empty">${!c.reported ? "Tell us the date you first reported the problem to your landlord to see the deadlines." : c.scope.covered === false ? "The Awaab's Law clock doesn't apply here; see the route above." : "No Awaab's Law deadline applies at this hazard level, but your landlord must still deal with repairs."}</p>`;
  }

  const ph = state.inspect?.photos || [];
  $("#photoFindings").innerHTML = ph.length ? ph.map((p, i) => `<div class="item">
      ${photos[i] ? `<img src="${URL.createObjectURL(photos[i])}" alt="">` : "<div></div>"}
      <div><b>${esc(p.location)}</b><p>${esc(p.what_is_visible)}</p>
      <p>Extent: ${esc(p.extent)} · Likely cause: ${esc(p.likely_cause)}</p>
      <div class="tags">${(p.signs || []).map((s) => `<span>${esc(s)}</span>`).join("")}</div></div></div>`).join("")
    + `<p class="overall">${esc(state.inspect.overall)}</p>` : `<p class="empty">No photos added. Photos make your case much stronger.</p>`;

  $("#reasons").innerHTML = (a.reasons || []).map((r) => `<li>${esc(r)}</li>`).join("");
  $("#safety").innerHTML = (a.safety_now || []).map((r) => `<li>${esc(r)}</li>`).join("");
  $("#gaps").innerHTML = (a.evidence_gaps || []).map((r) => `<li>${esc(r)}</li>`).join("");

  const rec = state.verify;
  if (rec) {
    $("#recordCard").classList.remove("hidden");
    $("#recordTitle").textContent = `${rec.landlord}'s record`;
    $("#record").innerHTML = rec.findings.length ? rec.findings.map((f) => `<li><span class="k">${esc(f.kind)}</span>
      <div>${esc(f.summary)}<a class="src" href="${esc(f.url)}" target="_blank" rel="noopener">✓ Verified: ${esc(f.source_title)}</a></div></li>`).join("")
      : `<p class="empty">We couldn't find verified Ombudsman findings or news about this landlord.</p>`;
  } else $("#recordCard").classList.add("hidden");

  letters = state.letters;
  $("#complaintTab").classList.toggle("hidden", !letters.complaint);
  showTab("letter");
  renderRouting(done.usage);
  $("#results").classList.remove("hidden");
  $("#results").scrollIntoView({ behavior: "smooth" });
}

function showTab(t) {
  tab = t;
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("on", b.dataset.tab === t));
  $("#letterText").textContent = letters[t];
}
document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
$("#copy").addEventListener("click", () => navigator.clipboard.writeText(letters[tab]));
$("#download").addEventListener("click", () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([letters[tab]], { type: "text/plain" }));
  a.download = tab === "letter" ? "awaabs-law-letter.txt" : "stage-1-complaint.txt"; a.click();
});

function renderRouting(usage) {
  const total = ((performance.now() - started) / 1000).toFixed(1);
  const tok = usage.reduce((s, u) => s + u.prompt_tokens + u.completion_tokens, 0);
  $("#routing").innerHTML = `<table><tr><th>Step</th><th>Model</th><th>Time</th><th>Tokens</th></tr>${usage.map((u) =>
    `<tr><td>${esc(u.step)}<div class="model">${esc(u.model)}</div></td><td><span class="chip ${u.tier}">${u.tier}</span></td><td>${u.latency_s}s</td><td>${u.prompt_tokens + u.completion_tokens}${u.reasoning_tokens ? `<div class="rt">${u.reasoning_tokens} reasoning</div>` : ""}</td></tr>`).join("")}
    <tr><th>Total</th><th></th><th>${total}s</th><th>${tok}</th></tr></table>`;
  $("#routing").classList.remove("hidden");
}
