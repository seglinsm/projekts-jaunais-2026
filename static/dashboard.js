(function () {
    const DEMO_DATA = {
        username: "Demo lietotājs",
        hasSavedPlan: true,
        goalName: "Ceļojums uz Itāliju",
        goalAmount: 2500,
        currentBalance: 925,
        monthlyContribution: 180,
        targetDate: "2026-09-30",
        note: "Lidojumiem, viesnīcai un ēdienam.",
        remainingAmount: 1575,
        progressPercentage: 37.0,
        visualProgressPercentage: 37.0,
        requiredMonthlyAmount: 224.5,
        statusLabel: "Jāpiespiež vairāk",
        statusTone: "warning",
        forecastText: "Ar pašreizējo tempu tev vajadzēs vēl apmēram 9 mēnešus.",
        timelineText: "Lai paspētu līdz datumam, tev vajag apmēram 224,50 € mēnesī.",
        nextMilestoneText: "Nākamais posms ir 50%.",
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

    function renderDashboard(data, mode) {
        const previewMode = mode !== "live";

        setText("sessionBadge", previewMode ? "Priekšskatījuma režīms" : `Ielogojies kā ${data.username}`);
        setText("modeBadge", previewMode ? "Rāda demo datus" : "Rāda tavus datus");
        setText("heroTitle", data.goalName || "Izveido savu pirmo mērķi");
        setText(
            "heroCopy",
            previewMode
                ? "Šis priekšskatījums rāda lapas izskatu arī ārpus Flask. Palaid serveri, ja gribi īstu ieeju, saglabātus datus un strādājošas formas."
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
                throw new Error(`Paneļa datu pieprasījums neizdevās ar statusu ${response.status}`);
            }

            const data = await response.json();
            renderDashboard(data, "live");
        } catch (_error) {
            renderDashboard(DEMO_DATA, "preview");
        }
    }

    document.addEventListener("DOMContentLoaded", loadDashboardData);
})();
