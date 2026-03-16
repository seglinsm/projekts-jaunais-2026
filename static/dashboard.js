(function () {
    const demoGoals = [
        {
            id: 101,
            title: "Trip to Italy",
            targetAmount: 500,
            totalSaved: 180,
            remainingAmount: 320,
            progressPercentage: 36,
            visualProgressPercentage: 36,
            monthlySavingRate: 70,
            recurringContributionAmount: 50,
            estimateText: "At your current pace, you may reach this goal in 5 months.",
            recommendation: "You are on a steady path toward your goal.",
        },
        {
            id: 102,
            title: "New Laptop",
            targetAmount: 1200,
            totalSaved: 420,
            remainingAmount: 780,
            progressPercentage: 35,
            visualProgressPercentage: 35,
            monthlySavingRate: 110,
            recurringContributionAmount: 100,
            estimateText: "At your current pace, you may reach this goal in 8 months.",
            recommendation: "You are on a steady path toward your goal.",
        },
        {
            id: 103,
            title: "Emergency Fund",
            targetAmount: 1000,
            totalSaved: 250,
            remainingAmount: 750,
            progressPercentage: 25,
            visualProgressPercentage: 25,
            monthlySavingRate: 60,
            recurringContributionAmount: 40,
            estimateText: "At your current pace, you may reach this goal in 13 months.",
            recommendation: "Consider increasing your regular contribution to reach your goal faster.",
        },
        {
            id: 104,
            title: "Vacation Apartment Deposit",
            targetAmount: 2500,
            totalSaved: 900,
            remainingAmount: 1600,
            progressPercentage: 36,
            visualProgressPercentage: 36,
            monthlySavingRate: 180,
            recurringContributionAmount: 150,
            estimateText: "At your current pace, you may reach this goal in 9 months.",
            recommendation: "You are ahead of schedule.",
        },
    ];

    const currencyFormatter = new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 2,
    });

    const dateFormatter = new Intl.DateTimeFormat("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
    });

    const shortMonthFormatter = new Intl.DateTimeFormat("en-US", {
        year: "numeric",
        month: "long",
    });

    const chartPalette = ["#a4e05d", "#8ad44a", "#81c8d6", "#ffc943", "#d86d6d", "#9d35ba"];
    const charts = {};
    let pageMode = "demo";

    function formatCurrency(value) {
        return currencyFormatter.format(Number(value || 0));
    }

    function buildOverview(goals) {
        const totalTarget = goals.reduce((sum, goal) => sum + Number(goal.targetAmount || 0), 0);
        const totalSaved = goals.reduce((sum, goal) => sum + Number(goal.totalSaved || 0), 0);
        const totalRemaining = goals.reduce((sum, goal) => sum + Number(goal.remainingAmount || 0), 0);
        const averageProgress = goals.length
            ? goals.reduce((sum, goal) => sum + Number(goal.progressPercentage || 0), 0) / goals.length
            : 0;

        return {
            totalTarget,
            totalSaved,
            totalRemaining,
            averageProgress,
            goalCount: goals.length,
        };
    }

    async function loadGoals() {
        if (window.location.protocol === "file:") {
            return { mode: "demo", items: demoGoals };
        }

        try {
            const response = await fetch("/api/goals", {
                headers: { Accept: "application/json" },
            });

            if (!response.ok) {
                throw new Error("Request failed");
            }

            const payload = await response.json();
            return { mode: "live", items: payload.items || [] };
        } catch (_error) {
            return { mode: "demo", items: demoGoals };
        }
    }

    function setMeta(overview, mode) {
        const metricStrip = document.getElementById("metricStrip");
        const modeBadge = document.getElementById("modeBadge");
        const monthInput = document.getElementById("monthInput");
        const monthDisplay = document.getElementById("monthDisplay");
        const todayLabel = document.getElementById("todayLabel");

        metricStrip.innerHTML = [
            ["Target", formatCurrency(overview.totalTarget)],
            ["Saved", formatCurrency(overview.totalSaved)],
            ["Remaining", formatCurrency(overview.totalRemaining)],
            ["Average progress", `${overview.averageProgress.toFixed(1)}%`],
        ]
            .map(
                ([label, value]) => `
                    <div class="metric-pill">
                        <div class="metric-label">${label}</div>
                        <div class="metric-value">${value}</div>
                    </div>
                `
            )
            .join("");

        todayLabel.textContent = dateFormatter.format(new Date());

        const currentMonth = new Date();
        monthInput.value = `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, "0")}`;
        monthDisplay.textContent = shortMonthFormatter.format(currentMonth);

        monthInput.addEventListener("change", () => {
            if (!monthInput.value) {
                return;
            }
            const [year, month] = monthInput.value.split("-");
            const pickedDate = new Date(Number(year), Number(month) - 1, 1);
            monthDisplay.textContent = shortMonthFormatter.format(pickedDate);
        });

        modeBadge.textContent = mode === "live" ? "Live data from API" : "Demo preview mode";
        modeBadge.className = `mode-badge ${mode === "live" ? "mode-live" : "mode-demo"}`;
    }

    function renderSidebar(goals) {
        const sidebarGoals = document.getElementById("sidebarGoals");

        if (!goals.length) {
            sidebarGoals.innerHTML = `<div class="sidebar-goal"><div class="sidebar-goal-meta">No goals available yet.</div></div>`;
            return;
        }

        sidebarGoals.innerHTML = goals
            .slice(0, 6)
            .map(
                (goal) => `
                    <div class="sidebar-goal">
                        <div class="sidebar-goal-top">
                            <span class="sidebar-goal-title">${goal.title}</span>
                            <span class="sidebar-goal-progress">${Number(goal.progressPercentage || 0).toFixed(0)}%</span>
                        </div>
                        <div class="mini-progress">
                            <div class="mini-progress-fill" style="width:${Math.min(Number(goal.visualProgressPercentage || 0), 100)}%"></div>
                        </div>
                        <div class="sidebar-goal-meta">${formatCurrency(goal.totalSaved)} saved of ${formatCurrency(goal.targetAmount)}</div>
                    </div>
                `
            )
            .join("");
    }

    function renderTable(goals) {
        const goalTableBody = document.getElementById("goalTableBody");

        goalTableBody.innerHTML = goals
            .map(
                (goal) => `
                    <tr>
                        <td>${goal.title}</td>
                        <td>${formatCurrency(goal.targetAmount)}</td>
                        <td>${formatCurrency(goal.totalSaved)}</td>
                        <td>${formatCurrency(goal.remainingAmount)}</td>
                        <td class="progress-cell">${Number(goal.progressPercentage || 0).toFixed(0)}%</td>
                    </tr>
                `
            )
            .join("");
    }

    function renderRecommendations(goals) {
        const recommendationList = document.getElementById("recommendationList");

        recommendationList.innerHTML = goals
            .slice(0, 5)
            .map(
                (goal) => `
                    <div class="recommendation-card">
                        <div class="recommendation-card-title">${goal.title}</div>
                        <div class="recommendation-card-text">${goal.recommendation || "No recommendation yet."}</div>
                    </div>
                `
            )
            .join("");
    }

    function destroyChart(chartId) {
        if (charts[chartId]) {
            charts[chartId].destroy();
        }
    }

    function createChart(chartId, config) {
        destroyChart(chartId);
        const context = document.getElementById(chartId);
        if (!context || !window.Chart) {
            return;
        }
        charts[chartId] = new window.Chart(context, config);
    }

    function chartDefaults() {
        if (!window.Chart) {
            return;
        }

        window.Chart.defaults.color = "#dce7ef";
        window.Chart.defaults.font.family = "Manrope";
        window.Chart.defaults.plugins.legend.labels.boxWidth = 12;
        window.Chart.defaults.plugins.legend.labels.boxHeight = 12;
    }

    function renderCharts(goals, overview) {
        chartDefaults();

        createChart("overviewChart", {
            type: "doughnut",
            data: {
                labels: ["Saved", "Remaining"],
                datasets: [
                    {
                        data: [overview.totalSaved, Math.max(overview.totalRemaining, 0)],
                        backgroundColor: ["#a4e05d", "#d8dce5"],
                        borderWidth: 0,
                    },
                ],
            },
            options: {
                cutout: "62%",
                plugins: {
                    legend: {
                        position: "bottom",
                    },
                },
            },
        });

        createChart("paceChart", {
            type: "bar",
            data: {
                labels: goals.map((goal) => goal.title),
                datasets: [
                    {
                        label: "Monthly saving pace",
                        data: goals.map((goal) => Number(goal.monthlySavingRate || 0)),
                        backgroundColor: ["#a4e05d", "#92d74d", "#81c8d6", "#ffc943", "#d86d6d"],
                        borderRadius: 10,
                    },
                ],
            },
            options: {
                scales: {
                    x: {
                        grid: { display: false },
                    },
                    y: {
                        grid: { color: "rgba(255,255,255,0.08)" },
                    },
                },
                plugins: {
                    legend: { display: false },
                },
            },
        });

        createChart("targetChart", {
            type: "doughnut",
            data: {
                labels: goals.map((goal) => goal.title),
                datasets: [
                    {
                        data: goals.map((goal) => Number(goal.targetAmount || 0)),
                        backgroundColor: chartPalette,
                        borderWidth: 0,
                    },
                ],
            },
            options: {
                cutout: "52%",
                plugins: {
                    legend: {
                        position: "bottom",
                    },
                },
            },
        });

        createChart("savedChart", {
            type: "doughnut",
            data: {
                labels: goals.map((goal) => goal.title),
                datasets: [
                    {
                        data: goals.map((goal) => Number(goal.totalSaved || 0)),
                        backgroundColor: ["#81c8d6", "#d86d6d", "#ffc943", "#a4e05d", "#9d35ba", "#d8dce5"],
                        borderWidth: 0,
                    },
                ],
            },
            options: {
                cutout: "52%",
                plugins: {
                    legend: {
                        position: "bottom",
                    },
                },
            },
        });
    }

    async function handleGoalFormSubmit(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const button = document.getElementById("goalFormButton");
        const note = document.getElementById("formNote");

        if (pageMode !== "live") {
            note.textContent = "This file is running in demo preview mode. Start Flask and open http://127.0.0.1:5000 to save real goals.";
            return;
        }

        const formData = new FormData(form);
        const payload = {
            title: formData.get("title"),
            targetAmount: formData.get("targetAmount"),
            description: formData.get("description"),
            targetDate: formData.get("targetDate"),
        };

        button.disabled = true;
        button.textContent = "Saving...";

        try {
            const response = await fetch("/api/goals", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Accept: "application/json",
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                throw new Error("Could not create goal");
            }

            form.reset();
            note.textContent = "Goal saved. Dashboard data refreshed.";
            await loadAndRender();
        } catch (_error) {
            note.textContent = "Could not create the goal from the dashboard form.";
        } finally {
            button.disabled = false;
            button.textContent = "Add Goal";
        }
    }

    async function loadAndRender() {
        const payload = await loadGoals();
        const goals = payload.items || [];
        const overview = buildOverview(goals);
        pageMode = payload.mode;

        setMeta(overview, payload.mode);
        renderSidebar(goals);
        renderTable(goals);
        renderRecommendations(goals);
        renderCharts(goals, overview);
    }

    function init() {
        if (window.lucide) {
            window.lucide.createIcons();
        }

        const goalForm = document.getElementById("goalForm");
        goalForm.addEventListener("submit", handleGoalFormSubmit);
        loadAndRender();
    }

    document.addEventListener("DOMContentLoaded", init);
})();
