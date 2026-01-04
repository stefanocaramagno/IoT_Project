document.addEventListener("DOMContentLoaded", () => {
  const windowSelect = document.getElementById("window-select");
  if (windowSelect && windowSelect.form) {
    windowSelect.addEventListener("change", () => {
      windowSelect.form.submit();
    });
  }

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
