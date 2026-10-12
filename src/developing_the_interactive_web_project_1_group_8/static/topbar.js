console.log( "topbar.js loaded" );

const searchInput = document.getElementById( "search" );

var delayTimer;

// the timer is implemented to avoid making too many API calls while the user is typing
searchInput.addEventListener( "input", function ( event ) {
  const query = event.target.value;
  console.log( "Search query:", query );

  if ( delayTimer ) {
    clearTimeout( delayTimer );
  }

  delayTimer = setTimeout( function () {
    // Make an API call to the search endpoint with the query
    fetch( `/api/search?q=${ encodeURIComponent( query ) }` )
      .then( response => response.json() )
      .then( data => {
        console.log( "Search results:", data );
        // You can update the UI with the search results here
      } )
      .catch( error => {
        console.error( "Error fetching search results:", error );
      } );
    delayTimer = null;
  }, 500 ); // Delay of 500 milliseconds
} );