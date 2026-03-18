(function () {
    const PREVIEW_DATA = {
        username: "",
        hasSavedPlan: false,
        goalName: "",
        goalAmount: "",
        currentBalance: "",
        monthlyContribution: "",
        targetDate: "",
        note: "",
        remainingAmount: 0,
        progressPercentage: 0,
        visualProgressPercentage: 0,
        requiredMonthlyAmount: null,
        statusLabel: "Gaida ievadi",
        statusTone: "calm",
        forecastText: "Ievadi savu mērķi un summas, lai redzētu progresu.",
        timelineText: "Kad pievienosi ikmēneša iemaksu un datumu, te redzēsi tempu.",
        nextMilestoneText: "Pēc plāna saglabāšanas te parādīsies nākamais progresa posms.",
        daysUntilTarget: null,
        milestones: [
            { label: "25%", reached: false },
            { label: "50%", reached: false },
            { label: "75%", reached: false },
            { label: "100%", reached: false },
        ],
    };

    const RING_CIRCUMFERENCE = 339.292;

    function formatCurrency(value) {
        const amount = Number(value || 0);
        return `${amount.toLocaleString("lv-LV", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })} €`;
    }

    function formatPercent(value) {
        const amount = Number(value || 0);
        return `${amount.toFixed(1)}%`;
    }

    function formatDate(value) {
        if (!value) {
            return "Nav mērķa datuma";
        }

        const date = new Date(`${value}T00:00:00`);
        if (Number.isNaN(date.getTime())) {
            return value;
        }

        return date.toLocaleDateString("lv-LV", {
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

    function renderSummaryValues(data, waitingForInput) {
        if (waitingForInput) {
            setText("remainingBadge", "Gaida mērķi");
            setText("currentBalanceValue", "Tavs atlikums");
            setText("goalAmountValue", "Tava gala summa");
            setText("remainingValue", "Atlikums parādīsies te");
            setText("monthlyPlanValue", "Tava ikmēneša iemaksa");
            setText("targetDateValue", "Tavs mērķa datums");
            setText("requiredPaceValue", "Temps parādīsies te");
            return;
        }

        setText("remainingBadge", `${formatCurrency(data.remainingAmount)} atlicis`);
        setText("currentBalanceValue", formatCurrency(data.currentBalance));
        setText("goalAmountValue", formatCurrency(data.goalAmount));
        setText("remainingValue", formatCurrency(data.remainingAmount));
        setText("monthlyPlanValue", formatCurrency(data.monthlyContribution));
        setText("targetDateValue", formatDate(data.targetDate));
        setText(
            "requiredPaceValue",
            data.requiredMonthlyAmount == null ? "Brīvs" : formatCurrency(data.requiredMonthlyAmount)
        );
    }

    function renderDashboard(data, mode) {
        const previewMode = mode !== "live";
        const waitingForInput = !data.hasSavedPlan;

        setText("sessionBadge", previewMode ? "Veidnes skats" : `Ielogojies kā ${data.username}`);
        setText("modeBadge", waitingForInput ? "Gaida tavu ievadi" : "Rāda tavus datus");
        setText("heroTitle", data.goalName || "Tavs mērķa nosaukums");
        setText(
            "heroCopy",
            waitingForInput
                ? "Sāc ar mērķa nosaukumu un gala summu. Kad ievadīsi savus datus, te parādīsies tavs progress."
                : "Seko vienam skaidram mērķim, ātri to atjaunini un turi svarīgos ciparus acu priekšā."
        );

        setText("progressRingLabel", formatPercent(data.progressPercentage));
        setText("progressStatus", data.statusLabel || "Var sākt");
        updateRing(data.visualProgressPercentage);

        setValue("goalNameInput", data.goalName || "");
        setValue("goalAmountInput", data.goalAmount || "");
        setValue("currentBalanceInput", data.currentBalance || "");
        setValue("monthlyContributionInput", data.monthlyContribution || "");
        setValue("targetDateInput", data.targetDate || "");
        setValue("noteInput", data.note || "");

        renderSummaryValues(data, waitingForInput);
        setText("forecastText", data.forecastText || "Pievieno ikmēneša iemaksu, lai redzētu aptuveno finiša laiku.");
        setText("timelineText", data.timelineText || "Uzliec mērķa datumu, lai redzētu, vai tavs temps ir pietiekams.");
        setText("nextMilestoneText", data.nextMilestoneText || "Tavs nākamais progresa posms parādīsies te.");

        const progressBar = document.getElementById("progressBarFill");
        if (progressBar) {
            progressBar.style.width = `${Math.max(0, Math.min(Number(data.visualProgressPercentage || 0), 100))}%`;
        }

        const focusLine = data.daysUntilTarget == null
            ? "Mērķa datums vēl nav uzlikts. Tas dod brīvību, bet neļauj pārbaudīt tempu."
            : `Līdz mērķa datumam palikušas ${data.daysUntilTarget} dienas.`;
        setText("focusLine", focusLine);

        const noteCard = document.getElementById("noteCard");
        if (noteCard) {
            noteCard.textContent = data.note || "Pievieno īsu piezīmi, ja gribi sev atgādināt, kāpēc šis mērķis ir svarīgs.";
            noteCard.classList.toggle("note-card-empty", !data.note);
        }

        updateMilestones(Array.isArray(data.milestones) ? data.milestones : []);
        updateQuickAddState(previewMode || !data.hasSavedPlan);
    }

    async function loadDashboardData() {
        if (window.location.protocol === "file:") {
            renderDashboard(PREVIEW_DATA, "preview");
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
                throw new Error(`Paneļa datu pieprasījums neizdevās ar statusu ${response.status}`);
            }

            const data = await response.json();
            renderDashboard(data, "live");
        } catch (_error) {
            renderDashboard(PREVIEW_DATA, "preview");
        }
    }

    document.addEventListener("DOMContentLoaded", loadDashboardData);
})();
