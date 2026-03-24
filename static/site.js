(function () {
    function getParams() {
        return new URLSearchParams(window.location.search);
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#39;");
    }

    function renderNotice() {
        const container = document.getElementById("pazinojumuJosla");
        if (!container) {
            return;
        }

        const params = getParams();
        const pazinojums = params.get("pazinojums");
        if (!pazinojums) {
            return;
        }

        const level = params.get("pazinojuma_limenis") === "error" ? "error" : "success";
        container.hidden = false;
        container.innerHTML = `<div class="flash flash-${level}">${escapeHtml(pazinojums)}</div>`;
    }

    function prefillUsername() {
        const usernameInput = document.getElementById("lietotajvardaIevade");
        if (!usernameInput) {
            return;
        }

        const username = getParams().get("lietotajvards");
        if (username) {
            usernameInput.value = username;
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        renderNotice();
        prefillUsername();
    });
})();
