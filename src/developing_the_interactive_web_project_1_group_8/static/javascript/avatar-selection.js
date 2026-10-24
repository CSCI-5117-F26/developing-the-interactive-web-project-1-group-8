// https://developer.mozilla.org/en-US/docs/Web/API/HTML_Drag_and_Drop_API/File_drag_and_drop
const avatarInput = document.getElementById("avatar");
const avatarDropZone = document.getElementById("avatar-drop-zone");
const avatarPreview = document.getElementById("avatar-preview");
const avatarNotice = document.getElementById("avatar-notice");
const avatarClear = document.getElementById("avatar-clear");
const avatarDelete = document.getElementById("avatar-delete");
const avatarDeleteButton = document.getElementById("avatar-delete-button");
const savedAvatar = avatarPreview.src;
const maxAvatarBytes = 5 * 1024 * 1024;
let previewUrl = null;

document.getElementById("avatar-drop-help").hidden = false;

function resetAvatarPreview() {
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }
  avatarPreview.src = savedAvatar;
  avatarClear.hidden = true;
  avatarDelete.value = "0";
}

function clearAvatarSelection(message) {
  avatarInput.value = "";
  resetAvatarPreview();
  avatarNotice.textContent = message;
}

function markAvatarForDeletion() {
  clearAvatarSelection("Avatar will be deleted when you click Save profile.");
  avatarDelete.value = "1";
  avatarPreview.src = avatarPreview.dataset.defaultAvatar;
  avatarClear.hidden = false;
}

if (avatarDelete.value === "1") {
  markAvatarForDeletion();
}
if (avatarDeleteButton) {
  avatarDeleteButton.addEventListener("click", markAvatarForDeletion);
}

async function displayAvatar(files) {
  if (files.length === 0 && avatarDelete.value === "1") {
    return;
  }
  resetAvatarPreview();
  if (files.length > 1) {
    clearAvatarSelection("Drop one image at a time.");
    return;
  }
  const file = files[0];
  if (!file) {
    avatarNotice.textContent = "No new avatar selected.";
    return;
  }
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    clearAvatarSelection("Choose a JPEG, PNG, or WebP image.");
    return;
  }
  if (file.size > maxAvatarBytes) {
    clearAvatarSelection("Avatar must be 5 MB or smaller.");
    return;
  }

  const imageUrl = URL.createObjectURL(file);
  previewUrl = imageUrl;
  avatarClear.hidden = false;
  avatarNotice.textContent = "Loading avatar preview...";
  const image = new Image();
  image.src = imageUrl;
  try {
    await image.decode();
  } catch {
    if (previewUrl === imageUrl) {
      clearAvatarSelection("This image could not be previewed.");
    }
    return;
  }
  if (previewUrl !== imageUrl) {
    return;
  }
  avatarPreview.src = imageUrl;
  avatarNotice.textContent = `Preview of ${file.name}.`;
}

avatarInput.addEventListener("change", function (event) {
  return displayAvatar(event.target.files);
});
avatarClear.addEventListener("click", function () {
  clearAvatarSelection("Picture change cancelled.");
});

avatarDropZone.addEventListener("dragover", function (event) {
  const fileItems = [...event.dataTransfer.items].filter(
    (item) => item.kind === "file",
  );
  if (fileItems.length > 0) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    avatarDropZone.classList.add("is-dragging");
  }
});

window.addEventListener("drop", function (event) {
  if ([...event.dataTransfer.items].some((item) => item.kind === "file")) {
    event.preventDefault();
  }
});

window.addEventListener("dragover", function (event) {
  const fileItems = [...event.dataTransfer.items].filter(
    (item) => item.kind === "file",
  );
  if (fileItems.length > 0) {
    event.preventDefault();
    if (!avatarDropZone.contains(event.target)) {
      event.dataTransfer.dropEffect = "none";
    }
  }
});

avatarDropZone.addEventListener("dragleave", function (event) {
  if (!avatarDropZone.contains(event.relatedTarget)) {
    avatarDropZone.classList.remove("is-dragging");
  }
});

function dropHandler(event) {
  event.preventDefault();
  avatarDropZone.classList.remove("is-dragging");
  const files = [...event.dataTransfer.items]
    .map((item) => item.getAsFile())
    .filter((file) => file);
  if (files.length === 0) {
    return;
  }
  avatarInput.files = event.dataTransfer.files;
  return displayAvatar(files);
}

avatarDropZone.addEventListener("drop", dropHandler);
