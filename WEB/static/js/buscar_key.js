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
  const downloadBtn = document.getElementById("resultDownloadBtn");

  let resultsCache = null;
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
    resultsCache = null;
    resultsNeedsRefresh = true;
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
    if (downloadBtn) {
      downloadBtn.disabled = true;
      downloadBtn.dataset.href = "";
    }
  };

  const renderResults = (data) => {
    if (!resultPanel) return;

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
        resultEmpty.textContent = rows.length
          ? "No hay columnas disponibles para mostrar."
          : "La búsqueda finalizó sin coincidencias.";
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
        const suffix = hasMore ? ` de ${total} registros (vista previa).` : ` registro${plural}.`;
        const prefix = hasMore ? `Mostrando ${rows.length}` : `Mostrando ${rows.length}`;
        resultMeta.textContent = `${prefix}${suffix}`;
      } else {
        resultMeta.textContent = "Sin registros para mostrar.";
      }
    }

    if (downloadBtn) {
      const url = data?.download_url || "";
      downloadBtn.dataset.href = url;
      downloadBtn.disabled = !url;
    }
  };

  const loadResults = async ({ force = false, autoActivate = false } = {}) => {
    if (!resultPanel) {
      if (autoActivate) activatePanel("results");
      return;
    }
    if (resultsLoading) {
      if (autoActivate) activatePanel("results");
      return;
    }
    if (!force && !resultsNeedsRefresh && resultsCache) {
      renderResults(resultsCache);
      if (autoActivate) activatePanel("results");
      return;
    }

    resultsLoading = true;
    resultHead.innerHTML = "";
    resultBody.innerHTML = "";
    if (resultMeta) {
      resultMeta.textContent = "Cargando resultados...";
    }
    if (downloadBtn) {
      downloadBtn.disabled = true;
      downloadBtn.dataset.href = "";
    }

    try {
      const response = await fetch("/buscar/key/result/data", { cache: "no-store" });
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("No se encontraron resultados recientes. Ejecuta una búsqueda para generar un informe.");
        }
        throw new Error(`Error al cargar resultados (HTTP ${response.status}).`);
      }
      const data = await response.json();
      resultsCache = data;
      resultsNeedsRefresh = false;
      renderResults(data);
    } catch (error) {
      resultsCache = null;
      resultsNeedsRefresh = true;
      if (resultPanel) {
        resultPanel.classList.add("is-empty");
      }
      if (resultEmpty) {
        resultEmpty.textContent =
          error instanceof Error ? error.message : "No se pudieron cargar los resultados.";
      }
      if (resultMeta) {
        resultMeta.textContent = "";
      }
      if (downloadBtn) {
        downloadBtn.disabled = true;
        downloadBtn.dataset.href = "";
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
        await loadResults({ force: true, autoActivate: true });
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
