const searchInput = document.getElementById("search");
const searchForm = document.getElementById("search-form");
var delayTimer;
var currentFocus = -1;
// a lot of code is from https://dev.to/brunooliveira/flask-series-part-6-improving-user-input-with-autocomplete-4e06

// the timer is implemented to avoid making too many API calls while the user is typing
searchInput.addEventListener("input", function (event) {
  const query = event.target.value;

  if (delayTimer) {
    clearTimeout(delayTimer);
  }

  delayTimer = setTimeout(function () {
    if (query.trim() === "") return; // Don't make an API call for empty queries

    // Make an API call to the search endpoint with the query
    fetch(`/api/search?q=${encodeURIComponent(query)}`)
      .then((response) => response.json())
      .then((data) => {
        console.log("Search results:", data);
        // Update the UI with the search results here
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
    e.preventDefault();
    if (currentFocus > -1) {
      /*and simulate a click on the "active" item:*/
      if (x) x[currentFocus].click();
    }
  }
});

searchForm.addEventListener("submit", function (event) {
  event.preventDefault();

  const query = searchInput.value.trim();
  if (query == "") {
    return;
  }

  event.target.submit(); // Submit the form if the query is not empty
});

function closeAllLists(elmnt) {
  /*close all autocomplete lists in the document,
  except the one passed as an argument:*/
  var x = document.getElementsByClassName("autocomplete-items");
  for (var i = 0; i < x.length; i++) {
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
