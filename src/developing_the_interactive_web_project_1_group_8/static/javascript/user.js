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
      .then((data) => {
        if (data.ok) {
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
          console.error("Error:", data.error);
        }
      })
      .catch((error) => {
        console.error("Error:", error);
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
      .then((data) => {
        if (data.ok) {
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
          console.error("Error:", data.error);
        }
      })
      .catch((error) => {
        console.error("Error:", error);
      });
  });
}
