(function () {
    const demoGoals = [
        {
            id: 101,
            title: "Ceļojums uz Itāliju",
            targetAmount: 500,
            totalSaved: 180,
            remainingAmount: 320,
            progressPercentage: 36,
            visualProgressPercentage: 36,
            monthlySavingRate: 70,
            recurringContributionAmount: 50,
            targetDate: "2026-08-15",
            estimateText: "Ar pašreizējo tempu šo mērķi varētu sasniegt apmēram 5 mēnešu laikā.",
            recommendation: "Jūs stabili virzāties uz savu mērķi.",
        },
        {
            id: 102,
            title: "Jauns klēpjdators",
            targetAmount: 1200,
            totalSaved: 420,
            remainingAmount: 780,
            progressPercentage: 35,
            visualProgressPercentage: 35,
            monthlySavingRate: 110,
            recurringContributionAmount: 100,
            targetDate: "2026-11-30",
            estimateText: "Ar pašreizējo tempu šo mērķi varētu sasniegt apmēram 8 mēnešu laikā.",
            recommendation: "Jūs stabili virzāties uz savu mērķi.",
        },
        {
            id: 103,
            title: "Drošības fonds",
            targetAmount: 1000,
            totalSaved: 250,
            remainingAmount: 750,
            progressPercentage: 25,
            visualProgressPercentage: 25,
            monthlySavingRate: 60,
            recurringContributionAmount: 40,
            targetDate: "2026-12-31",
            estimateText: "Ar pašreizējo tempu šo mērķi varētu sasniegt apmēram 13 mēnešu laikā.",
            recommendation: "Apsveriet regulārās iemaksas palielināšanu, lai mērķi sasniegtu ātrāk.",
        },
        {
            id: 104,
            title: "Brīvdienu dzīvokļa pirmā iemaksa",
            targetAmount: 2500,
            totalSaved: 900,
            remainingAmount: 1600,
            progressPercentage: 36,
            visualProgressPercentage: 36,
            monthlySavingRate: 180,
            recurringContributionAmount: 150,
            targetDate: "2026-09-10",
            estimateText: "Ar pašreizējo tempu šo mērķi varētu sasniegt apmēram 9 mēnešu laikā.",
            recommendation: "Jūs esat priekšā plānam.",
        },
    ];

    const currencyFormatter = new Intl.NumberFormat("lv-LV", {
        style: "currency",
        currency: "EUR",
        minimumFractionDigits: 2,
    });

    const fullDateFormatter = new Intl.DateTimeFormat("lv-LV", {
        year: "numeric",
        month: "long",
        day: "numeric",
    });

    const shortMonthFormatter = new Intl.DateTimeFormat("lv-LV", {
        year: "numeric",
        month: "long",
    });

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
                throw new Error("Pieprasījums neizdevās");
            }

            const payload = await response.json();
            return { mode: "live", items: payload.items || [] };
        } catch (_error) {
            return { mode: "demo", items: demoGoals };
        }
    }

    function clampProgress(value) {
        return Math.max(0, Math.min(Number(value || 0), 100));
    }

    function setMeta(overview, mode) {
        const metricStrip = document.getElementById("metricStrip");
        const modeBadge = document.getElementById("modeBadge");
        const monthInput = document.getElementById("monthInput");
        const monthDisplay = document.getElementById("monthDisplay");
        const todayLabel = document.getElementById("todayLabel");

        metricStrip.innerHTML = [
            ["Kopējā mērķa summa", formatCurrency(overview.totalTarget)],
            ["Kopā uzkrāts", formatCurrency(overview.totalSaved)],
            ["Kopā atlicis", formatCurrency(overview.totalRemaining)],
            ["Vidējais progress", `${overview.averageProgress.toFixed(1)}%`],
        ]
            .map(
                ([label, value]) => `
                    <article class="stat-card">
                        <div class="stat-label">${label}</div>
                        <div class="stat-value">${value}</div>
                    </article>
                `
            )
            .join("");

        const currentMonth = new Date();
        monthInput.value = `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, "0")}`;
        monthDisplay.textContent = shortMonthFormatter.format(currentMonth);
        todayLabel.textContent = fullDateFormatter.format(currentMonth);

        monthInput.addEventListener("change", () => {
            if (!monthInput.value) {
                return;
            }
            const [year, month] = monthInput.value.split("-");
            monthDisplay.textContent = shortMonthFormatter.format(new Date(Number(year), Number(month) - 1, 1));
        });

        modeBadge.textContent = mode === "live" ? "Tiešsaistes API režīms" : "Demo priekšskatījuma režīms";
        modeBadge.className = `mode-box ${mode === "live" ? "mode-live" : "mode-demo"}`;
    }

    function renderSidebar(goals) {
        const sidebarGoals = document.getElementById("sidebarGoals");

        if (!goals.length) {
            sidebarGoals.innerHTML = `<div class="sidebar-goal"><div class="sidebar-goal-meta">Vēl nav pieejamu mērķu.</div></div>`;
            return;
        }

        sidebarGoals.innerHTML = goals
            .slice(0, 4)
            .map(
                (goal) => `
                    <div class="sidebar-goal">
                        <div class="sidebar-goal-top">
                            <span class="sidebar-goal-title">${goal.title}</span>
                            <span class="sidebar-goal-progress">${clampProgress(goal.progressPercentage).toFixed(0)}%</span>
                        </div>
                        <div class="mini-progress">
                            <div class="mini-progress-fill" style="width:${clampProgress(goal.visualProgressPercentage)}%"></div>
                        </div>
                        <div class="sidebar-goal-meta">${formatCurrency(goal.totalSaved)} no ${formatCurrency(goal.targetAmount)}</div>
                    </div>
                `
            )
            .join("");
    }

    function renderMainProgress(goals) {
        const goalProgressList = document.getElementById("goalProgressList");

        goalProgressList.innerHTML = goals
            .map(
                (goal) => `
                    <div class="goal-progress-card">
                        <div class="goal-progress-top">
                            <div>
                                <div class="goal-progress-title">${goal.title}</div>
                                <div class="goal-progress-meta">${goal.estimateText || "Vēl nav prognozes."}</div>
                            </div>
                            <strong>${clampProgress(goal.progressPercentage).toFixed(0)}%</strong>
                        </div>
                        <div class="track">
                            <div class="track-fill" style="width:${clampProgress(goal.visualProgressPercentage)}%"></div>
                        </div>
                        <div class="goal-progress-amounts">
                            <div>
                                <span>Mērķis</span>
                                <strong>${formatCurrency(goal.targetAmount)}</strong>
                            </div>
                            <div>
                                <span>Uzkrāts</span>
                                <strong>${formatCurrency(goal.totalSaved)}</strong>
                            </div>
                            <div>
                                <span>Atlicis</span>
                                <strong>${formatCurrency(goal.remainingAmount)}</strong>
                            </div>
                            <div>
                                <span>Regulāri</span>
                                <strong>${formatCurrency(goal.recurringContributionAmount)}/mēn.</strong>
                            </div>
                        </div>
                        <div class="progress-foot">
                            <span>${goal.recommendation || "Vēl nav ieteikuma."}</span>
                            <span>${goal.targetDate || "Nav mērķa datuma"}</span>
                        </div>
                    </div>
                `
            )
            .join("");
    }

    function renderPace(goals) {
        const paceList = document.getElementById("paceList");
        const maxRate = Math.max(...goals.map((goal) => Number(goal.monthlySavingRate || 0)), 1);

        paceList.innerHTML = goals
            .slice(0, 5)
            .map((goal) => {
                const width = (Number(goal.monthlySavingRate || 0) / maxRate) * 100;
                return `
                    <div class="compact-progress-card">
                        <div class="compact-progress-top">
                            <span>${goal.title}</span>
                            <strong>${formatCurrency(goal.monthlySavingRate)}/mēn.</strong>
                        </div>
                        <div class="track-thin">
                            <div class="track-fill-thin" style="width:${clampProgress(width)}%"></div>
                        </div>
                        <div class="compact-progress-note">Regulārais plāns: ${formatCurrency(goal.recurringContributionAmount)}/mēn.</div>
                    </div>
                `;
            })
            .join("");
    }

    function renderUpcoming(goals) {
        const upcomingList = document.getElementById("upcomingList");
        const sortedGoals = [...goals].sort((a, b) => {
            const aDate = a.targetDate || "9999-12-31";
            const bDate = b.targetDate || "9999-12-31";
            return aDate.localeCompare(bDate);
        });

        upcomingList.innerHTML = sortedGoals
            .slice(0, 5)
            .map(
                (goal) => `
                    <div class="upcoming-card">
                        <div class="upcoming-title">${goal.title}</div>
                        <div class="upcoming-date">${goal.targetDate || "Nav mērķa datuma"}</div>
                        <div class="upcoming-meta">${formatCurrency(goal.remainingAmount)} atlicis uzkrāt</div>
                    </div>
                `
            )
            .join("");
    }

    function renderRecommendations(goals) {
        const recommendationList = document.getElementById("recommendationList");

        recommendationList.innerHTML = goals
            .slice(0, 4)
            .map(
                (goal) => `
                    <div class="recommendation-card">
                        <div class="recommendation-card-title">${goal.title}</div>
                        <div class="recommendation-card-text">${goal.recommendation || "Vēl nav ieteikuma."}</div>
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
                        <td>${formatCurrency(goal.totalSaved)}</td>
                        <td>${formatCurrency(goal.remainingAmount)}</td>
                        <td class="table-progress-cell">
                            <div class="table-progress-label">
                                <span>Pabeigtība</span>
                                <span>${clampProgress(goal.progressPercentage).toFixed(0)}%</span>
                            </div>
                            <div class="track-thin">
                                <div class="track-fill-thin" style="width:${clampProgress(goal.visualProgressPercentage)}%"></div>
                            </div>
                        </td>
                    </tr>
                `
            )
            .join("");
    }

    async function handleGoalFormSubmit(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const button = document.getElementById("goalFormButton");
        const note = document.getElementById("formNote");

        if (pageMode !== "live") {
            note.textContent = "Šis fails darbojas demo priekšskatījuma režīmā. Palaidiet Flask un atveriet http://127.0.0.1:5000, lai saglabātu reālus mērķus.";
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
        button.textContent = "Saglabā...";

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
                throw new Error("Neizdevās izveidot mērķi");
            }

            form.reset();
            note.textContent = "Mērķis saglabāts. Panelis atjaunināts.";
            await loadAndRender();
        } catch (_error) {
            note.textContent = "Neizdevās izveidot mērķi no paneļa formas.";
        } finally {
            button.disabled = false;
            button.textContent = "Pievienot mērķi";
        }
    }

    async function loadAndRender() {
        const payload = await loadGoals();
        const goals = payload.items || [];
        const overview = buildOverview(goals);
        pageMode = payload.mode;

        setMeta(overview, payload.mode);
        renderSidebar(goals);
        renderMainProgress(goals);
        renderPace(goals);
        renderUpcoming(goals);
        renderRecommendations(goals);
        renderTable(goals);
    }

    function init() {
        if (window.lucide) {
            window.lucide.createIcons();
        }

        document.getElementById("goalForm").addEventListener("submit", handleGoalFormSubmit);
        loadAndRender();
    }

    document.addEventListener("DOMContentLoaded", init);
})();
