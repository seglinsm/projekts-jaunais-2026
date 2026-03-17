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
        const container = document.getElementById("noticeBanner");
        if (!container) {
            return;
        }

        const params = getParams();
        const notice = params.get("notice");
        if (!notice) {
            return;
        }

        const level = params.get("notice_level") === "error" ? "error" : "success";
        container.hidden = false;
        container.innerHTML = `<div class="flash flash-${level}">${escapeHtml(notice)}</div>`;
    }

    function prefillUsername() {
        const usernameInput = document.getElementById("usernameInput");
        if (!usernameInput) {
            return;
        }

        const username = getParams().get("username");
        if (username) {
            usernameInput.value = username;
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        renderNotice();
        prefillUsername();
    });
})();
