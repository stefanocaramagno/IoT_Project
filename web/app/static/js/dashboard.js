/**
 * File: dashboard.js
 *
 * Obiettivo
 * ---------
 * Gestire il comportamento client-side della pagina "Dashboard" e inizializzare i grafici Chart.js
 * a partire da dataset già preparati lato backend e inseriti nel DOM tramite attributi `data-*`.
 * In particolare:
 * - invio automatico del form al cambio finestra temporale (`#window-select`);
 * - parsing difensivo dei dataset JSON presenti su ciascun canvas (`data-chart`);
 * - creazione dei grafici (line/bar/doughnut) solo quando canvas e dati sono disponibili.
 *
 * Ruolo nel sistema
 * -----------------
 * Questo script rappresenta il layer di visualizzazione dinamica della Dashboard:
 * - non calcola KPI, non aggrega dati e non interroga il database;
 * - non effettua chiamate di rete;
 * - trasforma esclusivamente dataset “server-rendered” (JSON nel DOM) in grafici interattivi Chart.js.
 * In tal modo preserva la separazione tra:
 * - elaborazione/aggregazione (server-side);
 * - rendering e interazione UI (client-side).
 *
 * Contesto di utilizzo
 * --------------------
 * La pagina Dashboard deve includere:
 * - una select con id `window-select` all’interno di un form (per filtrare `window_minutes`);
 * - uno o più canvas con id noti (es. `events-over-time-chart`, `events-by-district-chart`, ecc.);
 * - per ciascun canvas: attributo `data-chart='{"labels":[...], ...}'` contenente JSON valido;
 * - Chart.js caricato globalmente e disponibile come `window.Chart`.
 *
 * Note di implementazione
 * -----------------------
 * - Fail-safe: se Chart.js non è presente, se un canvas manca o se il JSON non è valido,
 *   la relativa inizializzazione viene saltata senza interrompere l’esecuzione.
 * - Ogni grafico è inizializzato in una IIFE dedicata per isolamento dello scope e modularità.
 * - Il parsing dei dataset avviene tramite `getChartData`, con gestione esplicita degli errori.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Auto-submit del form associato alla selezione della finestra temporale.
  const windowSelect = document.getElementById("window-select");
  if (windowSelect && windowSelect.form) {
    windowSelect.addEventListener("change", () => {
      windowSelect.form.submit();
    });
  }

  /**
   * Estrae e parse-a i dati JSON associati a un canvas tramite `data-chart`.
   * Ritorna `null` se:
   * - il canvas non esiste,
   * - l’attributo non è presente,
   * - la stringa non è JSON valido.
   */
  function getChartData(canvas) {
    if (!canvas) return null;
    const rawData = canvas.dataset.chart;
    if (!rawData) return null;
    try {
      return JSON.parse(rawData);
    } catch (err) {
      console.error("Invalid chart data:", err);
      return null;
    }
  }

  /**
   * Grafico: "Events over time"
   * Tipo: line chart
   * Dataset: serie low/medium/high su asse temporale (labels).
   */
  (function initEventsOverTimeChart() {
    const canvas = document.getElementById("events-over-time-chart");
    if (!canvas || !window.Chart) return;

    const parsed = getChartData(canvas);
    if (!parsed || !Array.isArray(parsed.labels)) return;

    const labels = parsed.labels;
    const series = parsed.series || {};

    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Low",
            data: series.low || [],
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 0,
            borderColor: "#22c55e",
            backgroundColor: "rgba(34,197,94,0.15)",
            fill: true,
          },
          {
            label: "Medium",
            data: series.medium || [],
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 0,
            borderColor: "#fbbf24",
            backgroundColor: "rgba(251,191,36,0.15)",
            fill: true,
          },
          {
            label: "High",
            data: series.high || [],
            borderWidth: 2,
            tension: 0.3,
            pointRadius: 0,
            borderColor: "#fb7185",
            backgroundColor: "rgba(251,113,133,0.15)",
            fill: true,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        scales: {
          x: {
            grid: {
              display: false,
            },
          },
          y: {
            beginAtZero: true,
            ticks: {
              precision: 0,
            },
            grid: {
              color: "rgba(148,163,184,0.25)",
            },
          },
        },
        plugins: {
          legend: {
            labels: {
              usePointStyle: true,
              boxWidth: 8,
            },
          },
        },
      },
    });
  })();

  /**
   * Grafico: "Events by district & severity"
   * Tipo: stacked bar chart
   * Dataset: serie low/medium/high per distretto (labels).
   */
  (function initEventsByDistrictChart() {
    const canvas = document.getElementById("events-by-district-chart");
    if (!canvas || !window.Chart) return;

    const parsed = getChartData(canvas);
    if (!parsed || !Array.isArray(parsed.labels)) return;

    const labels = parsed.labels;
    const series = parsed.series || {};

    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Low",
            data: series.low || [],
            backgroundColor: "rgba(34,197,94,0.7)",
            stack: "severity",
          },
          {
            label: "Medium",
            data: series.medium || [],
            backgroundColor: "rgba(251,191,36,0.8)",
            stack: "severity",
          },
          {
            label: "High",
            data: series.high || [],
            backgroundColor: "rgba(251,113,133,0.9)",
            stack: "severity",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        scales: {
          x: {
            stacked: true,
            ticks: {
              maxRotation: 40,
              minRotation: 0,
              autoSkip: false,
            },
            grid: {
              display: false,
            },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: {
              precision: 0,
            },
            grid: {
              color: "rgba(148,163,184,0.25)",
            },
          },
        },
        plugins: {
          legend: {
            labels: {
              usePointStyle: true,
              boxWidth: 8,
            },
          },
        },
      },
    });
  })();

  /**
   * Grafico: "Critical events → escalations → actions"
   * Tipo: bar chart
   * Dataset: `labels` e array `values`.
   * Scopo: rappresentare una pipeline quantitativa dei passaggi critici.
   */
  (function initCriticalPipelineChart() {
    const canvas = document.getElementById("critical-pipeline-chart");
    if (!canvas || !window.Chart) return;

    const parsed = getChartData(canvas);
    if (!parsed || !Array.isArray(parsed.labels)) return;

    const labels = parsed.labels;
    const values = parsed.values || [];

    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Count",
            data: values,
            backgroundColor: [
              "rgba(251,113,133,0.9)",
              "rgba(251,191,36,0.9)",
              "rgba(56,189,248,0.9)",
            ],
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            grid: {
              display: false,
            },
          },
          y: {
            beginAtZero: true,
            ticks: {
              precision: 0,
            },
            grid: {
              color: "rgba(148,163,184,0.25)",
            },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
        },
      },
    });
  })();

  /**
   * Grafico: "Event severity distribution"
   * Tipo: doughnut chart
   * Dataset: `labels` e array `values`.
   * Scopo: mostrare la composizione percentuale low/medium/high.
   */
  (function initEventSeverityDistributionChart() {
    const canvas = document.getElementById("event-severity-chart");
    if (!canvas || !window.Chart) return;

    const parsed = getChartData(canvas);
    if (!parsed || !Array.isArray(parsed.labels)) return;

    const labels = parsed.labels;
    const values = parsed.values || [];

    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [
          {
            data: values,
            backgroundColor: [
              "rgba(34,197,94,0.9)",
              "rgba(251,191,36,0.9)",
              "rgba(251,113,133,0.9)",
            ],
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "60%",
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              usePointStyle: true,
              boxWidth: 8,
            },
          },
        },
      },
    });
  })();

  /**
   * Grafico: "Actions by type"
   * Tipo: horizontal bar chart (indexAxis = "y")
   * Dataset: `labels` e array `values`.
   * Scopo: distribuire le azioni di coordinamento per tipologia.
   */
  (function initActionsByTypeChart() {
    const canvas = document.getElementById("actions-by-type-chart");
    if (!canvas || !window.Chart) return;

    const parsed = getChartData(canvas);
    if (!parsed || !Array.isArray(parsed.labels)) return;

    const labels = parsed.labels;
    const values = parsed.values || [];

    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Actions",
            data: values,
            backgroundColor: "rgba(56,189,248,0.9)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        scales: {
          x: {
            beginAtZero: true,
            ticks: {
              precision: 0,
            },
            grid: {
              color: "rgba(148,163,184,0.25)",
            },
          },
          y: {
            grid: {
              display: false,
            },
          },
        },
        plugins: {
          legend: {
            display: false,
          },
        },
      },
    });
  })();

  /**
   * Grafico: "Events by sensor type & severity"
   * Tipo: stacked bar chart
   * Dataset: serie low/medium/high per tipologia sensore (labels).
   */
  (function initEventsBySensorTypeChart() {
    const canvas = document.getElementById("events-by-sensor-type-chart");
    if (!canvas || !window.Chart) return;

    const parsed = getChartData(canvas);
    if (!parsed || !Array.isArray(parsed.labels)) return;

    const labels = parsed.labels;
    const series = parsed.series || {};

    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Low",
            data: series.low || [],
            backgroundColor: "rgba(34,197,94,0.7)",
            stack: "severity",
          },
          {
            label: "Medium",
            data: series.medium || [],
            backgroundColor: "rgba(251,191,36,0.8)",
            stack: "severity",
          },
          {
            label: "High",
            data: series.high || [],
            backgroundColor: "rgba(251,113,133,0.9)",
            stack: "severity",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false,
        },
        scales: {
          x: {
            stacked: true,
            ticks: {
              maxRotation: 40,
              minRotation: 0,
              autoSkip: false,
            },
            grid: {
              display: false,
            },
          },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: {
              precision: 0,
            },
            grid: {
              color: "rgba(148,163,184,0.25)",
            },
          },
        },
        plugins: {
          legend: {
            labels: {
              usePointStyle: true,
              boxWidth: 8,
            },
          },
        },
      },
    });
  })();

  /**
   * Grafico: "Sensor type distribution"
   * Tipo: doughnut chart
   * Dataset: `labels` e array `values`.
   * Nota: genera dinamicamente una palette ciclica in base al numero di label.
   */
  (function initSensorTypeDistributionChart() {
    const canvas = document.getElementById("sensor-type-distribution-chart");
    if (!canvas || !window.Chart) return;

    const parsed = getChartData(canvas);
    if (!parsed || !Array.isArray(parsed.labels)) return;

    const labels = parsed.labels;
    const values = parsed.values || [];

    const baseColors = [
      "rgba(56,189,248,0.9)",
      "rgba(34,197,94,0.9)",
      "rgba(251,191,36,0.9)",
      "rgba(251,113,133,0.9)",
      "rgba(129,140,248,0.9)",
      "rgba(244,114,182,0.9)",
      "rgba(45,212,191,0.9)",
    ];
    const backgroundColors = labels.map(
      (_, idx) => baseColors[idx % baseColors.length]
    );

    const ctx = canvas.getContext("2d");
    new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [
          {
            data: values,
            backgroundColor: backgroundColors,
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "60%",
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              usePointStyle: true,
              boxWidth: 8,
            },
          },
        },
      },
    });
  })();
});
