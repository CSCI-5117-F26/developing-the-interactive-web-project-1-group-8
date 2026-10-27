function autocomplete(str, uri) {
  if (!str || !uri) {
    return;
  }

  var searchElement = document.getElementById("bgg-games-" + str);
  if (!searchElement) {
    return;
  }

  /*the autocomplete function takes two arguments,
  the text field element and an array of possible autocompleted values:*/
  var currentFocus;
  var delayTimer;
  if (!searchElement) {
    return;
  }
  /*execute a function when someone writes in the text field:*/
  searchElement.addEventListener("input", async function (e) {
    var a,
      b,
      i,
      val = this.value;
    /*close any already open lists of autocompleted values*/
    closeAllLists();
    searchElement.parentNode.querySelector(`input[name='${str}-key']`).value =
      "";
    searchElement.parentNode.querySelector(`input[name='${str}-value']`).value =
      "";
    currentFocus = -1;

    if (delayTimer) {
      clearTimeout(delayTimer);
    }
    if (!val.trim()) {
      return false;
    }

    /*create a DIV element that will contain the items (values):*/
    a = document.createElement("DIV");
    a.setAttribute("id", this.id + "autocomplete-list");
    a.setAttribute("class", "autocomplete-items");
    /*append the DIV element as a child of the autocomplete container:*/
    this.parentNode.parentNode.appendChild(a);

    delayTimer = setTimeout(async function () {
      delayTimer = null;
      if (val.trim() === "") return; // Don't make an API call for empty queries

      var data;

      if (typeof uri === "string") {
        // Make an API call to the search endpoint with the query
        data = await fetch(`${uri}?q=${encodeURIComponent(val)}`)
          .then((response) => response.json())
          .catch(() => []);
      } else if (typeof uri === "object") {
        // Filter the provided object for matching values
        data = Object.entries(uri)
          .filter(([key, value]) =>
            key.toLowerCase().includes(val.toLowerCase()),
          )
          .map(([key, value]) => ({ name: key, id: value }));
      } else {
        console.error("Invalid URI type. Must be a string or an object.");
        return;
      }

      if (!a.isConnected || searchElement.value !== val) return;
      console.log("Search results:", data);

      /*for each item in the array...*/
      for (i = 0; i < data.length; i++) {
        /*create a DIV element for each matching element:*/
        b = document.createElement("DIV");

        /*make the matching letters bold:*/
        const name = data[i].name;
        let start = 0,
          matchIndex;
        while (
          (matchIndex = name
            .toLowerCase()
            .indexOf(val.toLowerCase(), start)) !== -1
        ) {
          b.append(name.slice(start, matchIndex));
          const strong = document.createElement("strong");
          strong.textContent = name.slice(matchIndex, matchIndex + val.length);
          b.appendChild(strong);
          start = matchIndex + val.length;
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
          searchElement.setAttribute(
            "value",
            this.getElementsByTagName("input")[0].value,
          );
          searchElement.value = this.getElementsByTagName("input")[0].value;

          /*insert the value for the hidden input field:*/
          searchElement.parentNode.querySelector(
            `input[name='${str}-value']`,
          ).value = this.getElementsByTagName("input")[1].value;
          searchElement.parentNode.querySelector(
            `input[name='${str}-key']`,
          ).value = this.getElementsByTagName("input")[0].value;
          /*close the list of autocompleted values,
          (or any other open lists of autocompleted values:*/
          closeAllLists();
        });
        a.appendChild(b);
        // }
      }
    }, 500);
  }); // Delay of 500 milliseconds

  /*execute a function presses a key on the keyboard:*/
  searchElement.addEventListener("keydown", function (e) {
    var x = document.getElementById(this.id + "autocomplete-list");
    if (x) x = x.getElementsByTagName("div");
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
      /*Only prevent submission when selecting a highlighted suggestion.*/
      if (x && x.length && currentFocus > -1) {
        e.preventDefault();
        /*and simulate a click on the "active" item:*/
        if (x) x[currentFocus].click();
      }
    }
  });

  function addActive(x) {
    /*a function to classify an item as "active":*/
    if (!x || !x.length) return false;
    /*start by removing the "active" class on all items:*/
    removeActive(x);
    if (currentFocus >= x.length) currentFocus = 0;
    if (currentFocus < 0) currentFocus = x.length - 1;
    /*add class "autocomplete-active":*/
    x[currentFocus].classList.add("active");
  }
  function removeActive(x) {
    /*a function to remove the "active" class from all autocomplete items:*/
    for (var i = 0; i < x.length; i++) {
      x[i].classList.remove("active");
    }
  }
  function closeAllLists(elmnt) {
    /*close all autocomplete lists in the document,
  except the one passed as an argument:*/
    var x = document.getElementsByClassName("autocomplete-items");
    for (var i = x.length - 1; i >= 0; i--) {
      if (elmnt != x[i] && elmnt != searchElement) {
        x[i].parentNode.removeChild(x[i]);
      }
    }
  }
  /*execute a function when someone clicks in the document:*/
  document.addEventListener("click", function (e) {
    closeAllLists(e.target);
  });
}

const categories = {
  "Abstract Strategy": 1009,
  "Action / Dexterity": 1032,
  Adventure: 1022,
  "Age of Reason": 2726,
  "American Civil War": 1048,
  "American Indian Wars": 1108,
  "American Revolutionary War": 1075,
  "American West": 1055,
  Ancient: 1050,
  Animals: 1089,
  Arabian: 1052,
  "Aviation / Flight": 2650,
  Bluffing: 1023,
  Book: 1117,
  "Card Game": 1002,
  "Children's Game": 1041,
  "City Building": 1029,
  "Civil War": 1102,
  Civilization: 1015,
  "Collectible Components": 1044,
  "Comic Book / Strip": 1116,
  Deduction: 1039,
  Dice: 1017,
  Economic: 1021,
  Educational: 1094,
  Electronic: 1072,
  Environmental: 1084,
  "Expansion for Base-game": 1042,
  Exploration: 1020,
  "Fan Expansion": 2687,
  Fantasy: 1010,
  Farming: 1013,
  Fighting: 1046,
  "Game System": 1119,
  Horror: 1024,
  Humor: 1079,
  "Industry / Manufacturing": 1088,
  "Korean War": 1091,
  Mafia: 1033,
  Math: 1104,
  "Mature / Adult": 1118,
  Maze: 1059,
  Medical: 2145,
  Medieval: 1035,
  Memory: 1045,
  Miniatures: 1047,
  "Modern Warfare": 1069,
  "Movies / TV / Radio theme": 1064,
  "Murder / Mystery": 1040,
  Music: 1054,
  Mythology: 1082,
  Napoleonic: 1051,
  Nautical: 1008,
  Negotiation: 1026,
  "Novel-based": 1093,
  Number: 1098,
  "Party Game": 1030,
  "Pike and Shot": 2725,
  Pirates: 1090,
  Political: 1001,
  "Post-Napoleonic": 2710,
  Prehistoric: 1036,
  "Print & Play": 1120,
  Puzzle: 1028,
  Racing: 1031,
  "Real-time": 1037,
  Religious: 1115,
  Renaissance: 1070,
  "Science Fiction": 1016,
  "Space Exploration": 1113,
  "Spies / Secret Agents": 1081,
  Sports: 1038,
  "Territory Building": 1086,
  "Third-party Expansion": 3129,
  Trains: 1034,
  Transportation: 1011,
  Travel: 1097,
  Trivia: 1027,
  "Video Game Theme": 1101,
  "Vietnam War": 1109,
  Wargame: 1019,
  "Word Game": 1025,
  "World War I": 1065,
  "World War II": 1049,
  Zombies: 2481,
};

const mechanics = {
  Acting: 2073,
  "Action / Event": 2840,
  "Action Drafting": 2838,
  "Action Points": 2001,
  "Action Queue": 2689,
  "Action Retrieval": 2839,
  "Action Timer": 2834,
  "Advantage Token": 2847,
  "Algorithmic Resolution": 3140,
  Alliances: 2916,
  "Area Majority / Influence": 2080,
  "Area Movement": 2046,
  "Area-Impulse": 2021,
  "Auction / Bidding": 2012,
  "Auction Compensation": 3098,
  "Auction: Dexterity": 2930,
  "Auction: Dutch": 2924,
  "Auction: Dutch Priority": 2932,
  "Auction: English": 2918,
  "Auction: Fixed Placement": 2931,
  "Auction: Multiple Lot": 2927,
  "Auction: Once Around": 2923,
  "Auction: Sealed Bid": 2920,
  "Auction: Turn Order Until Pass": 2919,
  "Automatic Resource Growth": 2903,
  "Betting and Bluffing": 2014,
  Bias: 2957,
  "Bids As Wagers": 3097,
  Bingo: 2999,
  Bribery: 2913,
  "Campaign / Battle Card Driven": 2018,
  "Card Play Conflict Resolution": 2857,
  "Catch the Leader": 2887,
  Chaining: 2956,
  "Chit-Pull System": 2057,
  "Closed Drafting": 2984,
  "Closed Economy Auction": 2928,
  "Command Cards": 2841,
  "Commodity Speculation": 2013,
  "Communication Limits": 2893,
  Connections: 2883,
  "Constrained Bidding": 2922,
  Contracts: 2912,
  "Cooperative Game": 2023,
  "Crayon Rail System": 2010,
  "Critical Hits and Failures": 2854,
  "Cube Tower": 2990,
  "Deck Construction": 3004,
  "Deck, Bag, and Pool Building": 2664,
  Deduction: 3002,
  "Delayed Purchase": 2901,
  "Dice Rolling": 2072,
  "Die Icon Resolution": 2856,
  "Different Dice Movement": 2950,
  Drawing: 3096,
  "Elapsed Real Time Ending": 2882,
  Enclosure: 2043,
  "End Game Bonuses": 2875,
  Events: 2850,
  "Expiring Actions": 3139,
  Facing: 3143,
  "Finale Ending": 2885,
  Flicking: 2860,
  Follow: 2843,
  "Force Commitment": 2864,
  "Grid Coverage": 2978,
  "Grid Movement": 2676,
  "Hand Management": 2040,
  Handicaps: 3137,
  "Hexagon Grid": 2026,
  "Hidden Movement": 2967,
  "Hidden Roles": 2891,
  "Hidden Victory Points": 2987,
  "Highest-Lowest Scoring": 2889,
  "Hot Potato": 3000,
  "I Cut, You Choose": 2906,
  "Impulse Movement": 2952,
  Income: 2902,
  "Increase Value of Unchosen Resources": 2914,
  Induction: 3003,
  Interrupts: 2837,
  Investment: 2910,
  "Kill Steal": 2871,
  "King of the Hill": 2886,
  "Ladder Climbing": 2980,
  "Lane Battler": 3144,
  Layering: 3001,
  "Legacy Game": 2824,
  "Line Drawing": 2039,
  "Line of Sight": 2975,
  Loans: 2904,
  "Lose a Turn": 2836,
  Mancala: 2955,
  "Map Addition": 2959,
  "Map Deformation": 2961,
  "Map Reduction": 2960,
  Market: 2900,
  Matching: 3007,
  "Measurement Movement": 2949,
  "Melding and Splaying": 2981,
  Memory: 2047,
  "Minimap Resolution": 2863,
  "Modular Board": 2011,
  "Move Through Deck": 2962,
  "Movement Points": 2947,
  "Movement Template": 2963,
  "Moving Multiple Units": 2958,
  "Multi-Use Cards": 3099,
  "Multiple Maps": 2965,
  "Narrative Choice / Paragraph": 2851,
  Negotiation: 2915,
  "Neighbor Scope": 3104,
  "Network and Route Building": 2081,
  "Once-Per-Game Abilities": 2846,
  "Open Drafting": 2041,
  "Order Counters": 2844,
  Ordering: 3101,
  Ownership: 2911,
  "Paper-and-Pencil": 2055,
  "Passed Action Token": 2835,
  "Pattern Building": 2048,
  "Pattern Movement": 2946,
  "Pattern Recognition": 2060,
  "Physical Removal": 2989,
  "Pick-up and Deliver": 2007,
  "Pieces as Map": 2964,
  "Player Elimination": 2685,
  "Player Judge": 2865,
  "Point to Point Movement": 2078,
  "Predictive Bid": 3006,
  "Prisoner's Dilemma": 2858,
  "Programmed Movement": 2953,
  "Push Your Luck": 2661,
  "Questions and Answers": 3102,
  Race: 2876,
  "Random Production": 2909,
  "Ratio / Combat Results Table": 2855,
  "Re-rolling and Locking": 2870,
  "Real-Time": 2831,
  "Relative Movement": 2954,
  "Resource Queue": 3103,
  "Resource to Move": 2948,
  Retirement: 3141,
  "Rock-Paper-Scissors": 2003,
  "Role Playing": 2028,
  "Roles with Asymmetric Information": 2892,
  "Roll / Spin and Move": 2035,
  Rondel: 2813,
  "Scenario / Mission / Campaign Game": 2822,
  "Score-and-Reset Game": 2823,
  "Secret Unit Deployment": 2016,
  "Selection Order Bid": 2926,
  "Semi-Cooperative Game": 2820,
  "Set Collection": 2004,
  Simulation: 2070,
  "Simultaneous Action Selection": 2020,
  Singing: 2038,
  "Single Loser Game": 2821,
  "Single Play": 3138,
  "Slide / Push": 3005,
  "Solo / Solitaire Game": 2819,
  "Speed Matching": 2991,
  Spelling: 3113,
  "Square Grid": 2940,
  "Stacking and Balancing": 2988,
  "Stat Check Resolution": 2853,
  "Static Capture": 2861,
  "Stock Holding": 2005,
  Storytelling: 2027,
  "Sudden Death Ending": 2884,
  Tags: 3100,
  "Take That": 2686,
  "Targeted Clues": 2866,
  "Team-Based Game": 2019,
  "Tech Trees / Tech Tracks": 2849,
  "Three Dimensional Movement": 2944,
  "Tile Placement": 2002,
  "Track Movement": 2939,
  Trading: 2008,
  "Traitor Game": 2814,
  "Trick-taking": 2009,
  "Tug of War": 2888,
  "Turn Order: Auction": 2827,
  "Turn Order: Claim Action": 2829,
  "Turn Order: Pass Order": 2830,
  "Turn Order: Progressive": 2828,
  "Turn Order: Random": 2985,
  "Turn Order: Role Order": 2833,
  "Turn Order: Stat-Based": 2826,
  "Turn Order: Time Track": 2663,
  "Variable Phase Order": 2079,
  "Variable Player Powers": 2015,
  "Variable Set-up": 2897,
  "Victory Points as a Resource": 2874,
  "Visual Restriction": 3142,
  Voting: 2017,
  "Worker Placement": 2082,
  "Worker Placement with Dice Workers": 2935,
  "Worker Placement, Different Worker Types": 2933,
  "Zone of Control": 2974,
};

const subdomain = {
  "Abstract Games": 4666,
  "Children's Games": 4665,
  "Customizable Games": 4667,
  "Family Games": 5499,
  "Party Games": 5498,
  "Strategy Games": 5497,
  "Thematic Games": 5496,
  Wargames: 4664,
};

autocomplete("search", "/api/search-games");
autocomplete("categories", categories);
autocomplete("mechanics", mechanics);
autocomplete("subdomains", subdomain);
