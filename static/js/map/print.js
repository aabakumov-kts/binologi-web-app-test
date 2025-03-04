"use strict";

function ControlPrint(controlDiv) {
  controlDiv.className = 'b-map-control-print';
  controlDiv.addEventListener('click', function () {
    $('body').addClass('print');
    initMap();
    setTimeout(function () {
      window.print();
    }, 1000);
    setTimeout(function () {
      $('body').removeClass('print');
      initMap();
    }, 1000);
  });
}

// Printing was disabled to avoid confusion caused by its incomplete functionality
function initPrint() {
  // var divPrint = document.createElement('div');
  // var controlPrint = new ControlPrint(divPrint);
  // divPrint.index = 1;
  // map.controls[google.maps.ControlPosition.LEFT_BOTTOM].push(divPrint);
}
