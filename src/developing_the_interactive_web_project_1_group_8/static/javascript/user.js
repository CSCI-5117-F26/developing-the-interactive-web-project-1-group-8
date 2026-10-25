const followButton = document.getElementById("follow-button");
const blockButton = document.getElementById("block-button");
if (followButton) {
  followButton.addEventListener("click", function () {
    const username = this.dataset.username;
    const action = this.dataset.action; // "follow" or "unfollow"

    fetch(`/api/user/${encodeURIComponent(username)}/${action}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": this.dataset.csrfToken,
      },
    })
      .then(async (response) => {
        if (response.ok) {
          // Update the button text and action
          if (action === "follow") {
            this.innerHTML =
              'Unfollow <i class="fa fa-user-times" aria-hidden="true"></i>';
            this.dataset.action = "unfollow";
          } else {
            this.innerHTML =
              'Follow <i class="fa fa-user-plus" aria-hidden="true"></i>';
            this.dataset.action = "follow";
          }
        } else {
          if (
            response.headers.get("Content-Type")?.includes("application/json")
          ) {
            const data = await response.json();
            showProfileNotice(data.error);
          } else {
            showProfileNotice(
              "This action could not be completed. Refresh the page and try again.",
            );
          }
        }
      })
      .catch(() => {
        showProfileNotice(
          "This action could not be completed. Please try again.",
        );
      });
  });
}

if (blockButton) {
  blockButton.addEventListener("click", function () {
    const username = this.dataset.username;
    const action = this.dataset.action; // "block" or "unblock"

    fetch(`/api/user/${encodeURIComponent(username)}/${action}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": this.dataset.csrfToken,
      },
    })
      .then(async (response) => {
        if (response.ok) {
          window.location.reload(); // Reload the page to reflect the block action

          // // Update the button text and action
          // if ( action === "block" ) {
          //   this.innerHTML = "Unblock <i class=\"fa fa-unlock\" aria-hidden=\"true\"></i>";
          //   this.dataset.action = "unblock";
          // } else {
          //   this.innerHTML = "Block <i class=\"fa fa-ban\" aria-hidden=\"true\"></i>";
          //   this.dataset.action = "block";

          // }
        } else {
          if (
            response.headers.get("Content-Type")?.includes("application/json")
          ) {
            const data = await response.json();
            showProfileNotice(data.error);
          } else {
            showProfileNotice(
              "This action could not be completed. Refresh the page and try again.",
            );
          }
        }
      })
      .catch(() => {
        showProfileNotice(
          "This action could not be completed. Please try again.",
        );
      });
  });
}
