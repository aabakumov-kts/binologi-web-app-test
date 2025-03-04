// This is actually a callback executed by Google Maps SDK upon loading.
// noinspection JSUnusedGlobalSymbols
function initMap() {
    var map = new google.maps.Map(document.querySelector('.map-container'), {
        center: {lat: binPosition.lat, lng: binPosition.lng},
        scrollwheel: true,
        zoom: 15,
        mapTypeControl: false,
        scaleControl: false,
        zoomControl: true,
        zoomControlOptions: {
          position: google.maps.ControlPosition.LEFT_CENTER,
        },
        fullscreenControl: false,
        streetViewControl: false,
    });
    new google.maps.Marker({
        map: map,
        position: {lat: binPosition.lat, lng: binPosition.lng},
        draggable: false,
    });
}
