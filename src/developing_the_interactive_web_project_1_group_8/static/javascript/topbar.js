const searchInput = document.getElementById("search");
const searchForm = document.getElementById("search-form");
var delayTimer;
var currentFocus = -1;
// a lot of code is from https://dev.to/brunooliveira/flask-series-part-6-improving-user-input-with-autocomplete-4e06

// the timer is implemented to avoid making too many API calls while the user is typing
searchInput.addEventListener("input", async function (event) {
  const query = event.target.value;

  closeAllLists();
  if (delayTimer) {
    clearTimeout(delayTimer);
  }

  if (!query.trim()) return;
  currentFocus = -1;
  var a = document.createElement("DIV");
  a.setAttribute("id", this.id + "autocomplete-list");
  a.setAttribute("class", "autocomplete-items");
  a.style.width = searchInput.offsetWidth + "px";
  /*append the DIV element as a child of the autocomplete container:*/
  this.parentNode.parentNode.appendChild(a);

  delayTimer = setTimeout(function () {
    if (query.trim() === "") return; // Don't make an API call for empty queries
    var game = document.getElementsByName("search-value")[0]?.value ?? "";
    var gameName = document.getElementsByName("search-key")[0]?.value ?? "";
    var category =
      document.getElementsByName("categories-value")[0]?.value ?? "";
    var categoryName =
      document.getElementsByName("categories-key")[0]?.value ?? "";
    var usePlayerCounts =
      document.getElementById("use-num-players")?.checked ?? false;
    var minPlayer = document.getElementById("players-1")?.value ?? "";
    var maxPlayer = document.getElementById("players-2")?.value ?? "";
    var duration = document.getElementById("duration")?.value ?? "";
    var recency = document.getElementById("recency")?.value ?? "";
    var full = document.getElementById("hide-full")?.checked ?? "";
    var past = document.getElementById("past")?.checked ?? "";
    var played = document.getElementById("played-before")?.checked ?? "";
    var friends = document.getElementById("friend-events")?.checked ?? "";

    const params = new URLSearchParams();
    if (gameName && game) params.set("game", game);
    if (gameName) params.set("game-name", gameName);
    if (categoryName && category) params.set("category", category);
    if (categoryName) params.set("category-name", categoryName);
    if (usePlayerCounts && minPlayer) params.set("min", minPlayer);
    if (usePlayerCounts && maxPlayer) params.set("max", maxPlayer);
    if (duration) params.set("duration", duration);
    if (recency) params.set("recency", recency);
    if (full) params.set("full", full);
    if (past) params.set("past", past);
    if (played) params.set("played", played);
    if (friends) params.set("friends", friends);

    // Make an API call to the search endpoint with the query
    fetch(`/api/search?q=${encodeURIComponent(query)}&${params.toString()}`)
      .then((response) => response.json())
      .then((data) => {
        //console.log(data);
        if (!a.isConnected || searchInput.value !== query || !data.length)
          return;

        /*for each item in the array...*/
        for (var i = 0; i < data.length; i++) {
          /*create a DIV element for each matching element:*/
          var b = document.createElement("DIV");

          /*make the matching letters bold:*/
          const name = data[i].name;
          let start = 0,
            matchIndex;
          while (
            (matchIndex = name
              .toLowerCase()
              .indexOf(query.toLowerCase(), start)) !== -1
          ) {
            b.append(name.slice(start, matchIndex));
            const strong = document.createElement("strong");
            strong.textContent = name.slice(
              matchIndex,
              matchIndex + query.length,
            );
            b.appendChild(strong);
            start = matchIndex + query.length;
          }
          b.append(name.slice(start));

          /*insert a input field that will hold the current array item's value:*/
          for (const [field, value] of [
            ["name", name],
            ["id", data[i].id],
          ]) {
            const hidden = document.createElement("input");
            hidden.type = "hidden";
            hidden.name = field;
            hidden.value = value;
            b.appendChild(hidden);
          }

          /*execute a function when someone clicks on the item value (DIV element):*/
          b.addEventListener("click", function (e) {
            /*insert the value for the autocomplete text field:*/
            searchInput.value = this.getElementsByTagName("input")[0].value;
            /*close the list of autocompleted values,
              (or any other open lists of autocompleted values:*/
            closeAllLists();
            handleSearch();
          });
          a.appendChild(b);
          // }
        }
      })
      .catch((error) => {
        console.error("Error fetching search results:", error);
      });
    delayTimer = null;
  }, 500); // Delay of 500 milliseconds
});

/*execute a function presses a key on the keyboard:*/
searchInput.addEventListener("keydown", function (e) {
  var x = document.getElementById(this.id + "autocomplete-list");
  if (x) x = x.getElementsByTagName("div");
  if (!x || !x.length) return;
  if (e.keyCode == 40) {
    /*If the arrow DOWN key is pressed,
    increase the currentFocus variable:*/
    currentFocus++;
    /*and and make the current item more visible:*/
    addActive(x);
  } else if (e.keyCode == 38) {
    //up
    /*If the arrow UP key is pressed,
    decrease the currentFocus variable:*/
    currentFocus--;
    /*and and make the current item more visible:*/
    addActive(x);
  } else if (e.keyCode == 13) {
    /*If the ENTER key is pressed, prevent the form from being submitted,*/
    if (currentFocus > -1) {
      e.preventDefault();
      /*and simulate a click on the "active" item:*/
      if (x) x[currentFocus].click();
    }
  }
});

searchForm.addEventListener("submit", function (event) {
  event.preventDefault();

  handleSearch(); // Submit the form if the query is not empty
});

function closeAllLists(elmnt) {
  /*close all autocomplete lists in the document,
  except the one passed as an argument:*/
  var x = document.getElementsByClassName("autocomplete-items");
  for (var i = x.length - 1; i >= 0; i--) {
    if (elmnt != x[i] && elmnt != searchInput) {
      x[i].parentNode.removeChild(x[i]);
    }
  }
}

function removeActive(x) {
  /*a function to remove the "active" class from all autocomplete items:*/
  for (var i = 0; i < x.length; i++) {
    x[i].classList.remove("autocomplete-active");
  }
}

function addActive(x) {
  /*a function to classify an item as "active":*/
  if (!x || !x.length) return false;
  /*start by removing the "active" class on all items:*/
  removeActive(x);
  if (currentFocus >= x.length) currentFocus = 0;
  if (currentFocus < 0) currentFocus = x.length - 1;
  /*add class "autocomplete-active":*/
  x[currentFocus].classList.add("autocomplete-active");
}

function handleSearch() {
  var q = searchInput.value.trim();
  var game = document.getElementsByName("search-value")[0]?.value ?? "";
  var gameName = document.getElementsByName("search-key")[0]?.value ?? "";
  var category = document.getElementsByName("categories-value")[0]?.value ?? "";
  var categoryName =
    document.getElementsByName("categories-key")[0]?.value ?? "";
  var usePlayerCounts =
    document.getElementById("use-num-players")?.checked ?? false;
  var minPlayer = document.getElementById("players-1")?.value ?? "";
  var maxPlayer = document.getElementById("players-2")?.value ?? "";
  var duration = document.getElementById("duration")?.value ?? "";
  var recency = document.getElementById("recency")?.value ?? "";
  var full = document.getElementById("hide-full")?.checked ?? "";
  var past = document.getElementById("past")?.checked ?? "";
  var played = document.getElementById("played-before")?.checked ?? "";
  var friends = document.getElementById("friend-events")?.checked ?? "";

  const params = new URLSearchParams({ q });
  if (gameName && game) params.set("game", game);
  if (gameName) params.set("game-name", gameName);
  if (categoryName && category) params.set("category", category);
  if (categoryName) params.set("category-name", categoryName);
  if (usePlayerCounts && minPlayer) params.set("min", minPlayer);
  if (usePlayerCounts && maxPlayer) params.set("max", maxPlayer);
  if (duration) params.set("duration", duration);
  if (recency) params.set("recency", recency);
  if (full) params.set("full", full);
  if (past) params.set("past", past);
  if (played) params.set("played", played);
  if (friends) params.set("friends", friends);
  window.location.href = "/search?" + params.toString();
}
