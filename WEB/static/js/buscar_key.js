document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("buscarKeyForm");
  const logOutput = document.getElementById("logOutput");
  const ejecutarBtn = document.getElementById("buscarKeyBtn");
  const limpiarBtn = document.getElementById("limpiarLogBtn");
  const statusBadge = document.getElementById("logStatus");
  const resultBox = document.getElementById("resultMessage");

  const setStatus = (text, variant = "muted") => {
    statusBadge.textContent = text;
    statusBadge.dataset.variant = variant;
  };

  const showResult = (status, message) => {
    resultBox.textContent = message;
    resultBox.className = `result-message ${status === "SUCCESS" ? "success" : "error"}`;
    resultBox.style.display = "block";
  };

  const resetResult = () => {
    resultBox.textContent = "";
    resultBox.className = "result-message";
    resultBox.style.display = "none";
  };

  const appendLog = (text) => {
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
      if (done) {
        break;
      }
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
          } catch (err) {
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
        } catch (err) {
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
    logOutput.textContent = "";

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
      setStatus("Error");
      return;
    }

    if (!response.ok || !response.body) {
      const text = await response.text();
      appendLog(`[SERVER] Respuesta inesperada (${response.status}): ${text}\n`);
      showResult("ERROR", "La ejecución no pudo iniciarse. Verifica los parámetros.");
      setStatus("Error");
      return;
    }

    const result = await handleStream(response);
    if (result) {
      showResult(result.status, result.message);
      setStatus(result.status === "SUCCESS" ? "Completado" : "Error", result.status);
    } else {
      showResult("ERROR", "El proceso finalizó sin entregar un resultado final.");
      setStatus("Error");
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    ejecutarBtn.disabled = true;
    setStatus("Ejecutando...");
    await ejecutarBusqueda();
    ejecutarBtn.disabled = false;
  });

  limpiarBtn.addEventListener("click", () => {
    logOutput.textContent = "";
    setStatus("En espera");
    resetResult();
  });
});
