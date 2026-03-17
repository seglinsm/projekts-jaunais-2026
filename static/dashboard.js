(function () {
    const DEMO_DATA = {
        username: "Preview user",
        hasSavedPlan: true,
        goalName: "Trip to Italy",
        goalAmount: 2500,
        currentBalance: 925,
        monthlyContribution: 180,
        targetDate: "2026-09-30",
        note: "Flights, hotel, and food budget.",
        remainingAmount: 1575,
        progressPercentage: 37.0,
        visualProgressPercentage: 37.0,
        requiredMonthlyAmount: 224.5,
        statusLabel: "Needs a boost",
        statusTone: "warning",
        forecastText: "At your current pace, you need about 9 more months.",
        timelineText: "You need roughly EUR 224.50 per month to hit the target date.",
        nextMilestoneText: "50% is your next milestone.",
        daysUntilTarget: 197,
        milestones: [
            { label: "25%", reached: true },
            { label: "50%", reached: false },
            { label: "75%", reached: false },
            { label: "100%", reached: false },
        ],
    };

    const RING_CIRCUMFERENCE = 339.292;

    function formatCurrency(value) {
        const amount = Number(value || 0);
        return `EUR ${amount.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;
    }

    function formatPercent(value) {
        const amount = Number(value || 0);
        return `${amount.toFixed(1)}%`;
    }

    function formatDate(value) {
        if (!value) {
            return "No target date";
        }

        const date = new Date(`${value}T00:00:00`);
        if (Number.isNaN(date.getTime())) {
            return value;
        }

        return date.toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
        });
    }

    function setText(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    function setValue(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.value = value ?? "";
        }
    }

    function updateRing(progress) {
        const ring = document.getElementById("progressRingFill");
        if (!ring) {
            return;
        }

        const safeProgress = Math.max(0, Math.min(Number(progress || 0), 100));
        const offset = RING_CIRCUMFERENCE - (RING_CIRCUMFERENCE * safeProgress) / 100;
        ring.style.strokeDashoffset = `${offset}`;
    }

    function updateMilestones(milestones) {
        document.querySelectorAll("[data-milestone]").forEach((element) => {
            const value = Number(element.dataset.milestone);
            const match = milestones.find((item) => Number.parseInt(item.label, 10) === value);
            element.classList.toggle("milestone-hit", Boolean(match && match.reached));
        });
    }

    function updateQuickAddState(disabled) {
        document.querySelectorAll(".quick-add-button").forEach((button) => {
            button.disabled = disabled;
        });
    }

    function renderDashboard(data, mode) {
        const previewMode = mode !== "live";

        setText("sessionBadge", previewMode ? "Preview mode" : `Signed in as ${data.username}`);
        setText("modeBadge", previewMode ? "Preview demo data" : "Live project data");
        setText("heroTitle", data.goalName || "Build your first savings goal");
        setText(
            "heroCopy",
            previewMode
                ? "This preview keeps the layout visible even outside Flask. Run the server for real login, saved data, and form actions."
                : "Track one clear target, update it quickly, and keep the important numbers visible."
        );

        setText("progressRingLabel", formatPercent(data.progressPercentage));
        setText("progressStatus", data.statusLabel || "Ready to start");
        updateRing(data.visualProgressPercentage);

        setValue("goalNameInput", data.goalName || "");
        setValue("goalAmountInput", data.goalAmount || "");
        setValue("currentBalanceInput", data.currentBalance || "");
        setValue("monthlyContributionInput", data.monthlyContribution || "");
        setValue("targetDateInput", data.targetDate || "");
        setValue("noteInput", data.note || "");

        setText("remainingBadge", `${formatCurrency(data.remainingAmount)} left`);
        setText("currentBalanceValue", formatCurrency(data.currentBalance));
        setText("goalAmountValue", formatCurrency(data.goalAmount));
        setText("remainingValue", formatCurrency(data.remainingAmount));
        setText("monthlyPlanValue", formatCurrency(data.monthlyContribution));
        setText("targetDateValue", formatDate(data.targetDate));
        setText(
            "requiredPaceValue",
            data.requiredMonthlyAmount == null ? "Flexible" : formatCurrency(data.requiredMonthlyAmount)
        );
        setText("forecastText", data.forecastText || "Add a monthly contribution to unlock a finish estimate.");
        setText("timelineText", data.timelineText || "Set a target date to check whether your pace is enough.");
        setText("nextMilestoneText", data.nextMilestoneText || "Your next milestone will appear here.");

        const progressBar = document.getElementById("progressBarFill");
        if (progressBar) {
            progressBar.style.width = `${Math.max(0, Math.min(Number(data.visualProgressPercentage || 0), 100))}%`;
        }

        const focusLine = data.daysUntilTarget == null
            ? "No deadline set yet. That keeps the plan flexible, but it also removes the pace check."
            : `${data.daysUntilTarget} days remain until your target date.`;
        setText("focusLine", focusLine);

        const noteCard = document.getElementById("noteCard");
        if (noteCard) {
            noteCard.textContent = data.note || "Add a short note if you want a reminder of why this goal matters.";
            noteCard.classList.toggle("note-card-empty", !data.note);
        }

        updateMilestones(Array.isArray(data.milestones) ? data.milestones : []);
        updateQuickAddState(previewMode || !data.hasSavedPlan);
    }

    async function loadDashboardData() {
        if (window.location.protocol === "file:") {
            renderDashboard(DEMO_DATA, "preview");
            return;
        }

        try {
            const response = await fetch("/api/dashboard-data", {
                credentials: "same-origin",
                headers: {
                    Accept: "application/json",
                },
            });

            if (!response.ok) {
                throw new Error(`Dashboard data request failed with ${response.status}`);
            }

            const data = await response.json();
            renderDashboard(data, "live");
        } catch (_error) {
            renderDashboard(DEMO_DATA, "preview");
        }
    }

    document.addEventListener("DOMContentLoaded", loadDashboardData);
})();
