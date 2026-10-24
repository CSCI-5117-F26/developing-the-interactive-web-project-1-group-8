document.querySelectorAll("[data-friend-link]").forEach(function (button) {
  button.addEventListener("click", async function () {
    const link = this.dataset.friendLink;
    try {
      await navigator.clipboard.writeText(link);
      showProfileNotice("Friend link copied.");
    } catch {
      showProfileNotice(`Copy this friend link: ${link}`);
    }
    document
      .getElementById("profile-action-notice")
      .scrollIntoView({ block: "nearest" });
  });
});
