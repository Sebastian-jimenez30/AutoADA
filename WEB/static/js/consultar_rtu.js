document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("buscarKeyForm");
  if (!form) return;

  const origin = window.location.origin;

  const empresaSelect = document.getElementById("empresa");
  const dominioSelect = document.getElementById("dominio");
  const buscador = document.getElementById("buscadorRtu");
  const rtuListContainer = document.getElementById("rtuList");
  const rtuCountLabel = document.getElementById("rtuCount");
  const actualizarBtn = document.getElementById("actualizarRtuBtn");
  const consultarBtn = document.getElementById("verificarBtn");

  const runUrl = form.dataset.runUrl || "/consultar/rtu/run";
  const actualizarUrl = "/consultar/rtu/actualizar";
  const listUrl = "/consultar/rtu/list";
  const resultDownloadBase = form.dataset.fileDownload || "/consultar/rtu/result/download";
  const resultEndpoint = form.dataset.resultUrl || "/consultar/rtu/result";

  const resultPanel = document.getElementById("resultPanel");
  const resultHead = document.getElementById("resultTableHead");
  const resultBody = document.getElementById("resultTableBody");
  const resultEmpty = document.getElementById("resultEmptyState");
  const downloadBtn = document.getElementById("resultDownloadBtn");
  const resultMeta = document.getElementById("resultMeta");
  const sheetTabsContainer = document.getElementById("resultSheetTabs");
  const fileListContainer = document.getElementById("resultFileList");
  const resultDetails = document.getElementById("resultDetails");

  const summaryPanel = document.getElementById("summaryPanel");
  const summaryList = document.getElementById("summaryList");
  const summaryStatus = document.getElementById("summaryStatus");
  const summaryLoader = document.getElementById("summaryLoader");
  const summaryEmpty = document.getElementById("summaryEmpty");

  const logOutput = document.getElementById("logOutput");
  const statusBadge = document.getElementById("logStatus");
  const resultBox = document.getElementById("resultMessage");
  const tabs = Array.from(document.querySelectorAll(".output-tab"));
  const panels = Array.from(document.querySelectorAll(".output-panel"));

  let selectedRtus = new Set();
  let currentItems = [];
  const sheetCache = new Map();
  let availableSheets = [];
  let activeSheet = null;
  let resultsNeedsRefresh = true;
  let resultsLoading = false;
  const SUMMARY_VARIANTS = new Set(["info", "success", "warning", "error"]);
  const MAX_SUMMARY_ITEMS = 40;

  const buildResultUrl = (sheetValue) => {
    try {
      const url = new URL(resultEndpoint, origin);
      if (sheetValue) {
        url.searchParams.set("sheet", sheetValue);
      } else {
        url.searchParams.delete("sheet");
      }
      return url.toString();
    } catch {
      if (sheetValue) {
        const separator = resultEndpoint.includes("?") ? "&" : "?";
        return `${resultEndpoint}${separator}sheet=${encodeURIComponent(sheetValue)}`;
      }
      return resultEndpoint;
    }
  };

  const buildDownloadUrl = (filePath) => {
    if (!resultDownloadBase || !filePath) return "";
    try {
      const url = new URL(resultDownloadBase, origin);
      if (!url.searchParams.has("path")) {
        url.searchParams.append("path", filePath);
      } else {
        url.searchParams.set("path", filePath);
      }
      return url.toString();
    } catch {
      const separator = resultDownloadBase.includes("?") ? "&" : "?";
      return `${resultDownloadBase}${separator}path=${encodeURIComponent(filePath)}`;
    }
  };

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

  const setSummaryStatus = (label, variant = "info") => {
    if (!summaryStatus) return;
    summaryStatus.textContent = label;
    summaryStatus.dataset.variant = variant;
  };

  const toggleSummaryLoader = (visible) => {
    if (!summaryLoader) return;
    summaryLoader.hidden = !visible;
  };

  const setSummaryHasMessages = (hasMessages) => {
    if (summaryPanel) {
      summaryPanel.classList.toggle("has-messages", hasMessages);
    }
    if (summaryEmpty) {
      summaryEmpty.hidden = hasMessages;
    }
  };

  const clearSummaryMessages = () => {
    if (summaryList) {
      summaryList.innerHTML = "";
    }
    setSummaryHasMessages(false);
  };

  const appendSummaryMessage = (message, variant = "info") => {
    if (!summaryPanel || !summaryList) return;
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
    setSummaryHasMessages(true);
    summaryList.scrollTop = summaryList.scrollHeight;
  };

  const resetSummaryView = () => {
    if (!summaryPanel) return;
    summaryPanel.dataset.state = "idle";
    clearSummaryMessages();
    toggleSummaryLoader(false);
    setSummaryStatus("En espera", "idle");
    if (summaryEmpty) {
      summaryEmpty.textContent = "Los mensajes generales apareceran aqui durante la ejecucion.";
    }
  };

  const startSummaryRun = () => {
    if (!summaryPanel) return;
    resetSummaryView();
    summaryPanel.dataset.state = "running";
    toggleSummaryLoader(true);
    setSummaryStatus("Procesando", "info");
    appendSummaryMessage("Proceso iniciado.", "info");
  };

  const finishSummaryRun = (state) => {
    if (!summaryPanel) return;
    summaryPanel.dataset.state = "done";
    toggleSummaryLoader(false);
    if (state === "success") {
      setSummaryStatus("Completado", "success");
      appendSummaryMessage("Proceso completado sin errores.", "success");
    } else if (state === "error") {
      setSummaryStatus("Finalizado con errores", "error");
      appendSummaryMessage("El proceso finalizo con errores.", "error");
    } else {
      setSummaryStatus("Finalizado", "info");
    }
  };

  const handleSummaryPayload = (payload) => {
    const content = (payload || "").trim();
    if (!content) return;
    const parts = content
      .split("|")
      .map((segment) => segment.trim())
      .filter(Boolean);
    if (!parts.length) return;

    let variant = "info";
    const last = parts[parts.length - 1]?.toLowerCase();
    if (last && SUMMARY_VARIANTS.has(last)) {
      variant = last;
      parts.pop();
    }
    const message = parts.join(" | ").trim();
    if (!message) return;
    appendSummaryMessage(message, variant);
  };

  const resetResultsView = () => {
    resultsNeedsRefresh = true;
    activeSheet = null;
    availableSheets = [];
    sheetCache.clear();
    if (!resultPanel) return;

    resultHead.innerHTML = "";
    resultBody.innerHTML = "";
    resultPanel.classList.add("is-empty");
    if (resultEmpty) {
      resultEmpty.textContent = "Los resultados apareceran aqui al finalizar el proceso.";
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
    if (fileListContainer) {
      fileListContainer.innerHTML = "";
      fileListContainer.classList.remove("is-visible");
      fileListContainer.hidden = true;
    }
    if (resultDetails) {
      resultDetails.innerHTML = "";
      resultDetails.classList.remove("is-visible");
      resultDetails.hidden = true;
    }
  };

  const updateSheetTabs = (sheets, active) => {
    if (!sheetTabsContainer) return;
    sheetTabsContainer.innerHTML = "";
    sheetTabsContainer.classList.remove("has-tabs");

    if (!Array.isArray(sheets) || sheets.length <= 1) return;

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

  const renderFileList = (files) => {
    if (!fileListContainer) return;
    const list = Array.isArray(files) ? files.filter(Boolean) : [];
    if (!list.length) {
      fileListContainer.innerHTML = "";
      fileListContainer.classList.remove("is-visible");
      fileListContainer.hidden = true;
      return;
    }

    const fragment = document.createDocumentFragment();
    const title = document.createElement("p");
    title.textContent = "Archivos generados:";
    fragment.appendChild(title);

    const ul = document.createElement("ul");
    list.forEach((filePath) => {
      const li = document.createElement("li");
      const href = buildDownloadUrl(filePath);
      if (href) {
        const link = document.createElement("a");
        link.href = href;
        link.textContent = filePath;
        link.target = "_blank";
        link.rel = "noopener";
        li.appendChild(link);
      } else {
        const span = document.createElement("span");
        span.textContent = filePath;
        li.appendChild(span);
      }
      ul.appendChild(li);
    });
    fragment.appendChild(ul);

    fileListContainer.innerHTML = "";
    fileListContainer.appendChild(fragment);
    fileListContainer.classList.add("is-visible");
    fileListContainer.hidden = false;
  };

  const renderDetails = (details) => {
    if (!resultDetails) return;
    const lines = Array.isArray(details) ? details.filter(Boolean) : [];
    if (!lines.length) {
      resultDetails.innerHTML = "";
      resultDetails.classList.remove("is-visible");
      resultDetails.hidden = true;
      return;
    }

    const fragment = document.createDocumentFragment();
    const title = document.createElement("p");
    title.textContent = "Resumen:";
    fragment.appendChild(title);
    const list = document.createElement("ul");
    list.style.margin = "8px 0 0 16px";
    list.style.padding = "0";
    lines.forEach((line) => {
      const item = document.createElement("li");
      item.textContent = line;
      list.appendChild(item);
    });
    fragment.appendChild(list);

    resultDetails.innerHTML = "";
    resultDetails.appendChild(fragment);
    resultDetails.classList.add("is-visible");
    resultDetails.hidden = false;
  };

  const renderResults = (data) => {
    if (!resultPanel || !resultHead || !resultBody) return;

    const sheetList = Array.isArray(data?.sheets) ? data.sheets : [];
    if (sheetList.length) {
      availableSheets = sheetList;
    }
    if (data?.active_sheet) {
      activeSheet = data.active_sheet;
    }
    updateSheetTabs(availableSheets, activeSheet);
    refreshSheetTabsActiveState();

    const isRaw = typeof data?.raw_text === "string";
    const columns = !isRaw && Array.isArray(data?.columns) ? data.columns : [];
    const rows = !isRaw && Array.isArray(data?.rows) ? data.rows : [];
    const total = !isRaw && typeof data?.total === "number" ? data.total : rows.length;
    const hasMore = !isRaw && Boolean(data?.has_more);
    const files = Array.isArray(data?.files) ? data.files : [];
    const details = data?.details || (data?.extra && data.extra.details);
    const message = data?.message;

    resultPanel.removeAttribute("hidden");
    resultHead.innerHTML = "";
    resultBody.innerHTML = "";

    const hasTabularData = columns.length > 0 && rows.length > 0;

    if (isRaw) {
      resultPanel.classList.remove("is-empty");
      if (resultEmpty) {
        resultEmpty.textContent = "";
      }
      const pre = document.createElement("pre");
      pre.className = "result-raw-text";
      pre.textContent = data.raw_text || "";
      const wrapperRow = document.createElement("tr");
      const wrapperCell = document.createElement("td");
      wrapperCell.colSpan = 1;
      wrapperCell.appendChild(pre);
      wrapperRow.appendChild(wrapperCell);
      resultBody.appendChild(wrapperRow);
    } else if (!hasTabularData) {
      resultPanel.classList.add("is-empty");
      if (resultEmpty) {
        if (files.length) {
          resultEmpty.textContent = "No hay tabla para mostrar. Revisa los archivos generados.";
        } else if (message) {
          resultEmpty.textContent = message;
        } else {
          const sheetLabel = activeSheet ? `Hoja "${activeSheet}"` : "Hoja seleccionada";
          resultEmpty.textContent = `${sheetLabel} no contiene registros para mostrar.`;
        }
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
      if (isRaw) {
        const sheetLabel = activeSheet ? `Hoja: ${activeSheet} - ` : "";
        resultMeta.textContent = `${sheetLabel}Vista previa texto plano (CSV)`;
      } else if (hasTabularData) {
        const plural = rows.length === 1 ? "" : "s";
        const suffix = hasMore
          ? total > rows.length
            ? ` de ${total} registros (vista previa).`
            : ` de mas de ${rows.length} registros (vista previa).`
          : ` registro${plural}.`;
        const prefix = `Mostrando ${rows.length}`;
        const sheetLabel = activeSheet ? `Hoja: ${activeSheet} - ` : "";
        resultMeta.textContent = `${sheetLabel}${prefix}${suffix}`;
      } else if (message) {
        resultMeta.textContent = message;
      } else {
        resultMeta.textContent = "";
      }
    }

    if (downloadBtn) {
      const url = data?.download_url || "";
      downloadBtn.dataset.href = url;
      downloadBtn.disabled = !url;
    }

    renderFileList(files);
    renderDetails(details);
  };

  const loadResults = async ({
    force = false,
    autoActivate = false,
    sheet = null,
  } = {}) => {
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
    if (fileListContainer) {
      fileListContainer.innerHTML = "";
      fileListContainer.classList.remove("is-visible");
      fileListContainer.hidden = true;
    }
    if (resultDetails) {
      resultDetails.innerHTML = "";
      resultDetails.classList.remove("is-visible");
      resultDetails.hidden = true;
    }

    try {
      const response = await fetch(buildResultUrl(targetSheet), {
        cache: "no-store",
      });
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("No se encontraron resultados recientes. Ejecuta una consulta para generar un informe.");
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
      if (fileListContainer) {
        fileListContainer.innerHTML = "";
        fileListContainer.classList.remove("is-visible");
        fileListContainer.hidden = true;
      }
      if (resultDetails) {
        resultDetails.innerHTML = "";
        resultDetails.classList.remove("is-visible");
        resultDetails.hidden = true;
      }
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

  const appendLog = (text) => {
    if (!logOutput) return;
    logOutput.textContent += text;
    logOutput.scrollTop = logOutput.scrollHeight;
  };

  const renderList = () => {
    if (!rtuListContainer) return;
    rtuListContainer.innerHTML = "";
    currentItems.forEach((item) => {
      const div = document.createElement("div");
      div.className = "rtu-item";
      div.textContent = item;
      div.dataset.value = item;
      if (selectedRtus.has(item)) div.classList.add("is-selected");
      div.addEventListener("click", () => {
        if (selectedRtus.has(item)) {
          selectedRtus.delete(item);
          div.classList.remove("is-selected");
        } else {
          selectedRtus.add(item);
          div.classList.add("is-selected");
        }
      });
      rtuListContainer.appendChild(div);
    });
    if (rtuCountLabel) rtuCountLabel.textContent = `${currentItems.length} RTU/SAS`;
  };

  const loadList = async () => {
    const empresa = empresaSelect?.value;
    const dominio = dominioSelect?.value || "CC";
    if (!empresa) return;
    const params = new URLSearchParams();
    params.set("empresa", empresa);
    if (dominio) params.set("dominio", dominio);
    const query = (buscador?.value || "").trim();
    if (query) params.set("search", query);
    try {
      const resp = await fetch(`${listUrl}?${params.toString()}`, { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      currentItems = data?.rtus || [];
      selectedRtus = new Set([...selectedRtus].filter((r) => currentItems.includes(r)));
      renderList();
    } catch (err) {
      currentItems = [];
      renderList();
      appendLog(`[CLIENT] No se pudo cargar RTUs: ${err}\n`);
    }
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
        if (trimmed.startsWith("SUMMARY::")) {
          handleSummaryPayload(trimmed.substring("SUMMARY::".length));
          continue;
        }
        if (trimmed.startsWith("RESULT::")) {
          try {
            finalResult = JSON.parse(trimmed.substring("RESULT::".length));
          } catch {
            finalResult = { status: "ERROR", message: "No se pudo interpretar el resultado final." };
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
          finalResult = { status: "ERROR", message: "No se pudo interpretar el resultado final." };
        }
      } else if (leftover.trim().startsWith("SUMMARY::")) {
        handleSummaryPayload(leftover.trim().substring("SUMMARY::".length));
      } else {
        appendLog(`${leftover}\n`);
      }
    }
    return finalResult;
  };

  const runActualizar = async () => {
    const empresa = empresaSelect?.value;
    const dominio = dominioSelect?.value;
    if (!empresa) {
      showResult("ERROR", "Selecciona una empresa.");
      return;
    }
    resetResult();
    resetSummaryView();
    resetResultsView();
    if (logOutput) {
      logOutput.textContent = "";
    }
    setStatus("Actualizando datos...", "muted");
    startSummaryRun();
    try {
      const resp = await fetch(actualizarUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ empresa, dominio }),
      });
      if (!resp.ok || !resp.body) {
        showResult("ERROR", `Actualizacion fallo (HTTP ${resp.status}).`);
        setStatus("Error", "ERROR");
        finishSummaryRun("error");
        return;
      }
      const result = await handleStream(resp);
      if (result) {
        showResult(result.status, result.message);
        setStatus(result.status === "SUCCESS" ? "Completado" : "Error", result.status);
        finishSummaryRun(result.status === "SUCCESS" ? "success" : "error");
        if (result.status === "SUCCESS") {
          await loadList();
        }
      } else {
        showResult("ERROR", "El proceso finalizo sin entregar un resultado final.");
        setStatus("Error", "ERROR");
        finishSummaryRun("error");
      }
    } catch (err) {
      showResult("ERROR", `Actualizacion fallo: ${err}`);
      setStatus("Error", "ERROR");
      finishSummaryRun("error");
    }
  };

  const runConsulta = async () => {
    const empresa = empresaSelect?.value;
    const dominio = dominioSelect?.value || "CC";
    if (!empresa) {
      showResult("ERROR", "Selecciona una empresa.");
      return;
    }
    const rtus = Array.from(selectedRtus);
    if (!rtus.length) {
      showResult("ERROR", "Selecciona al menos una RTU/SAS.");
      return;
    }
    resetResult();
    resetSummaryView();
    resetResultsView();
    if (logOutput) {
      logOutput.textContent = "";
    }
    setStatus("Consultando...", "muted");
    startSummaryRun();
    activatePanel("summary");
    try {
      const params = new URLSearchParams();
      params.append("empresa", empresa);
      params.append("dominio", dominio);
      rtus.forEach((r) => params.append("rtus", r));
      const resp = await fetch(runUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params,
      });
      if (!resp.ok || !resp.body) {
        showResult("ERROR", `Consulta fallo (HTTP ${resp.status}).`);
        setStatus("Error", "ERROR");
        finishSummaryRun("error");
        return;
      }
      const result = await handleStream(resp);
      if (result) {
        showResult(result.status, result.message);
        setStatus(result.status === "SUCCESS" ? "Completado" : "Error", result.status);
        finishSummaryRun(result.status === "SUCCESS" ? "success" : "error");
        if (result.status === "SUCCESS") {
          resultsNeedsRefresh = true;
          sheetCache.clear();
          await loadResults({ force: true, autoActivate: true, sheet: null });
        }
      } else {
        showResult("ERROR", "El proceso finalizo sin entregar un resultado final.");
        setStatus("Error", "ERROR");
        finishSummaryRun("error");
      }
    } catch (err) {
      showResult("ERROR", `Consulta fallo: ${err}`);
      setStatus("Error", "ERROR");
      finishSummaryRun("error");
    }
  };

  if (actualizarBtn) {
    actualizarBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      actualizarBtn.disabled = true;
      consultarBtn && (consultarBtn.disabled = true);
      await runActualizar();
      actualizarBtn.disabled = false;
      consultarBtn && (consultarBtn.disabled = false);
    });
  }

  if (consultarBtn) {
    consultarBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      consultarBtn.disabled = true;
      actualizarBtn && (actualizarBtn.disabled = true);
      await runConsulta();
      consultarBtn.disabled = false;
      actualizarBtn && (actualizarBtn.disabled = false);
    });
  }

  if (empresaSelect) {
    empresaSelect.addEventListener("change", async () => {
      selectedRtus.clear();
      if (buscador) buscador.value = "";
      await loadList();
    });
    if (empresaSelect.options.length === 2 && !empresaSelect.value) {
      empresaSelect.selectedIndex = 1;
      loadList();
    }
  }

  if (dominioSelect) {
    dominioSelect.addEventListener("change", async () => {
      selectedRtus.clear();
      await loadList();
    });
  }

  if (buscador) {
    buscador.addEventListener("input", () => loadList());
  }

  if (empresaSelect && empresaSelect.value) {
    loadList();
  }

  resetSummaryView();
  resetResultsView();
});
