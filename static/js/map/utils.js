"use strict";
var currentData;

function getFilters() {
  return $.param({
    'waste_type': $('#waste_type').find('.selected').map(function () {
      return $(this).data('id');
    }).get(),
    'fullness': $('#fullness').find('.selected').map(function () {
      return $(this).data('id');
    }).get(),
    'error_type': $('#error_type').find('.selected').map(function () {
      return $(this).data('id');
    }).get(),
    'sector': $('#sector-filter').find('.selected').map(function () {
      return $(this).data('id');
    }).get(),
  }, true);
}

function getBounds(map) {
  var b = map.getBounds();
  if (typeof b === "undefined") return undefined;
  var bounds = b.toJSON();
  return $.param(bounds);
}

function setCurrentData(data) {
  currentData = data;
}

function findCurrentDataContainerById(id) {
  return _.find(currentData.containers, function (c) {
    return c.id === id;
  });
}

// Courtesy of this SO answer: https://stackoverflow.com/a/20361798/9335150
function pointToScreen(map, latLng) {
  var numTiles = 1 << map.getZoom();
  var projection = map.getProjection();
  var worldCoordinate = projection.fromLatLngToPoint(latLng);
  var pixelCoordinate = new google.maps.Point(worldCoordinate.x * numTiles, worldCoordinate.y * numTiles);

  var mapBounds = map.getBounds();
  var topLeft = new google.maps.LatLng(mapBounds.getNorthEast().lat(), mapBounds.getSouthWest().lng());

  var topLeftWorldCoordinate = projection.fromLatLngToPoint(topLeft);
  var topLeftPixelCoordinate = new google.maps.Point(
    topLeftWorldCoordinate.x * numTiles, topLeftWorldCoordinate.y * numTiles);

  return new google.maps.Point(
    pixelCoordinate.x - topLeftPixelCoordinate.x, pixelCoordinate.y - topLeftPixelCoordinate.y);
}
