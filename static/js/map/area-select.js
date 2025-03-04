var drawingManager;
var lastShape;

var shift_draw = false;

var selectionRectOptions = {
  strokeWeight: 1,
  strokeOpacity: 1,
  fillOpacity: 0.2,
  editable: false,
  clickable: false,
  strokeColor: '#3399FF',
  fillColor: '#3399FF',
};

function dropLastShape() {
  if (!lastShape) return;
  lastShape.setMap(null);
  lastShape = undefined;
}

function initAreaSelectionOnMap(map, getMarkers) {
  drawingManager = new google.maps.drawing.DrawingManager({
    drawingControl: false,
    drawingMode: null,
    drawingControlOptions: {drawingModes: [google.maps.drawing.OverlayType.POLYGON, google.maps.drawing.OverlayType.RECTANGLE]},
    rectangleOptions: selectionRectOptions,
    polygonOptions: selectionRectOptions,
    map: map
  });

  google.maps.event.addListener(map, 'mousedown', function () {
    dropLastShape();
  });

  google.maps.event.addListener(map, 'drag', function () {
    dropLastShape();
  });

  google.maps.event.addListener(drawingManager, 'overlaycomplete', function(e) {
    dropLastShape();

    // cancel drawing mode
    if (shift_draw === false) { drawingManager.setDrawingMode(null); }

    lastShape = e.overlay;
    lastShape.type = e.type;

    var intersectedMarker = undefined;
    var markers = getMarkers();
    if (lastShape.type === google.maps.drawing.OverlayType.RECTANGLE) {
      var lastBounds = lastShape.getBounds();
      intersectedMarker = _.find(markers, function (m) {
        return lastBounds.contains(m.getPosition());
      });
    } else if (lastShape.type === google.maps.drawing.OverlayType.POLYGON) {
      intersectedMarker = _.find(markers, function (m) {
        return google.maps.geometry.poly.containsLocation(m.getPosition(), lastShape);
      });
    }

    if (intersectedMarker) {
      google.maps.event.trigger(intersectedMarker, 'click');
    }

    dropLastShape();
  });
}

function addAreaSelectionDocumentBindings(map) {
  $(document).bind('keydown', function(e) {
    // Left shift keycode = 16
    if (e.keyCode === 16 && shift_draw === false) {
      map.setOptions({draggable: false, disableDoubleClickZoom: true});
      shift_draw = true;
      drawingManager.setDrawingMode(google.maps.drawing.OverlayType.RECTANGLE);
    }
  });

  $(document).bind('keyup', function(e) {
    if(e.keyCode === 16){
      map.setOptions({draggable: true, disableDoubleClickZoom: true});
      shift_draw = false;
      drawingManager.setDrawingMode(null);
    }
  });
}
