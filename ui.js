// -------------------------------
// VIEW MANAGEMENT
// -------------------------------

function hideAllViews() {
  document.getElementById("dashboardView").style.display = "none";
  document.getElementById("clarityView").style.display = "none";
  document.getElementById("marketingCalendarView").style.display = "none";
  document.getElementById("trendsView").style.display = "none";
  document.getElementById("systemHealthView").style.display = "none";
}

function showDashboard() {
  hideAllViews();
  document.getElementById("dashboardView").style.display = "flex";
}

function showClarity() {
  hideAllViews();
  document.getElementById("clarityView").style.display = "block";
}

function showMarketingCalendar() {
  hideAllViews();
  document.getElementById("marketingCalendarView").style.display = "block";
}

function showTrends() {
  hideAllViews();
  document.getElementById("trendsView").style.display = "block";
}

function showSystemHealth() {
  hideAllViews();
  document.getElementById("systemHealthView").style.display = "block";
}

// -------------------------------
// TREND COLLECTOR API CALLS
// -------------------------------

// IMPORTANT: Replace <YOUR-REPL-URL> with your actual Replit URL.
// Example: https://homebridge-saas.kevin4165.repl.co

const BASE_URL = "https://trend-collector-service-2-xxxxx.onrender.com";

async function fetchTrends() {
  const output = document.getElementById("trendsOutput");
  output.textContent = "Loading...";

  try {
    const response = await fetch(`${BASE_URL}/trends`);
    const data = await response.json();
    output.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    output.textContent = "Error fetching trends.";
  }
}

async function checkHealth() {
  const output = document.getElementById("healthOutput");
  output.textContent = "Checking...";

  try {
    const response = await fetch(`${BASE_URL}/health`);
    const data = await response.json();
    output.textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    output.textContent = "Error checking system health.";
  }
}

// -------------------------------
// CLARITY ENGINE
// -------------------------------

document.getElementById("runButton").addEventListener("click", async () => {
  const input = document.getElementById("userInput").value;
  const results = document.getElementById("results");

  results.textContent = "Processing...";

  try {
    const response = await fetch("/clarity", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: input }),
    });

    const data = await response.json();
    results.textContent = data.output || "No response.";
  } catch (err) {
    results.textContent = "Error running clarity engine.";
  }
});

// -------------------------------
// MARKETING CALENDAR
// -------------------------------

function toggleWeekContent(weekId) {
  const content = document.getElementById(`week-content-${weekId}`);
  content.style.display = content.style.display === "none" ? "block" : "none";
}

// -------------------------------
// DASHBOARD PLACEHOLDERS
// -------------------------------

document.getElementById("priorityActionsList").innerHTML = `
  <li>Finalize onboarding sequence</li>
  <li>Review trend signals</li>
  <li>Prepare next outreach message</li>
`;

document.getElementById("weeklyObjectivesList").innerHTML = `
  <li>Record Denver Obvious Guide video</li>
  <li>Update clarity scripts</li>
  <li>Review probate partner list</li>
`;

document.getElementById("deadlinesList").innerHTML = `
  <li>Feb 15 — Probate attorney outreach</li>
  <li>Feb 20 — Senior care blog refresh</li>
  <li>Feb 28 — Market update recording</li>
`;

// -------------------------------
// DEFAULT VIEW
// -------------------------------

showDashboard();
// ===============================
// CONTENT MODAL LOGIC
// ===============================

function openModal(item) {
  document.getElementById("modalHeadline").textContent = item.headline || "";
  document.getElementById("modalNiche").textContent = item.niche || "";
  document.getElementById("modalStatus").textContent = item.status || "";

  document.getElementById("modalPost").textContent = item.post || "";
  document.getElementById("modalCTA").textContent = item.call_to_action || "";
  document.getElementById("modalScript").textContent = item.script30 || "";
  document.getElementById("modalThumb").textContent = item.thumbnailIdea || "";
  document.getElementById("modalTags").textContent = (item.hashtags || []).join(", ");

  document.getElementById("contentModal").style.display = "flex";
}

function closeModal() {
  document.getElementById("contentModal").style.display = "none";
}

// ===============================
// QUEUE TABLE CLICK HANDLER
// ===============================

function loadQueue() {
  const tableBody = document.getElementById("queueTableBody");
  tableBody.innerHTML = "Loading...";

  fetch(`${BASE_URL}/queue/list`)
    .then(res => res.json())
    .then(data => {
      if (!data.items) {
        tableBody.innerHTML = "No items found.";
        return;
      }

      tableBody.innerHTML = "";

      data.items.forEach(item => {
        const tr = document.createElement("tr");

        tr.innerHTML = `
          <td>${item.created_at}</td>
          <td style="cursor:pointer; color:#0077cc; text-decoration:underline;">
            ${item.headline}
            <div class="preview-text" style="font-size:12px; color:#666; margin-top:4px;">
              ${item.post ? item.post.substring(0, 160) + "..." : ""}
            </div>
          </td>
          <td>${item.niche}</td>
          <td>${item.status}</td>
          <td>${(item.hashtags || []).join(", ")}</td>
        `;

        tr.addEventListener("click", () => openModal(item));
        tableBody.appendChild(tr);
      });
    })
    .catch(() => {
      tableBody.innerHTML = "Error loading queue.";
    });
}
