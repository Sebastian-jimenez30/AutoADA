document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("buscarKeyForm");
  if (!form) return;

  const logOutput = document.getElementById("logOutput");
  const ejecutarBtn = document.getElementById("buscarKeyBtn");
  const verificarBtn = document.getElementById("verificarBtn");
  const aplicarInput = document.getElementById("aplicar");
  const piBtn = document.getElementById("consultarPiBtn");
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
  const fileListContainer = document.getElementById("resultFileList");
  const resultDetails = document.getElementById("resultDetails");
  const summaryPanel = document.getElementById("summaryPanel");
  const summaryList = document.getElementById("summaryList");
  const summaryStatus = document.getElementById("summaryStatus");
  const summaryLoader = document.getElementById("summaryLoader");
  const summaryEmpty = document.getElementById("summaryEmpty");
  const paramsCards = Array.from(document.querySelectorAll(".params-card"));

  const runUrl =
    form.dataset.runUrl || form.getAttribute("action") || "/buscar/key/run";
  const resultBaseUrl =
    form.dataset.resultUrl || "/buscar/key/result/data";
  const fileDownloadBase = form.dataset.fileDownload || "";
  const piUrl = form.dataset.piUrl || "";
  const confirmUrl = form.dataset.confirmUrl || "";
  const confirmModal = document.getElementById("confirmModal");
  const confirmList = document.getElementById("confirmList");
  const confirmAccept = document.getElementById("confirmAccept");
  const confirmCancel = document.getElementById("confirmCancel");
  const origin = window.location.origin;

  const buildResultUrl = (sheetValue) => {
    try {
      const url = new URL(resultBaseUrl, origin);
      if (sheetValue) {
        url.searchParams.set("sheet", sheetValue);
      } else {
        url.searchParams.delete("sheet");
      }
      return url.toString();
    } catch {
      if (sheetValue) {
        const separator = resultBaseUrl.includes("?") ? "&" : "?";
        return `${resultBaseUrl}${separator}sheet=${encodeURIComponent(
          sheetValue,
        )}`;
      }
      return resultBaseUrl;
    }
  };

  const buildDownloadUrl = (filePath) => {
    if (!fileDownloadBase || !filePath) return "";
    try {
      const url = new URL(fileDownloadBase, origin);
      if (!url.searchParams.has("path")) {
        url.searchParams.append("path", filePath);
      } else {
        url.searchParams.set("path", filePath);
      }
      return url.toString();
    } catch {
      const separator = fileDownloadBase.includes("?") ? "&" : "?";
      return `${fileDownloadBase}${separator}path=${encodeURIComponent(
        filePath,
      )}`;
    }
  };

  const sheetCache = new Map();
  let availableSheets = [];
  let activeSheet = null;
  let resultsNeedsRefresh = true;
  let resultsLoading = false;
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

    if (target === "results" && resultPanel) {
      resultPanel.removeAttribute("hidden");
    }
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
      resultEmpty.textContent =
        "Los resultados aparecerán aquí al finalizar el proceso.";
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
    }
    if (resultDetails) {
      resultDetails.innerHTML = "";
      resultDetails.classList.remove("is-visible");
    }
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
      summaryEmpty.textContent =
        "Los mensajes generales aparecerán aquí durante la ejecución.";
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
      appendSummaryMessage("El proceso finalizó con errores.", "error");
    } else {
      setSummaryStatus("Finalizado", "info");
    }
  };

  const handleSummaryPayload = (payload) => {
    if (!summaryPanel) return;
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

  resetSummaryView();

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
  };

  const renderDetails = (details) => {
    if (!resultDetails) return;
    const lines = Array.isArray(details) ? details.filter(Boolean) : [];
    if (!lines.length) {
      resultDetails.innerHTML = "";
      resultDetails.classList.remove("is-visible");
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
  };

  const renderResults = (data) => {
    if (!resultPanel || !data) return;

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
      resultHead.innerHTML = "";
      resultBody.innerHTML = "";
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
          resultEmpty.textContent =
            "No hay tabla para mostrar. Revisa los archivos generados.";
        } else if (message) {
          resultEmpty.textContent = message;
        } else {
          const sheetLabel = activeSheet
            ? `Hoja "${activeSheet}"`
            : "Hoja seleccionada";
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
            : ` de más de ${rows.length} registros (vista previa).`
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
    }
    if (resultDetails) {
      resultDetails.innerHTML = "";
      resultDetails.classList.remove("is-visible");
    }

    try {
      const response = await fetch(buildResultUrl(targetSheet), {
        cache: "no-store",
      });
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(
            "No se encontraron resultados recientes. Ejecuta una búsqueda para generar un informe.",
          );
        }
        throw new Error(
          `Error al cargar resultados (HTTP ${response.status}).`,
        );
      }
      const data = await response.json();
      if (data?.active_sheet) {
        sheetCache.set(data.active_sheet, data);
      }
      resultsNeedsRefresh = false;
      renderResults(data);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "No se pudieron cargar los resultados.";
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
      }
      if (resultDetails) {
        resultDetails.innerHTML = "";
        resultDetails.classList.remove("is-visible");
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

  const setStatus = (text, variant = "muted") => {
    if (!statusBadge) return;
    statusBadge.textContent = text;
    statusBadge.dataset.variant = variant;
  };

  const showResult = (status, message) => {
    if (!resultBox) return;
    resultBox.textContent = message;
    resultBox.className = `result-message ${
      status === "SUCCESS" ? "success" : "error"
    }`;
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

  const showConfirmModal = (files) =>
    new Promise((resolve) => {
      if (!confirmModal || !confirmAccept || !confirmCancel || !confirmList) {
        // fallback: confirm nativo
        const ok = window.confirm("Confirma que ejecutaste los archivos Delete/Purge en HSH?");
        resolve(ok);
        return;
      }
      confirmList.innerHTML = "";
      if (Array.isArray(files) && files.length) {
        files.forEach((file) => {
          const li = document.createElement("li");
          li.textContent = file;
          confirmList.appendChild(li);
        });
      } else {
        const li = document.createElement("li");
        li.textContent = "Sin archivos detectados (revisa la salida).";
        confirmList.appendChild(li);
      }
      confirmModal.classList.add("is-visible");
      const cleanup = (result) => {
        confirmModal.classList.remove("is-visible");
        resolve(result);
      };
      confirmAccept.onclick = () => cleanup(true);
      confirmCancel.onclick = () => cleanup(false);
    });

  const handleStream = async (response, allowConfirm = true) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let finalResult = null;
    let confirmPending = false;
    let pendingFiles = [];

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
        if (trimmed.startsWith("CONFIRM_DELETE::")) {
          if (allowConfirm) {
            confirmPending = true;
            appendSummaryMessage("Pendiente confirmación de Delete/Purge...", "warning");
          }
          continue;
        }
        if (trimmed.startsWith("RESULT::")) {
          try {
            finalResult = JSON.parse(trimmed.substring("RESULT::".length));
            if (finalResult && finalResult.delete_files) {
              pendingFiles = pendingFiles.concat(finalResult.delete_files || []);
            }
            if (finalResult && finalResult.purge_files) {
              pendingFiles = pendingFiles.concat(finalResult.purge_files || []);
            }
          } catch {
            finalResult = {
              status: "ERROR",
              message: "No fue posible interpretar el resultado final.",
            };
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
          finalResult = JSON.parse(
            leftover.trim().substring("RESULT::".length),
          );
          if (finalResult && finalResult.delete_files) {
            pendingFiles = pendingFiles.concat(finalResult.delete_files || []);
          }
          if (finalResult && finalResult.purge_files) {
            pendingFiles = pendingFiles.concat(finalResult.purge_files || []);
          }
        } catch {
          finalResult = {
            status: "ERROR",
            message: "No fue posible interpretar el resultado final.",
          };
        }
      } else if (leftover.trim().startsWith("SUMMARY::")) {
        handleSummaryPayload(leftover.trim().substring("SUMMARY::".length));
      } else if (leftover.trim().startsWith("CONFIRM_DELETE::")) {
        if (allowConfirm) {
          confirmPending = true;
          appendSummaryMessage("Pendiente confirmación de Delete/Purge...", "warning");
        }
      } else {
        appendLog(`${leftover}\n`);
      }
    }

    if (confirmPending && confirmUrl && allowConfirm) {
      const proceed = await showConfirmModal(pendingFiles);
      if (!proceed) {
        return { status: "ERROR", message: "Confirmación cancelada por el usuario." };
      }
      appendSummaryMessage("Ejecutando confirmación Delete/Purge...", "info");
      try {
        const respConfirm = await fetch(confirmUrl, { method: "POST" });
        if (respConfirm.ok && respConfirm.body) {
          const confirmResult = await handleStream(respConfirm, true);
          if (confirmResult) {
            finalResult = confirmResult;
          }
        } else {
          appendLog(`[CONFIRM] Respuesta inesperada (${respConfirm.status})\n`);
        }
      } catch (err) {
        appendLog(`[CONFIRM] Error: ${err}\n`);
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
      response = await fetch(runUrl, {
        method: "POST",
        body: formData,
      });
    } catch (error) {
      appendLog(`[CLIENT] Error de red: ${error}\n`);
      showResult("ERROR", "No fue posible conectar con el servidor.");
      setStatus("Error", "ERROR");
      finishSummaryRun("error");
      return;
    }

    if (!response.ok || !response.body) {
      const text = await response.text();
      appendLog(`[SERVER] Respuesta inesperada (${response.status}): ${text}\n`);
      showResult(
        "ERROR",
        "La ejecución no pudo iniciarse. Verifica los parámetros.",
      );
      setStatus("Error", "ERROR");
      finishSummaryRun("error");
      return;
    }

    const isApplyRun = !!(aplicarInput && aplicarInput.value);
    const result = await handleStream(response, isApplyRun);
    if (result) {
      showResult(result.status, result.message);
      setStatus(result.status === "SUCCESS" ? "Completado" : "Error", result.status);
      if (result.status === "SUCCESS") {
        resultsNeedsRefresh = true;
        sheetCache.clear();
        await loadResults({ force: true, autoActivate: true, sheet: null });
      }
      finishSummaryRun(result.status === "SUCCESS" ? "success" : "error");
    } else {
      showResult(
        "ERROR",
        "El proceso finalizó sin entregar un resultado final.",
      );
      setStatus("Error", "ERROR");
      finishSummaryRun("error");
    }
  };

  const setParamsVisibility = () => {
    if (!paramsCards.length) return;
    paramsCards.forEach((card) => {
      card.classList.remove("is-hidden");
      card.style.maxHeight = "";
    });
  };

  const ejecutarConsultaPi = async () => {
    if (!piUrl) {
      showResult("ERROR", "No hay endpoint de PI configurado.");
      return;
    }
    setStatus("Consultando PI...", "muted");
    startSummaryRun();
    try {
      const response = await fetch(piUrl, { method: "POST" });
      if (!response.ok || !response.body) {
        const txt = await response.text();
        appendLog(`[PI] Respuesta inesperada (${response.status}): ${txt}\n`);
        setStatus("Error", "ERROR");
        finishSummaryRun("error");
        return;
      }
      const result = await handleStream(response);
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
        showResult("ERROR", "La consulta PI finalizó sin resultado.");
        setStatus("Error", "ERROR");
        finishSummaryRun("error");
      }
    } catch (error) {
      appendLog(`[PI] Error de red: ${error}\n`);
      showResult("ERROR", "No fue posible conectar para la consulta PI.");
      setStatus("Error", "ERROR");
      finishSummaryRun("error");
    }
  };

  const launchRun = async () => {
    activatePanel("summary");
    resetResultsView();
    setStatus("Ejecutando...");
    startSummaryRun();
    await ejecutarBusqueda();
  };

  if (verificarBtn) {
    verificarBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      if (aplicarInput) {
        aplicarInput.value = "";
      }
      ejecutarBtn && (ejecutarBtn.disabled = true);
      verificarBtn.disabled = true;
      await launchRun();
      ejecutarBtn && (ejecutarBtn.disabled = false);
      verificarBtn.disabled = false;
      setParamsVisibility(false);
    });
  }

  if (ejecutarBtn) {
    ejecutarBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      if (aplicarInput) {
        aplicarInput.value = "1";
      }
      ejecutarBtn.disabled = true;
      if (verificarBtn) verificarBtn.disabled = true;
      await launchRun();
      ejecutarBtn.disabled = false;
      if (verificarBtn) verificarBtn.disabled = false;
      setParamsVisibility(false);
    });
  }

  if (piBtn) {
    piBtn.addEventListener("click", async (event) => {
      event.preventDefault();
      piBtn.disabled = true;
      ejecutarBtn && (ejecutarBtn.disabled = true);
      verificarBtn && (verificarBtn.disabled = true);
      await ejecutarConsultaPi();
      piBtn.disabled = false;
      ejecutarBtn && (ejecutarBtn.disabled = false);
      verificarBtn && (verificarBtn.disabled = false);
    });
  }

  // Fallback genérico: si el formulario se envía por submit (p.ej. Buscar Key con un solo botón)
  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await launchRun();
      setParamsVisibility(false);
    });
  }
});
