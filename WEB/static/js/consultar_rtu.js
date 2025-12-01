document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("buscarKeyForm");
  if (!form) return;

  const empresaSelect = document.getElementById("empresa");
  const buscador = document.getElementById("buscadorRtu");
  const rtuListContainer = document.getElementById("rtuList");
  const rtuCountLabel = document.getElementById("rtuCount");
  const actualizarBtn = document.getElementById("actualizarRtuBtn");
  const consultarBtn = document.getElementById("verificarBtn");

  const runUrl = form.dataset.runUrl || "/consultar/rtu/run";
  const actualizarUrl = "/consultar/rtu/actualizar";
  const listUrl = "/consultar/rtu/list";
  const resultDownloadBase = form.dataset.fileDownload || "/consultar/rtu/result/download";
  const resultPanel = document.getElementById("resultPanel");
  const resultHead = document.getElementById("resultTableHead");
  const resultBody = document.getElementById("resultTableBody");
  const resultEmpty = document.getElementById("resultEmptyState");
  const downloadBtn = document.getElementById("resultDownloadBtn");
  const resultMeta = document.getElementById("resultMeta");

  const logOutput = document.getElementById("logOutput");
  const statusBadge = document.getElementById("logStatus");
  const resultBox = document.getElementById("resultMessage");
  const tabs = Array.from(document.querySelectorAll(".output-tab"));
  const panels = Array.from(document.querySelectorAll(".output-panel"));

  let selectedRtus = new Set();
  let currentItems = [];

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

  const renderResults = (data) => {
    if (!resultPanel || !resultHead || !resultBody) return;
    resultHead.innerHTML = "";
    resultBody.innerHTML = "";
    if (!data || !data.columns || data.columns.length === 0 || !data.rows) {
      resultPanel.classList.add("is-empty");
      if (resultEmpty) resultEmpty.textContent = data?.message || "Sin resultados.";
      return;
    }
    resultPanel.classList.remove("is-empty");
    const trHead = document.createElement("tr");
    data.columns.forEach((col) => {
      const th = document.createElement("th");
      th.textContent = col;
      trHead.appendChild(th);
    });
    resultHead.appendChild(trHead);

    data.rows.forEach((row) => {
      const tr = document.createElement("tr");
      data.columns.forEach((col) => {
        const td = document.createElement("td");
        const val = row[col];
        td.textContent = val === null || val === undefined ? "" : val;
        tr.appendChild(td);
      });
      resultBody.appendChild(tr);
    });
    if (downloadBtn) {
      downloadBtn.disabled = !data.download_url;
      downloadBtn.dataset.href = data.download_url || "";
    }
    if (resultMeta) {
      resultMeta.textContent = `${data.active_sheet || ""} (${data.total || data.rows.length} registros${data.has_more ? " +" : ""})`;
    }
  };

  const loadResults = async () => {
    try {
      const resp = await fetch(form.dataset.resultUrl || "/consultar/rtu/result", { cache: "no-store" });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const data = await resp.json();
      renderResults(data);
    } catch (err) {
      if (resultPanel) {
        resultPanel.classList.add("is-empty");
      }
      if (resultEmpty) {
        resultEmpty.textContent = "No hay resultados disponibles.";
      }
      if (downloadBtn) {
        downloadBtn.disabled = true;
        downloadBtn.dataset.href = "";
      }
      if (resultMeta) {
        resultMeta.textContent = "";
      }
    }
  };

  const setStatus = (text, variant = "muted") => {
    if (!statusBadge) return;
    statusBadge.textContent = text;
    statusBadge.dataset.variant = variant;
  };

  const resetResult = () => {
    if (!resultBox) return;
    resultBox.textContent = "";
    resultBox.className = "result-message";
    resultBox.style.display = "none";
  };

  const showResult = (status, message) => {
    if (!resultBox) return;
    resultBox.textContent = message;
    resultBox.className = `result-message ${status === "SUCCESS" ? "success" : "error"}`;
    resultBox.style.display = "block";
  };

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
      if (selectedRtus.has(item)) {
        div.classList.add("is-selected");
      }
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
    if (rtuCountLabel) {
      rtuCountLabel.textContent = `${currentItems.length} RTU/SAS`;
    }
  };

  const loadList = async () => {
    const empresa = empresaSelect?.value;
    if (!empresa) return;
    const params = new URLSearchParams();
    params.set("empresa", empresa);
    const query = (buscador?.value || "").trim();
    if (query) params.set("search", query);
    try {
      const resp = await fetch(`${listUrl}?${params.toString()}`, { cache: "no-store" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      currentItems = data?.rtus || [];
      // mantener selección válida
      selectedRtus = new Set([...selectedRtus].filter((r) => currentItems.includes(r)));
      renderList();
    } catch (err) {
      currentItems = [];
      renderList();
      appendLog(`[CLIENT] No se pudo cargar RTUs: ${err}\n`);
    }
  };

  if (empresaSelect) {
    empresaSelect.addEventListener("change", async () => {
      selectedRtus.clear();
      await loadList();
    });
  }
  if (buscador) {
    buscador.addEventListener("input", () => {
      loadList();
    });
  }

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.target;
      activatePanel(target);
    });
  });

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
          continue;
        }
        if (trimmed.startsWith("RESULT::")) {
          try {
            finalResult = JSON.parse(trimmed.substring("RESULT::".length));
          } catch {
            finalResult = { status: "ERROR", message: "No se pudo interpretar el resultado." };
          }
          continue;
        }
        appendLog(`${cleaned}\n`);
      }
    }
    const leftover = buffer.replace(/\r/g, "").trim();
    if (leftover.startsWith("RESULT::")) {
      try {
        finalResult = JSON.parse(leftover.substring("RESULT::".length));
      } catch {
        finalResult = { status: "ERROR", message: "No se pudo interpretar el resultado." };
      }
    }
    return finalResult;
  };

  const runActualizar = async () => {
    const empresa = empresaSelect?.value;
    if (!empresa) {
      showResult("ERROR", "Selecciona una empresa.");
      return;
    }
    resetResult();
    if (logOutput) logOutput.textContent = "";
    setStatus("Actualizando datos...");
    try {
      const resp = await fetch("/consultar/rtu/actualizar", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ empresa }),
      });
      if (!resp.ok || !resp.body) {
        showResult("ERROR", `Actualización falló (HTTP ${resp.status}).`);
        setStatus("Error", "ERROR");
        return;
      }
      const result = await handleStream(resp);
      if (result) {
        showResult(result.status, result.message);
        setStatus(result.status === "SUCCESS" ? "Completado" : "Error", result.status);
        if (result.status === "SUCCESS") {
          await loadList();
        }
      }
    } catch (err) {
      showResult("ERROR", `Actualización falló: ${err}`);
      setStatus("Error", "ERROR");
    }
  };

  const runConsulta = async () => {
    const empresa = empresaSelect?.value;
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
    if (logOutput) logOutput.textContent = "";
    setStatus("Consultando...");
    activatePanel("console");
    try {
      const params = new URLSearchParams();
      params.append("empresa", empresa);
      rtus.forEach((r) => params.append("rtus", r));
      const resp = await fetch(runUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params,
      });
      if (!resp.ok || !resp.body) {
        showResult("ERROR", `Consulta falló (HTTP ${resp.status}).`);
        setStatus("Error", "ERROR");
        return;
      }
      const result = await handleStream(resp);
      if (result) {
        showResult(result.status, result.message);
        setStatus(result.status === "SUCCESS" ? "Completado" : "Error", result.status);
        if (result.files && result.files.length) {
          // descargar primero
          const filePath = result.files[0];
          const url = `${resultDownloadBase}?path=${encodeURIComponent(filePath)}`;
          window.location.href = url;
        }
      }
    } catch (err) {
      showResult("ERROR", `Consulta falló: ${err}`);
      setStatus("Error", "ERROR");
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
      await loadResults();
    });
  }

  // Init list if empresa preselected
  if (empresaSelect && empresaSelect.value) {
    loadList();
  }
});
        if (result && result.status === "SUCCESS") {
          await loadResults();
          activatePanel("results");
        }
