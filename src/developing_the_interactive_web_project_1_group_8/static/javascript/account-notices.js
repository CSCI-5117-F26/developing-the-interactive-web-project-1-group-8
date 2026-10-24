document.querySelectorAll(".account-notice").forEach(function (notice) {
  const dismissButton = notice.querySelector(".account-notice-dismiss");
  dismissButton.hidden = false;
  dismissButton.addEventListener("click", function () {
    notice.hidden = true;
  });
});

function showProfileNotice(message) {
  const notice = document.getElementById("profile-action-notice");
  // https://developer.mozilla.org/en-US/docs/Web/API/Node/textContent
  notice.querySelector(".account-notice-message").textContent = message;
  notice.hidden = false;
}
