const topicInput = document.getElementById("topic");
const manualScriptInput = document.getElementById("manual-script");
const generateBtn = document.getElementById("generate-btn");
const formError = document.getElementById("form-error");
const consoleEl = document.getElementById("console");
const progressFill = document.getElementById("progress-fill");
const globalStatus = document.getElementById("global-status");
const globalStatusLabel = document.getElementById("global-status-label");
const resultSection = document.getElementById("result-section");
const resultVideo = document.getElementById("result-video");
const resultTopic = document.getElementById("result-topic");
const downloadLink = document.getElementById("download-link");
const anotherBtn = document.getElementById("another-btn");

const STEP_PROGRESS = {
  "Using your provided script": 20,
  "Writing script...": 10,
  "Script ready": 25,
  "Generating voiceover...": 35,
  "Voiceover ready": 50,
  "Sourcing stock footage...": 60,
  "clips downloaded": 75,
  "Assembling final video...": 85,
  "Video ready": 100,
};

let pollTimer = null;

function setGlobalStatus(state, label) {
  globalStatus.dataset.state = state;
  globalStatusLabel.textContent = label;
}

function timestamp() {
  const d = new Date();
  return d.toTimeString().slice(0, 8);
}

function renderLog(lines) {
  if (!lines.length) {
    consoleEl.innerHTML = `<p class="console-idle">Waiting for a topic...</p>`;
    return;
  }
  consoleEl.innerHTML = lines
    .map((line, i) => {
      const isLatest = i === lines.length - 1;
      const isError = line.toLowerCase().startsWith("error");
      return `<div class="console-line ${isLatest ? "is-latest" : ""} ${isError ? "is-error" : ""}"><span class="ts">${timestamp()}</span>${escapeHtml(line)}</div>`;
    })
    .join("");
  consoleEl.scrollTop = consoleEl.scrollHeight;

  const last = lines[lines.length - 1];
  const pct = STEP_PROGRESS[last] ?? (lines.length * 12);
  progressFill.style.width = Math.min(pct, 100) + "%";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

async function startGeneration() {
  const topic = topicInput.value.trim();
  const manualScript = manualScriptInput.value.trim();

  formError.textContent = "";
  if (!topic) {
    formError.textContent = "Give it a topic first.";
    return;
  }

  generateBtn.disabled = true;
  generateBtn.querySelector("span").textContent = "Generating...";
  setGlobalStatus("generating", "GENERATING");
  resultSection.hidden = true;
  progressFill.style.width = "0%";
  renderLog([]);

  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, manual_script: manualScript || null }),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || "Something went wrong starting the job.");
    }

    pollStatus(data.job_id, topic);
  } catch (err) {
    formError.textContent = err.message;
    resetButton();
    setGlobalStatus("error", "ERROR");
  }
}

function pollStatus(jobId, topic) {
  pollTimer = setInterval(async () => {
    const res = await fetch(`/api/status/${jobId}`);
    const data = await res.json();
    renderLog(data.log || []);

    if (data.status === "done") {
      clearInterval(pollTimer);
      setGlobalStatus("ready", "READY");
      resetButton();
      showResult(jobId, topic);
    } else if (data.status === "error") {
      clearInterval(pollTimer);
      setGlobalStatus("error", "ERROR");
      formError.textContent = data.error || "Generation failed.";
      resetButton();
    }
  }, 1800);
}

function showResult(jobId, topic) {
  const videoUrl = `/api/video/${jobId}`;
  resultVideo.src = videoUrl;
  resultTopic.textContent = `"${topic}"`;
  downloadLink.href = videoUrl;
  resultSection.hidden = false;
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetButton() {
  generateBtn.disabled = false;
  generateBtn.querySelector("span").textContent = "Generate video";
}

anotherBtn.addEventListener("click", () => {
  resultSection.hidden = true;
  topicInput.value = "";
  manualScriptInput.value = "";
  renderLog([]);
  progressFill.style.width = "0%";
  setGlobalStatus("standby", "STANDBY");
  topicInput.focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
});

generateBtn.addEventListener("click", startGeneration);
topicInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") startGeneration();
});
