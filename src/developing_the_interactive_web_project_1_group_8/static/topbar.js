console.log( "topbar.js loaded" );

const searchInput = document.getElementById( "search" );
const searchForm = document.getElementById( "search-form" );
var delayTimer;

// the timer is implemented to avoid making too many API calls while the user is typing
searchInput.addEventListener( "input", function ( event ) {
  const query = event.target.value;

  if ( delayTimer ) {
    clearTimeout( delayTimer );
  }

  delayTimer = setTimeout( function () {
    if ( query.trim() === "" ) return; // Don't make an API call for empty queries

    // Make an API call to the search endpoint with the query
    fetch( `/api/search?q=${ encodeURIComponent( query ) }` )
      .then( response => response.json() )
      .then( data => {
        console.log( "Search results:", data );
        // Update the UI with the search results here
      } )
      .catch( error => {
        console.error( "Error fetching search results:", error );
      } );
    delayTimer = null;
  }, 500 ); // Delay of 500 milliseconds
} );


searchForm.addEventListener( "submit", function ( event ) {
  event.preventDefault();

  const query = searchInput.value.trim();
  if ( query == "" ) {
    return;
  }

  event.target.submit(); // Submit the form if the query is not empty

} );
