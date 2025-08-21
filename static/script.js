// Core elements
const chatBody = document.querySelector(".chatbot-body");
const chatForm = document.querySelector(".chat-form");
const messageInput = document.querySelector(".message-input");
const codeBtn = document.getElementById("codeBtn");
const voiceBtn = document.getElementById("voiceBtn");
const studentSidebar = document.getElementById("studentSidebar");

// Code analyzer
const codeAnalyzerModal = document.getElementById("codeAnalyzerModal");
const codeInput = document.getElementById("codeInput");
const analyzeResult = document.getElementById("analyzeResult");
const languageSelect = document.getElementById("languageSelect");

// State
let personalityMode = "friendly";
let isCodeMode = false;
let currentMode = "chat"; // chat | debug

document.addEventListener("DOMContentLoaded", function () {
  // Set initial personality as active
  document.getElementById("friendly-btn")?.classList.add("active");

  // Auto-resize textarea
  if (messageInput) {
    messageInput.addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });
  }
});

// Keyboard shortcuts
document.addEventListener("keydown", function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    openCodeAnalyzer();
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "m") {
    e.preventDefault();
    toggleCodeMode();
  }
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "s") {
    e.preventDefault();
    toggleStudentMode();
  }
  if (e.key === "Escape") {
    closeCodeAnalyzer();
    closeStudentMode();
  }
});

// Form submit and Enter-to-send
if (chatForm) {
  chatForm.addEventListener("submit", handleFormSubmit);
}
if (messageInput) {
  messageInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });
}

// Toggle code mode
function toggleCodeMode() {
  isCodeMode = !isCodeMode;
  codeBtn?.classList.toggle("active", isCodeMode);
  addMessage(isCodeMode ? "Coder mode: ON" : "Coder mode: OFF", false, false);
}

// Student mode panel
function toggleStudentMode() {
  studentSidebar?.classList.toggle("show");
}
function closeStudentMode() {
  studentSidebar?.classList.remove("show");
}

// Code Analyzer modal
function openCodeAnalyzer() {
  codeAnalyzerModal?.classList.add("show");
}
function closeCodeAnalyzer() {
  codeAnalyzerModal?.classList.remove("show");
}

// Personality
function setPersonality(p) {
  personalityMode = p;
  document.querySelectorAll(".tag").forEach((b) => b.classList.remove("active"));
  document.getElementById(`${p}-btn`)?.classList.add("active");
}
function setMode(m) {
  currentMode = m;
  addMessage(`Switched to ${m} mode.`, false, false);
}

// Quick actions
function quickPrompt(text) {
  messageInput.value = text;
  chatForm.dispatchEvent(new Event("submit"));
}

// Chat submit handler
function handleFormSubmit(e) {
  e.preventDefault();
  const text = (messageInput?.value || "").trim();
  if (!text) return;

  addMessage(text, true, isCodeLike(text));
  messageInput.value = "";
  messageInput.style.height = "40px";

  // Stream reply via SSE
  streamReply({
    mode: isCodeMode ? "debug" : "chat",
    personality: personalityMode,
    message: text,
  });
}

// Streaming via fetch + ReadableStream
function streamReply(payload) {
  const typing = addTypingIndicator();

  fetch("/api/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((res) => {
      if (!res.ok) throw new Error("Network error");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      const botDiv = document.createElement("div");
      botDiv.className = "chat-message bot";
      botDiv.innerHTML = "";
      chatBody.appendChild(botDiv);

      const process = ({ done, value }) => {
        if (done) {
          typing.remove();
          chatBody.scrollTop = chatBody.scrollHeight;
          return;
        }
        const chunk = decoder.decode(value, { stream: true });
        chunk.split("\n\n").forEach((line) => {
          if (!line) return;
          if (line.startsWith("event:start")) return;
          if (line.startsWith("event:end")) return;
          if (line.startsWith("data: ")) {
            const data = line.slice(6).replace(/\\n/g, "\n");
            botDiv.innerHTML += formatMessage(data);
          }
        });
        chatBody.scrollTop = chatBody.scrollHeight;
        return reader.read().then(process);
      };

      return reader.read().then(process);
    })
    .catch((err) => {
      typing.remove();
      addMessage("Error: " + err.message, false, false);
    });
}

// Analyzer
function analyzeCode() {
  const code = (codeInput?.value || "").trim();
  const language = languageSelect?.value || "auto";
  if (!code) {
    analyzeResult.innerHTML =
      `<div class="chat-message bot">Please paste some code to analyze.</div>`;
    return;
  }
  analyzeResult.innerHTML =
    `<div class="chat-message bot typing-indicator">Analyzing...</div>`;
  fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, language }),
  })
    .then((r) => r.json())
    .then((d) => {
      analyzeResult.innerHTML =
        `<div class="chat-message bot"><strong>Language:</strong> ${d.language}<br><br>${formatMessage(d.analysis || "")}</div>`;
    })
    .catch((e) => {
      analyzeResult.innerHTML =
        `<div class="chat-message bot">Error: ${e.message}</div>`;
    });
}

// Message helpers
function addTypingIndicator() {
  const el = document.createElement("div");
  el.className = "chat-message bot typing-indicator";
  el.textContent = "Typing...";
  chatBody.appendChild(el);
  chatBody.scrollTop = chatBody.scrollHeight;
  return el;
}

function addMessage(message, isUser = false, isCode = false) {
  // Remove welcome if exists
  const welcomeMsg = document.querySelector(".welcome-message");
  if (welcomeMsg) welcomeMsg.remove();

  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-message ${isUser ? "user" : "bot"}`;

  if (isCode) {
    msgDiv.innerHTML = `<pre><code>${escapeHtml(message)}</code></pre>`;
  } else {
    msgDiv.innerHTML = formatMessage(message);
  }

  chatBody.appendChild(msgDiv);
  chatBody.scrollTop = chatBody.scrollHeight;

  // Soft animation
  msgDiv.style.opacity = "0";
  msgDiv.style.transform = "translateY(20px) scale(0.95)";
  requestAnimationFrame(() => {
    msgDiv.style.transition =
      "all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)";
    msgDiv.style.opacity = "1";
    msgDiv.style.transform = "translateY(0) scale(1)";
  });
}

function isCodeLike(text) {
  return /```|;|{|\bdef\b|\bfunction\b|\bclass\b|\bconsole.log\b/.test(
    text || ""
  );
}

function formatMessage(message) {
  let formatted = escapeHtml(message)
    .replace(/^### (.*)$/gim, "<h3>$1</h3>")
    .replace(/^## (.*)$/gim, "<h2>$1</h2>")
    .replace(/^# (.*)$/gim, "<h1>$1</h1>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n/g, "<br>");
  return formatted;
}

function escapeHtml(text) {
  const map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };
  return String(text).replace(/[&<>"']/g, (m) => map[m]);
}

// Expose to HTML
window.setPersonality = setPersonality;
window.setMode = setMode;
window.toggleStudentMode = toggleStudentMode;
window.openCodeAnalyzer = openCodeAnalyzer;
window.closeCodeAnalyzer = closeCodeAnalyzer;
window.quickPrompt = quickPrompt;
window.analyzeCode = analyzeCode;
