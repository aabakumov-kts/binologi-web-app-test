function formatToPointData(lat, lng) {
    return 'SRID=4326;POINT (' + lng + ' ' + lat + ')';
}

function getFromPointString(s) {
    var arr = ['55.7535037511883829', '37.6198482461064785'];
    if (s !== '') {
        s = s.replace("SRID=4326;POINT (", "").replace(")", "");
        arr = s.split(" ");
    }
    return {lat: Number(arr[1]), lng: Number(arr[0])};
}

function widgetpoint(id) {
    var coord = getFromPointString($('#' + id).val());
    $('#' + id + '_lat').val(coord.lat);
    $('#' + id + '_lon').val(coord.lng);

    var map = new google.maps.Map(document.getElementById('map_' + id), {
        center: {lat: coord.lat, lng: coord.lng},
        scrollwheel: true,
        zoom: 9,
        mapTypeControl: false,
        scaleControl: false,
        zoomControl: true,
        zoomControlOptions: {
          position: google.maps.ControlPosition.LEFT_CENTER,
        },
        fullscreenControl: false,
        streetViewControl: false,
    });

    var marker = new google.maps.Marker({
        map: map,
        position: {lat: coord.lat, lng: coord.lng},
        draggable: true,
    });

    google.maps.event.addListener(marker, 'dragend', function () {
        var markerPos = marker.getPosition();
        $('#' + id).val(formatToPointData(markerPos.lat(), markerPos.lng()));
        $('#' + id + '_lat').val(markerPos.lat());
        $('#' + id + '_lon').val(markerPos.lng());
    });

    function updateMarkerPosition() {
        var lat = Number($('#' + id + '_lat').val());
        var lng = Number($('#' + id + '_lon').val());
        $('#' + id).val(formatToPointData(lat, lng));
        marker.setPosition({lat: lat, lng: lng});
    }

    $('#' + id + '_lat').blur(updateMarkerPosition);
    $('#' + id + '_lon').blur(updateMarkerPosition);
}
