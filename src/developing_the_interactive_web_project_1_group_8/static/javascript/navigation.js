// https://developer.mozilla.org/en-US/docs/Web/API/History/back
// https://developer.mozilla.org/en-US/docs/Web/API/Document/referrer
const referrer = document.referrer && new URL(document.referrer);

if (history.length > 1 && referrer?.origin === location.origin) {
  document.querySelectorAll("[data-back-link]").forEach((link) => {
    link.querySelector("[data-back-label]").textContent = "Back";

    link.addEventListener("click", (event) => {
      if (
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      )
        return;

      event.preventDefault();
      history.back();
    });
  });
}
