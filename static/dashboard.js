(function () {
    const PREVIEW_DATA = {
        lietotajvards: "",
        irSaglabatsPlans: false,
        merkaNosaukums: "",
        merkaSumma: "",
        pasreizejaisAtlikums: "",
        ikmenesaIemaksa: "",
        merkaDatums: "",
        piezime: "",
        atlikusiSumma: 0,
        progresaProcenti: 0,
        redzamieProgresaProcenti: 0,
        nepieciesamaIkmenesaIemaksa: null,
        statusaUzraksts: "Gaida ievadi",
        statusaTonis: "mierigs",
        prognozesTeksts: "Ievadi savu mērķi un summas, lai redzētu progresu.",
        terminaTeksts: "Kad pievienosi ikmēneša iemaksu un datumu, te redzēsi tempu.",
        nakamaPosmaTeksts: "Pēc plāna saglabāšanas te parādīsies nākamais progresa posms.",
        dienasLidzMerkim: null,
        progresaPosmi: [
            { etikete: "25%", sasniegts: false },
            { etikete: "50%", sasniegts: false },
            { etikete: "75%", sasniegts: false },
            { etikete: "100%", sasniegts: false },
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
            const match = milestones.find((item) => Number.parseInt(item.etikete, 10) === value);
            element.classList.toggle("milestone-hit", Boolean(match && match.sasniegts));
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

        setText("remainingBadge", `${formatCurrency(data.atlikusiSumma)} atlicis`);
        setText("currentBalanceValue", formatCurrency(data.pasreizejaisAtlikums));
        setText("goalAmountValue", formatCurrency(data.merkaSumma));
        setText("remainingValue", formatCurrency(data.atlikusiSumma));
        setText("monthlyPlanValue", formatCurrency(data.ikmenesaIemaksa));
        setText("targetDateValue", formatDate(data.merkaDatums));
        setText(
            "requiredPaceValue",
            data.nepieciesamaIkmenesaIemaksa == null ? "Brīvs" : formatCurrency(data.nepieciesamaIkmenesaIemaksa)
        );
    }

    function renderDashboard(data, mode) {
        const previewMode = mode !== "live";
        const waitingForInput = !data.irSaglabatsPlans;

        setText("sessionBadge", previewMode ? "Veidnes skats" : `Ielogojies kā ${data.lietotajvards}`);
        setText("modeBadge", waitingForInput ? "Gaida tavu ievadi" : "Rāda tavus datus");
        setText("heroTitle", data.merkaNosaukums || "Tavs mērķa nosaukums");
        setText(
            "heroCopy",
            waitingForInput
                ? "Sāc ar mērķa nosaukumu un gala summu. Kad ievadīsi savus datus, te parādīsies tavs progress."
                : "Seko vienam skaidram mērķim, ātri to atjaunini un turi svarīgos ciparus acu priekšā."
        );

        setText("progressRingLabel", formatPercent(data.progresaProcenti));
        setText("progressStatus", data.statusaUzraksts || "Var sākt");
        updateRing(data.redzamieProgresaProcenti);

        setValue("goalNameInput", data.merkaNosaukums || "");
        setValue("goalAmountInput", data.merkaSumma || "");
        setValue("currentBalanceInput", data.pasreizejaisAtlikums || "");
        setValue("monthlyContributionInput", data.ikmenesaIemaksa || "");
        setValue("targetDateInput", data.merkaDatums || "");
        setValue("noteInput", data.piezime || "");

        renderSummaryValues(data, waitingForInput);
        setText("forecastText", data.prognozesTeksts || "Pievieno ikmēneša iemaksu, lai redzētu aptuveno finiša laiku.");
        setText("timelineText", data.terminaTeksts || "Uzliec mērķa datumu, lai redzētu, vai tavs temps ir pietiekams.");
        setText("nextMilestoneText", data.nakamaPosmaTeksts || "Tavs nākamais progresa posms parādīsies te.");

        const progressBar = document.getElementById("progressBarFill");
        if (progressBar) {
            progressBar.style.width = `${Math.max(0, Math.min(Number(data.redzamieProgresaProcenti || 0), 100))}%`;
        }

        const focusLine = data.dienasLidzMerkim == null
            ? "Mērķa datums vēl nav uzlikts. Tas dod brīvību, bet neļauj pārbaudīt tempu."
            : `Līdz mērķa datumam palikušas ${data.dienasLidzMerkim} dienas.`;
        setText("focusLine", focusLine);

        const noteCard = document.getElementById("noteCard");
        if (noteCard) {
            noteCard.textContent = data.piezime || "Pievieno īsu piezīmi, ja gribi sev atgādināt, kāpēc šis mērķis ir svarīgs.";
            noteCard.classList.toggle("note-card-empty", !data.piezime);
        }

        updateMilestones(Array.isArray(data.progresaPosmi) ? data.progresaPosmi : []);
        updateQuickAddState(previewMode || !data.irSaglabatsPlans);
    }

    async function loadDashboardData() {
        if (window.location.protocol === "file:") {
            renderDashboard(PREVIEW_DATA, "preview");
            return;
        }

        try {
            const response = await fetch("/api/panela-dati", {
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
