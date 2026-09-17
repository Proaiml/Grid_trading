document.addEventListener("DOMContentLoaded", () => {
  // --- DOM Elementleri ---
  const symbolInput = document.getElementById("symbolInput");
  const priceLowInput = document.getElementById("priceLowInput");
  const priceHighInput = document.getElementById("priceHighInput");
  const gridNumberSlider = document.getElementById("gridNumberSlider");
  const gridNumberInput = document.getElementById("gridNumberInput");
  const gridNumVal = document.getElementById("gridNumVal");
  const budgetInput = document.getElementById("budgetInput");
  const pollIntervalInput = document.getElementById("pollIntervalInput");
  const recoveryPolicySelect = document.getElementById("recoveryPolicySelect");
  const liveConfirmationInput = document.getElementById("liveConfirmationInput");
  const apiKeyInput = document.getElementById("apiKeyInput");
  const apiSecretInput = document.getElementById("apiSecretInput");
  const liveWarningBox = document.getElementById("liveWarningBox");

  const badgeMode = document.getElementById("badgeMode");
  const badgePolicy = document.getElementById("badgePolicy");

  // Canlı Hesaplama Elementleri
  const calcSectors = document.getElementById("calcSectors");
  const calcStep = document.getElementById("calcStep");
  const calcStepPct = document.getElementById("calcStepPct");
  const calcRange = document.getElementById("calcRange");
  const calcSectorBudget = document.getElementById("calcSectorBudget");
  const calcCycleProfit = document.getElementById("calcCycleProfit");

  // KPI Elementleri
  const kpiRealizedProfit = document.getElementById("kpiRealizedProfit");
  const kpiRoi = document.getElementById("kpiRoi");
  const kpiCompletedTrades = document.getElementById("kpiCompletedTrades");
  const kpiTradesDetail = document.getElementById("kpiTradesDetail");
  const kpiTotalEquity = document.getElementById("kpiTotalEquity");
  const kpiAssetHoldings = document.getElementById("kpiAssetHoldings");
  const kpiMaxDd = document.getElementById("kpiMaxDd");
  const pnlTrendTag = document.getElementById("pnlTrendTag");

  // Tablo & Kontroller
  const tradesTableBody = document.getElementById("tradesTableBody");
  const tableTradeCount = document.getElementById("tableTradeCount");
  const simStepsSelect = document.getElementById("simStepsSelect");
  const btnRunSim = document.getElementById("btnRunSim");
  const btnSaveConfig = document.getElementById("btnSaveConfig");
  const btnSelfTest = document.getElementById("btnSelfTest");
  const btnGenerateBat = document.getElementById("btnGenerateBat");

  // Modallar
  const selfTestModal = document.getElementById("selfTestModal");
  const selfTestConsole = document.getElementById("selfTestConsole");
  const btnCloseSelfTest = document.getElementById("btnCloseSelfTest");
  const btnCloseSelfTest2 = document.getElementById("btnCloseSelfTest2");
  const btnRerunSelfTest = document.getElementById("btnRerunSelfTest");

  const batModal = document.getElementById("batModal");
  const batCodePreview = document.getElementById("batCodePreview");
  const batFilenameInput = document.getElementById("batFilenameInput");
  const btnCloseBatModal = document.getElementById("btnCloseBatModal");
  const btnSaveBatToDisk = document.getElementById("btnSaveBatToDisk");
  const btnDownloadBatFile = document.getElementById("btnDownloadBatFile");

  const toastContainer = document.getElementById("toastContainer");

  // Durum Değişkenleri
  let currentMode = "paper";
  let currentScenario = "sideways";
  let priceChartInstance = null;
  let profitChartInstance = null;
  let lastBatContent = "";

  // --- Toast Bildirimi ---
  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    let icon = "ℹ️";
    if (type === "success") icon = "✅";
    if (type === "error") icon = "❌";
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(50px)";
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  }

  // --- Canlı Hesaplamalar (Kullanıcı Yazarken) ---
  function updateLiveCalculations() {
    const low = parseFloat(priceLowInput.value) || 0;
    const high = parseFloat(priceHighInput.value) || 0;
    const gridNum = parseInt(gridNumberInput.value) || 1;
    const budget = parseFloat(budgetInput.value) || 0;

    gridNumVal.textContent = gridNum;
    gridNumberSlider.value = gridNum;

    const sectorCount = gridNum + 1;
    calcSectors.textContent = `${sectorCount} Sektör`;

    if (high > low && low > 0) {
      const step = (high - low) / sectorCount;
      const range = high - low;
      const stepPct = (step / low) * 100;
      calcStep.textContent = `${step.toFixed(4)} $`;
      calcStepPct.textContent = `% ${stepPct.toFixed(2)}`;
      calcRange.textContent = `${range.toFixed(4)} $`;

      const sectorBudget = budget / sectorCount;
      calcSectorBudget.textContent = `${sectorBudget.toFixed(2)} $`;
      const estCycleProfit = sectorBudget * (stepPct / 100);
      calcCycleProfit.textContent = `~${estCycleProfit.toFixed(2)} $`;
    } else {
      calcStep.textContent = "-";
      calcStepPct.textContent = "-";
      calcRange.textContent = "-";
    }
  }

  gridNumberSlider.addEventListener("input", (e) => {
    gridNumberInput.value = e.target.value;
    updateLiveCalculations();
  });

  gridNumberInput.addEventListener("input", () => updateLiveCalculations());
  priceLowInput.addEventListener("input", () => updateLiveCalculations());
  priceHighInput.addEventListener("input", () => updateLiveCalculations());
  budgetInput.addEventListener("input", () => updateLiveCalculations());

  // Hızlı Sembol Etiketleri
  document.querySelectorAll(".tag-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sym = btn.dataset.symbol;
      symbolInput.value = sym;
      if (sym === "BTCUSDT") {
        priceLowInput.value = "55000";
        priceHighInput.value = "68000";
        budgetInput.value = "500";
      } else if (sym === "ETHUSDT") {
        priceLowInput.value = "2300";
        priceHighInput.value = "3100";
        budgetInput.value = "300";
      } else if (sym === "SOLUSDT") {
        priceLowInput.value = "120";
        priceHighInput.value = "180";
        budgetInput.value = "200";
      } else if (sym === "BNBUSDT") {
        priceLowInput.value = "500";
        priceHighInput.value = "650";
        budgetInput.value = "250";
      } else if (sym === "MATICUSDT") {
        priceLowInput.value = "1.42";
        priceHighInput.value = "1.70";
        budgetInput.value = "60";
      }
      updateLiveCalculations();
      runSimulation();
    });
  });

  // Mod Değişimi
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentMode = btn.dataset.mode;

      badgeMode.className = `badge ${currentMode}`;
      badgeMode.innerHTML = `<span class="dot">●</span> Mod: ${currentMode.toUpperCase()}`;

      if (currentMode === "live") {
        liveWarningBox.style.display = "block";
      } else {
        liveWarningBox.style.display = "none";
      }
    });
  });

  // Senaryo Seçici
  document.querySelectorAll(".scenario-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll(".scenario-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      currentScenario = pill.dataset.scenario;
      runSimulation();
    });
  });

  // --- API: Config Yükleme ---
  async function loadConfig() {
    try {
      const res = await fetch("/api/config");
      if (!res.ok) throw new Error("Config alınamadı");
      const cfg = await res.json();

      if (cfg.symbol) symbolInput.value = cfg.symbol;
      if (cfg.price_low) priceLowInput.value = cfg.price_low;
      if (cfg.price_high) priceHighInput.value = cfg.price_high;
      if (cfg.grid_number) {
        gridNumberInput.value = cfg.grid_number;
        gridNumberSlider.value = cfg.grid_number;
      }
      if (cfg.total_quote_budget) budgetInput.value = cfg.total_quote_budget;
      if (cfg.poll_interval_seconds) pollIntervalInput.value = cfg.poll_interval_seconds;
      if (cfg.restart_recovery_policy) {
        recoveryPolicySelect.value = cfg.restart_recovery_policy;
        badgePolicy.textContent = `🛡️ ${cfg.restart_recovery_policy}`;
      }
      if (cfg.live_trading_confirmation) liveConfirmationInput.value = cfg.live_trading_confirmation;

      if (cfg.mode) {
        currentMode = cfg.mode.toLowerCase();
        document.querySelectorAll(".mode-btn").forEach((b) => {
          b.classList.toggle("active", b.dataset.mode === currentMode);
        });
        badgeMode.className = `badge ${currentMode}`;
        badgeMode.innerHTML = `<span class="dot">●</span> Mod: ${currentMode.toUpperCase()}`;
        if (currentMode === "live") liveWarningBox.style.display = "block";
      }

      updateLiveCalculations();
      runSimulation();
    } catch (err) {
      console.warn("Config yüklenirken hata:", err);
      updateLiveCalculations();
      runSimulation();
    }
  }

  // --- API: Config Kaydetme ---
  btnSaveConfig.addEventListener("click", async () => {
    const payload = {
      mode: currentMode,
      symbol: symbolInput.value.trim().toUpperCase(),
      price_low: priceLowInput.value.trim(),
      price_high: priceHighInput.value.trim(),
      grid_number: parseInt(gridNumberInput.value),
      total_quote_budget: budgetInput.value.trim(),
      poll_interval_seconds: parseFloat(pollIntervalInput.value),
      restart_recovery_policy: recoveryPolicySelect.value,
      live_trading_confirmation: liveConfirmationInput.value.trim(),
      api_key: apiKeyInput.value.trim() || undefined,
      api_secret: apiSecretInput.value.trim() || undefined,
    };

    try {
      btnSaveConfig.disabled = true;
      btnSaveConfig.textContent = "Kaydediliyor...";
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Kaydedilemedi");

      showToast("Yapılandırma config.json dosyasına başarıyla yazıldı!", "success");
      badgePolicy.textContent = `🛡️ ${payload.restart_recovery_policy}`;
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnSaveConfig.disabled = false;
      btnSaveConfig.textContent = "💾 Config Kaydet";
    }
  });

  // --- API: Simülasyon Çalıştırma & Grafik Çizimi ---
  async function runSimulation() {
    const payload = {
      symbol: symbolInput.value.trim().toUpperCase() || "MATICUSDT",
      price_low: parseFloat(priceLowInput.value) || 1.42,
      price_high: parseFloat(priceHighInput.value) || 1.70,
      grid_number: parseInt(gridNumberInput.value) || 4,
      total_quote_budget: parseFloat(budgetInput.value) || 60,
      scenario: currentScenario,
      steps: parseInt(simStepsSelect.value) || 150,
      volatility: 1.0,
    };

    try {
      btnRunSim.disabled = true;
      btnRunSim.textContent = "⏳ Hesaplanıyor...";
      const res = await fetch("/api/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Simülasyon hatası");
      }
      const sim = await res.json();
      renderSimulationResults(sim);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnRunSim.disabled = false;
      btnRunSim.textContent = "▶️ Simülasyonu Yenile";
    }
  }

  btnRunSim.addEventListener("click", () => runSimulation());
  simStepsSelect.addEventListener("change", () => runSimulation());

  function renderSimulationResults(sim) {
    const stats = sim.stats;

    // KPI Güncellemesi
    const pnlPrefix = stats.total_realized_profit >= 0 ? "+" : "";
    kpiRealizedProfit.textContent = `${pnlPrefix}${stats.total_realized_profit.toFixed(2)} $`;
    kpiRealizedProfit.style.color = stats.total_realized_profit >= 0 ? "var(--color-green)" : "var(--color-red)";

    const roiPrefix = stats.roi_pct >= 0 ? "+" : "";
    kpiRoi.textContent = `% ${roiPrefix}${stats.roi_pct.toFixed(2)} Net Getiri`;
    kpiRoi.style.color = stats.roi_pct >= 0 ? "var(--color-green)" : "var(--color-red)";

    kpiCompletedTrades.textContent = `${stats.sell_count} Döngü`;
    kpiTradesDetail.textContent = `${stats.buy_count} Alım / ${stats.sell_count} Satım (Toplam ${stats.total_trades})`;

    kpiTotalEquity.textContent = `${stats.final_equity.toFixed(2)} $`;
    kpiAssetHoldings.textContent = `Nakit: ${stats.cash_left.toFixed(2)} $ | ${stats.open_positions_count} Açık Pozisyon (${stats.open_positions_value.toFixed(2)} $)`;

    kpiMaxDd.textContent = `% ${stats.max_drawdown_pct.toFixed(2)}`;
    pnlTrendTag.textContent = `Toplam Kâr: ${pnlPrefix}${stats.total_realized_profit.toFixed(2)} $ (${roiPrefix}% ${stats.roi_pct.toFixed(2)})`;

    // İşlem Tablosu Güncellemesi
    tableTradeCount.textContent = `${sim.trades.length} İşlem`;
    if (sim.trades.length === 0) {
      tradesTableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted); padding: 16px;">Bu aralıkta sınır geçişi gerçekleşmedi.</td></tr>`;
    } else {
      tradesTableBody.innerHTML = sim.trades
        .slice(-60)
        .reverse()
        .map((t) => {
          const isBuy = t.type === "BUY";
          const profitCol = isBuy ? "-" : `<span style="color: var(--color-green); font-weight: 700;">+${t.profit.toFixed(3)} $</span>`;
          return `
            <tr>
              <td>#${t.step}</td>
              <td><span class="type-tag ${t.type}">${isBuy ? "▲ AL" : "▼ SAT"}</span></td>
              <td><span style="color: var(--accent-gold);">${t.sector}</span></td>
              <td>${t.price.toFixed(4)} $</td>
              <td>${t.qty.toFixed(4)}</td>
              <td>${t.cost.toFixed(2)} $</td>
              <td>${profitCol}</td>
              <td>${t.cash_left.toFixed(2)} $</td>
            </tr>
          `;
        })
        .join("");
    }

    // Chart.js - Fiyat & Grid Seviyeleri Grafiği
    drawPriceChart(sim);

    // Chart.js - Kümülatif Kâr Eğrisi
    drawProfitChart(sim);
  }

  function drawPriceChart(sim) {
    const ctx = document.getElementById("priceChart").getContext("2d");
    if (priceChartInstance) {
      priceChartInstance.destroy();
    }

    const labels = sim.prices.map((_, idx) => `${idx}`);
    const tradeMap = {};
    sim.trades.forEach((t) => {
      tradeMap[t.step] = t;
    });

    const pointStyles = sim.prices.map((_, idx) => {
      const trade = tradeMap[idx];
      if (!trade) return "circle";
      return trade.type === "BUY" ? "triangle" : "triangle";
    });

    const pointColors = sim.prices.map((_, idx) => {
      const trade = tradeMap[idx];
      if (!trade) return "transparent";
      return trade.type === "BUY" ? "#0ecb81" : "#f6465d";
    });

    const pointRadius = sim.prices.map((_, idx) => {
      const trade = tradeMap[idx];
      if (!trade) return 0;
      return 6;
    });

    // Sektör yatay çizgileri
    const sectorDatasets = sim.sectors_info.map((s, idx) => ({
      label: s.name,
      data: sim.prices.map(() => s.low),
      borderColor: "rgba(255, 255, 255, 0.08)",
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
      fill: false,
      order: 10,
    }));

    // En üst sınır çizgisi
    const highBound = sim.sectors_info[sim.sectors_info.length - 1].high;
    sectorDatasets.push({
      label: "Price_High",
      data: sim.prices.map(() => highBound),
      borderColor: "rgba(246, 70, 93, 0.35)",
      borderWidth: 1.5,
      borderDash: [2, 2],
      pointRadius: 0,
      fill: false,
      order: 9,
    });

    // En alt sınır çizgisi
    const lowBound = sim.sectors_info[0].low;
    sectorDatasets.push({
      label: "Price_Low",
      data: sim.prices.map(() => lowBound),
      borderColor: "rgba(14, 203, 129, 0.35)",
      borderWidth: 1.5,
      borderDash: [2, 2],
      pointRadius: 0,
      fill: false,
      order: 9,
    });

    const datasets = [
      {
        label: `${sim.symbol} Fiyatı`,
        data: sim.prices,
        borderColor: "#f0b90b",
        borderWidth: 2,
        tension: 0.2,
        pointStyle: pointStyles,
        pointBackgroundColor: pointColors,
        pointBorderColor: pointColors,
        pointRadius: pointRadius,
        pointRotation: sim.prices.map((_, idx) => {
          const trade = tradeMap[idx];
          if (!trade) return 0;
          return trade.type === "SELL" ? 180 : 0;
        }),
        fill: false,
        order: 1,
      },
      ...sectorDatasets,
    ];

    priceChartInstance = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            mode: "index",
            intersect: false,
            callbacks: {
              label: (context) => {
                const idx = context.dataIndex;
                const trade = tradeMap[idx];
                if (context.datasetIndex === 0) {
                  let text = ` Fiyat: ${context.parsed.y.toFixed(4)} $`;
                  if (trade) {
                    text += ` | [${trade.type} @ ${trade.sector}] Miktar: ${trade.qty}`;
                    if (trade.profit > 0) text += ` | Kâr: +${trade.profit.toFixed(3)} $`;
                  }
                  return text;
                }
                return null;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: "rgba(255, 255, 255, 0.03)" },
            ticks: { color: "#6b7280", font: { size: 10 } },
          },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.05)" },
            ticks: {
              color: "#9ca3af",
              font: { family: "'JetBrains Mono', monospace", size: 10 },
              callback: (val) => `${val.toFixed(2)} $`,
            },
          },
        },
      },
    });
  }

  function drawProfitChart(sim) {
    const ctx = document.getElementById("profitChart").getContext("2d");
    if (profitChartInstance) {
      profitChartInstance.destroy();
    }

    const labels = sim.profit_curve.map((_, idx) => `${idx}`);

    profitChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Kümülatif Gerçekleşen Kâr ($)",
            data: sim.profit_curve,
            borderColor: "#0ecb81",
            backgroundColor: "rgba(14, 203, 129, 0.08)",
            borderWidth: 2,
            tension: 0.1,
            pointRadius: 0,
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => ` Gerçekleşen Kâr: +${ctx.parsed.y.toFixed(3)} $`,
            },
          },
        },
        scales: {
          x: { display: false },
          y: {
            grid: { color: "rgba(255, 255, 255, 0.04)" },
            ticks: {
              color: "#9ca3af",
              font: { family: "'JetBrains Mono', monospace", size: 9 },
              callback: (val) => `+${val.toFixed(2)} $`,
            },
          },
        },
      },
    });
  }

  // --- API: Self-Test Modal & Çalıştırma ---
  btnSelfTest.addEventListener("click", () => {
    selfTestModal.style.display = "flex";
    runSelfTest();
  });

  btnCloseSelfTest.addEventListener("click", () => (selfTestModal.style.display = "none"));
  btnCloseSelfTest2.addEventListener("click", () => (selfTestModal.style.display = "none"));
  btnRerunSelfTest.addEventListener("click", () => runSelfTest());

  async function runSelfTest() {
    selfTestConsole.textContent = "Bot çekirdeği 20.480 durum patikalı güvenlik testine tabi tutuluyor...\nLütfen bekleyin...";
    try {
      const res = await fetch("/api/self-test", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        selfTestConsole.innerHTML = `<span style="color: #34d399; font-weight: bold;">[BAŞARILI]</span>\n\n${data.output}`;
        showToast("Self-test tüm testleri başarıyla geçti!", "success");
      } else {
        selfTestConsole.innerHTML = `<span style="color: #f87171; font-weight: bold;">[HATA]</span>\n\n${data.output}`;
        showToast("Self-test başarısız oldu!", "error");
      }
    } catch (err) {
      selfTestConsole.textContent = `Hata oluştu: ${err.message}`;
    }
  }

  // --- API: .BAT Oluşturucu Modal ---
  btnGenerateBat.addEventListener("click", async () => {
    batModal.style.display = "flex";
    batCodePreview.textContent = "Script oluşturuluyor...";
    try {
      const res = await fetch("/api/generate-bat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          custom_name: batFilenameInput.value.trim() || "start_custom_bot.bat",
          save_to_disk: false,
        }),
      });
      const data = await res.json();
      lastBatContent = data.bat_content;
      batCodePreview.textContent = data.bat_content;
    } catch (err) {
      batCodePreview.textContent = `Hata: ${err.message}`;
    }
  });

  btnCloseBatModal.addEventListener("click", () => (batModal.style.display = "none"));

  btnSaveBatToDisk.addEventListener("click", async () => {
    const filename = batFilenameInput.value.trim() || "start_custom_bot.bat";
    try {
      btnSaveBatToDisk.disabled = true;
      btnSaveBatToDisk.textContent = "Kaydediliyor...";
      const res = await fetch("/api/generate-bat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          custom_name: filename,
          save_to_disk: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Kaydedilemedi");
      showToast(`'${filename}' dosyası v1.2 klasörüne başarıyla kaydedildi!`, "success");
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnSaveBatToDisk.disabled = false;
      btnSaveBatToDisk.textContent = "💾 v1.2 Klasörüne Kaydet";
    }
  });

  btnDownloadBatFile.addEventListener("click", () => {
    const filename = batFilenameInput.value.trim() || "start_custom_bot.bat";
    if (!lastBatContent) return;
    const blob = new Blob([lastBatContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast(`'${filename}' indirildi!`, "success");
  });

  // Başlangıç Yüklemesi
  loadConfig();

  // URL Hash ile doğrudan modal açma desteği (#bat, #test)
  if (window.location.hash === "#bat") {
    setTimeout(() => {
      document.getElementById("btnGenerateBat").click();
    }, 1200);
  } else if (window.location.hash === "#test") {
    setTimeout(() => {
      document.getElementById("btnSelfTest").click();
    }, 1200);
  }
});

