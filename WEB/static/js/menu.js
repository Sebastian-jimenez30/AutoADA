document.addEventListener("DOMContentLoaded", () => {
  const statusGrid = document.getElementById("statusGrid");
  const btnActualizar = document.getElementById("btnActualizar");
  const btnRefrescar = document.getElementById("btnRefrescar");
  const tabs = Array.from(document.querySelectorAll(".output-tab"));
  const panels = Array.from(document.querySelectorAll(".output-panel"));
  const logOutput = document.getElementById("logOutput");
  const statusBadge = document.getElementById("logStatus");
  const resultBox = document.getElementById("resultMessage");
  const summaryList = document.getElementById("summaryList");
  const summaryStatus = document.getElementById("summaryStatus");
  const summaryLoader = document.getElementById("summaryLoader");
  const summaryEmpty = document.getElementById("summaryEmpty");

  const SUMMARY_VARIANTS = new Set(["info", "success", "warning", "error"]);
  const MAX_SUMMARY_ITEMS = 40;

  const activatePanel = (target) => {
    tabs.forEach((tab) => {
      const isActive = tab.dataset.target === target;
      tab.classList.toggle("is-active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    panels.forEach((panel) => {
      const isActive = panel.dataset.panel === target;
      panel.classList.toggle("is-active", isActive);
    });
  };

  const scrollToOutputs = () => {
    const container = document.querySelector(".buscarkey-output") || document.querySelector(".output-panels");
    if (container && typeof container.scrollIntoView === "function") {
      container.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const setStatus = (text, variant = "info") => {
    if (statusBadge) {
      statusBadge.textContent = text;
      statusBadge.dataset.status = variant;
    }
  };

  const showResult = (status, message) => {
    if (resultBox) {
      resultBox.textContent = message || "";
      resultBox.dataset.status = status || "INFO";
    }
  };

  const resetSummary = () => {
    if (summaryList) summaryList.innerHTML = "";
    if (summaryStatus) summaryStatus.textContent = "";
    if (summaryEmpty) summaryEmpty.hidden = false;
    if (summaryLoader) summaryLoader.hidden = true;
  };

  const appendSummaryMessage = (message, variant = "info") => {
    if (!summaryList || !summaryStatus) return;
    const clean = (message || "").trim();
    if (!clean) return;
    const normalized = SUMMARY_VARIANTS.has(variant) ? variant : "info";
    const item = document.createElement("li");
    item.className = "summary-message";
    item.dataset.variant = normalized;
    const textSpan = document.createElement("span");
    textSpan.textContent = clean;
    item.appendChild(textSpan);
    const timeSpan = document.createElement("span");
    timeSpan.className = "summary-message__time";
    timeSpan.textContent = new Date().toLocaleTimeString();
    item.appendChild(timeSpan);
    summaryList.appendChild(item);
    while (summaryList.children.length > MAX_SUMMARY_ITEMS) {
      summaryList.removeChild(summaryList.firstChild);
    }
    summaryStatus.textContent = clean;
    if (summaryEmpty) summaryEmpty.hidden = true;
  };

  const setSummaryLoader = (visible) => {
    if (summaryLoader) summaryLoader.hidden = !visible;
  };

  const resetConsole = () => {
    if (logOutput) logOutput.textContent = "";
    if (statusBadge) statusBadge.dataset.status = "info";
    if (resultBox) resultBox.textContent = "";
  };

  const renderStatus = (data) => {
    if (!statusGrid) return;
    const empresas = (data && data.empresas) || [];
    if (!empresas.length) {
      statusGrid.innerHTML = "<p>No hay datos de estado disponibles.</p>";
      return;
    }
    const fragment = document.createDocumentFragment();
    empresas.forEach((item) => {
      const card = document.createElement("article");
      card.className = "status-card";
      const title = document.createElement("h4");
      title.textContent = `${item.empresa} (${item.dominio})`;
      card.appendChild(title);

      const list = document.createElement("ul");
      [
        { label: "SCADA", value: item.scada },
        { label: "HSH", value: item.hsh },
        { label: "ODS TXT", value: item.ods },
      ].forEach((row) => {
        const li = document.createElement("li");
        const strong = document.createElement("strong");
        strong.textContent = `${row.label}: `;
        const span = document.createElement("span");
        span.className = "last-update";
        span.textContent = row.value || "Ultima actualizacion: —";
        li.appendChild(strong);
        li.appendChild(span);
        list.appendChild(li);
      });
      card.appendChild(list);
      fragment.appendChild(card);
    });
    statusGrid.innerHTML = "";
    statusGrid.appendChild(fragment);
  };

  const fetchStatus = async () => {
    try {
      const resp = await fetch("/menu/status");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      renderStatus(data);
    } catch (err) {
      if (statusGrid) statusGrid.innerHTML = `<p>Error al cargar estado: ${err}</p>`;
    }
  };

  const handleStream = async (response) => {
    if (!response.body) return { status: "ERROR", message: "Sin cuerpo de respuesta" };
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        const cleaned = line.replace(/\r/g, "").trim();
        if (!cleaned) continue;
        if (cleaned.startsWith("RESULT::")) {
          try {
            finalResult = JSON.parse(cleaned.substring("RESULT::".length));
          } catch {}
        } else if (cleaned.startsWith("SUMMARY::")) {
          const [text, variant] = cleaned.substring("SUMMARY::".length).split("|");
          appendSummaryMessage(text, variant || "info");
        } else {
          if (logOutput) {
            logOutput.textContent += `${cleaned}\n`;
            logOutput.scrollTop = logOutput.scrollHeight;
          }
        }
      }
    }
    return finalResult;
  };

  const runActualizar = async () => {
    if (btnActualizar) btnActualizar.disabled = true;
    if (btnRefrescar) btnRefrescar.disabled = true;
    resetConsole();
    resetSummary();
    setSummaryLoader(true);
    activatePanel("summary");
    scrollToOutputs();
    setStatus("Ejecutando...");
    showResult("INFO", "Actualizando datos...");

    try {
      const resp = await fetch("/menu/actualizar", { method: "POST" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const result = await handleStream(resp);
      if (result && result.message) {
        appendSummaryMessage(result.message, result.status?.toLowerCase() || "info");
        showResult(result.status || "INFO", result.message);
      }
      await fetchStatus();
    } catch (err) {
      appendSummaryMessage(`Error: ${err}`, "error");
      showResult("ERROR", String(err));
    } finally {
      setSummaryLoader(false);
      if (btnActualizar) btnActualizar.disabled = false;
      if (btnRefrescar) btnRefrescar.disabled = false;
    }
  };

  if (btnActualizar) {
    btnActualizar.addEventListener("click", (e) => {
      e.preventDefault();
      runActualizar();
    });
  }
  if (btnRefrescar) {
    btnRefrescar.addEventListener("click", (e) => {
      e.preventDefault();
      fetchStatus();
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      activatePanel(tab.dataset.target);
    });
  });

  fetchStatus();
});
