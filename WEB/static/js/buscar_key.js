document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("buscarKeyForm");
  if (!form) return;

  const logOutput = document.getElementById("logOutput");
  const ejecutarBtn = document.getElementById("buscarKeyBtn");
  const limpiarBtn = document.getElementById("limpiarLogBtn");
  const statusBadge = document.getElementById("logStatus");
  const resultBox = document.getElementById("resultMessage");

  const tabs = Array.from(document.querySelectorAll(".output-tab"));
  const panels = Array.from(document.querySelectorAll(".output-panel"));

  const resultPanel = document.getElementById("resultPanel");
  const resultHead = document.getElementById("resultTableHead");
  const resultBody = document.getElementById("resultTableBody");
  const resultEmpty = document.getElementById("resultEmptyState");
  const resultMeta = document.getElementById("resultMeta");
  const sheetTabsContainer = document.getElementById("resultSheetTabs");
  const downloadBtn = document.getElementById("resultDownloadBtn");

  const sheetCache = new Map();
  let availableSheets = [];
  let activeSheet = null;
  let latestResult = null;
  let resultsNeedsRefresh = true;
  let resultsLoading = false;

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

    if (target === "results" && resultPanel) {
      resultPanel.removeAttribute("hidden");
    }
  };

  const resetResultsView = () => {
    latestResult = null;
    resultsNeedsRefresh = true;
    activeSheet = null;
    availableSheets = [];
    sheetCache.clear();
    if (!resultPanel) return;
    resultHead.innerHTML = "";
    resultBody.innerHTML = "";
    resultPanel.classList.add("is-empty");
    if (resultEmpty) {
      resultEmpty.textContent = "Los resultados aparecerán aquí al finalizar el proceso.";
    }
    if (resultMeta) {
      resultMeta.textContent = "";
    }
    if (sheetTabsContainer) {
      sheetTabsContainer.innerHTML = "";
      sheetTabsContainer.classList.remove("has-tabs");
    }
    if (downloadBtn) {
      downloadBtn.disabled = true;
      downloadBtn.dataset.href = "";
    }
  };

  const updateSheetTabs = (sheets, active) => {
    if (!sheetTabsContainer) return;
    sheetTabsContainer.innerHTML = "";
    sheetTabsContainer.classList.remove("has-tabs");

    if (!Array.isArray(sheets) || sheets.length <= 1) {
      return;
    }

    sheetTabsContainer.classList.add("has-tabs");

    sheets.forEach((name) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "result-sheet-tab";
      button.dataset.sheet = name;
      button.textContent = name;
      const isActive = name === active;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("role", "tab");
      button.setAttribute("aria-selected", isActive ? "true" : "false");
      button.addEventListener("click", () => {
        loadResults({ sheet: name, autoActivate: true });
      });
      sheetTabsContainer.appendChild(button);
    });
  };

  const refreshSheetTabsActiveState = () => {
    if (!sheetTabsContainer) return;
    const buttons = sheetTabsContainer.querySelectorAll(".result-sheet-tab");
    buttons.forEach((button) => {
      const sheet = button.dataset.sheet;
      const isActive = sheet === activeSheet;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-selected", isActive ? "true" : "false");
    });
  };

  const renderResults = (data) => {
    if (!resultPanel || !data) return;

    latestResult = data;

    const sheetList = Array.isArray(data?.sheets) ? data.sheets : [];
    if (sheetList.length) {
      availableSheets = sheetList;
    }

    if (data?.active_sheet) {
      activeSheet = data.active_sheet;
    }

    updateSheetTabs(availableSheets, activeSheet);
    refreshSheetTabsActiveState();

    const columns = Array.isArray(data?.columns) ? data.columns : [];
    const rows = Array.isArray(data?.rows) ? data.rows : [];
    const total = typeof data?.total === "number" ? data.total : rows.length;
    const hasMore = Boolean(data?.has_more);

    resultPanel.removeAttribute("hidden");
    resultHead.innerHTML = "";
    resultBody.innerHTML = "";

    if (!columns.length || !rows.length) {
      resultPanel.classList.add("is-empty");
      if (resultEmpty) {
        const noColumns = rows.length && !columns.length;
        const sheetLabel = activeSheet ? `Hoja "${activeSheet}"` : "Hoja seleccionada";
        resultEmpty.textContent = noColumns
          ? `${sheetLabel} sin columnas visibles.`
          : `${sheetLabel} no contiene registros para mostrar.`;
      }
    } else {
      resultPanel.classList.remove("is-empty");

      const headRow = document.createElement("tr");
      columns.forEach((col) => {
        const th = document.createElement("th");
        th.textContent = col;
        headRow.appendChild(th);
      });
      resultHead.appendChild(headRow);

      rows.forEach((row) => {
        const tr = document.createElement("tr");
        columns.forEach((col) => {
          const td = document.createElement("td");
          const value = row[col];
          td.textContent = value == null ? "" : String(value);
          tr.appendChild(td);
        });
        resultBody.appendChild(tr);
      });
    }

    if (resultMeta) {
      if (rows.length) {
        const plural = rows.length === 1 ? "" : "s";
        const suffix = hasMore
          ? total > rows.length
            ? ` de ${total} registros (vista previa).`
            : ` de más de ${rows.length} registros (vista previa).`
          : ` registro${plural}.`;
        const prefix = `Mostrando ${rows.length}`;
        const sheetLabel = activeSheet ? `Hoja: ${activeSheet} — ` : "";
        resultMeta.textContent = `${sheetLabel}${prefix}${suffix}`;
      } else {
        const sheetLabel = activeSheet ? `Hoja: ${activeSheet}.` : "";
        resultMeta.textContent = `${sheetLabel} Sin registros para mostrar.`.trim();
      }
    }

    if (downloadBtn) {
      const url = data?.download_url || "";
      downloadBtn.dataset.href = url;
      downloadBtn.disabled = !url;
    }
  };

  const loadResults = async ({ force = false, autoActivate = false, sheet = null } = {}) => {
    if (!resultPanel) {
      if (autoActivate) activatePanel("results");
      return;
    }
    if (resultsLoading) {
      if (autoActivate) activatePanel("results");
      return;
    }

    const targetSheet = sheet ?? activeSheet ?? null;
    const mustForce = force || resultsNeedsRefresh;

    if (!mustForce && targetSheet && sheetCache.has(targetSheet)) {
      const cached = sheetCache.get(targetSheet);
      renderResults(cached);
      if (autoActivate) activatePanel("results");
      return;
    }

    resultsLoading = true;
    resultHead.innerHTML = "";
    resultBody.innerHTML = "";
    if (resultPanel) {
      resultPanel.classList.add("is-empty");
    }
    if (resultEmpty) {
      resultEmpty.textContent = "Cargando resultados...";
    }
    if (resultMeta) {
      resultMeta.textContent = "";
    }
    if (downloadBtn) {
      downloadBtn.disabled = true;
      downloadBtn.dataset.href = "";
    }

    const query = targetSheet ? `?sheet=${encodeURIComponent(targetSheet)}` : "";

    try {
      const response = await fetch(`/buscar/key/result/data${query}`, { cache: "no-store" });
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("No se encontraron resultados recientes. Ejecuta una búsqueda para generar un informe.");
        }
        throw new Error(`Error al cargar resultados (HTTP ${response.status}).`);
      }
      const data = await response.json();
      if (data?.active_sheet) {
        sheetCache.set(data.active_sheet, data);
      }
      resultsNeedsRefresh = false;
      renderResults(data);
    } catch (error) {
      latestResult = null;
      const message =
        error instanceof Error ? error.message : "No se pudieron cargar los resultados.";
      if (resultPanel) {
        resultPanel.classList.add("is-empty");
      }
      if (resultEmpty) {
        resultEmpty.textContent = message;
      }
      if (resultMeta) {
        resultMeta.textContent = "";
      }
      if (sheetTabsContainer) {
        sheetTabsContainer.innerHTML = "";
        sheetTabsContainer.classList.remove("has-tabs");
      }
      sheetCache.clear();
      availableSheets = [];
      activeSheet = null;
    } finally {
      resultsLoading = false;
      if (autoActivate) {
        activatePanel("results");
      }
    }
  };

  if (downloadBtn) {
    downloadBtn.addEventListener("click", () => {
      const url = downloadBtn.dataset.href;
      if (url) {
        window.location.href = url;
      }
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.target;
      activatePanel(target);
      if (target === "results") {
        loadResults();
      }
    });
  });

  const setStatus = (text, variant = "muted") => {
    if (!statusBadge) return;
    statusBadge.textContent = text;
    statusBadge.dataset.variant = variant;
  };

  const showResult = (status, message) => {
    if (!resultBox) return;
    resultBox.textContent = message;
    resultBox.className = `result-message ${status === "SUCCESS" ? "success" : "error"}`;
    resultBox.style.display = "block";
  };

  const resetResult = () => {
    if (!resultBox) return;
    resultBox.textContent = "";
    resultBox.className = "result-message";
    resultBox.style.display = "none";
  };

  const appendLog = (text) => {
    if (!logOutput) return;
    logOutput.textContent += text;
    logOutput.scrollTop = logOutput.scrollHeight;
  };

  const handleStream = async (response) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalResult = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const raw of lines) {
        const cleaned = raw.replace(/\r/g, "");
        const trimmed = cleaned.trim();
        if (!trimmed) continue;
        if (trimmed.startsWith("RESULT::")) {
          try {
            finalResult = JSON.parse(trimmed.substring("RESULT::".length));
          } catch {
            finalResult = { status: "ERROR", message: "No fue posible interpretar el resultado final." };
          }
          continue;
        }
        appendLog(`${cleaned}\n`);
      }
    }

    const leftover = buffer.replace(/\r/g, "");
    if (leftover.trim()) {
      if (leftover.trim().startsWith("RESULT::")) {
        try {
          finalResult = JSON.parse(leftover.trim().substring("RESULT::".length));
        } catch {
          finalResult = { status: "ERROR", message: "No fue posible interpretar el resultado final." };
        }
      } else {
        appendLog(`${leftover}\n`);
      }
    }

    return finalResult;
  };

  const ejecutarBusqueda = async () => {
    resetResult();
    if (logOutput) {
      logOutput.textContent = "";
    }

    const formData = new FormData(form);

    let response;
    try {
      response = await fetch("/buscar/key/run", {
        method: "POST",
        body: formData,
      });
    } catch (error) {
      appendLog(`[CLIENT] Error de red: ${error}\n`);
      showResult("ERROR", "No fue posible conectar con el servidor.");
      setStatus("Error", "ERROR");
      return;
    }

    if (!response.ok || !response.body) {
      const text = await response.text();
      appendLog(`[SERVER] Respuesta inesperada (${response.status}): ${text}\n`);
      showResult("ERROR", "La ejecución no pudo iniciarse. Verifica los parámetros.");
      setStatus("Error", "ERROR");
      return;
    }

    const result = await handleStream(response);
    if (result) {
      showResult(result.status, result.message);
      setStatus(result.status === "SUCCESS" ? "Completado" : "Error", result.status);
      if (result.status === "SUCCESS") {
        resultsNeedsRefresh = true;
        sheetCache.clear();
        await loadResults({ force: true, autoActivate: true, sheet: null });
      }
    } else {
      showResult("ERROR", "El proceso finalizó sin entregar un resultado final.");
      setStatus("Error", "ERROR");
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    ejecutarBtn.disabled = true;
    activatePanel("console");
    resetResultsView();
    setStatus("Ejecutando...");
    await ejecutarBusqueda();
    ejecutarBtn.disabled = false;
  });

  if (limpiarBtn) {
    limpiarBtn.addEventListener("click", () => {
      if (logOutput) {
        logOutput.textContent = "";
      }
      setStatus("En espera");
      resetResult();
    });
  }
});
