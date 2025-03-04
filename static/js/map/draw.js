"use strict";

var markerColorsByFullness = {
  0: '#1ea51b',
  50: [ '#ffe400', '#d9c200' ],
  75: '#ff7200',
  90: '#ff0000',
};
var disabledStationPartColor = '#d0d0d0';
var checkmark = '✓';
var statusIconSize = 30;
var multiStationColor = '#4D4FB7';

var paper;

function paperToDataUrl(paper) {
  var svg = paper.toSVG();
  var encoded = encodeURIComponent(svg).replace(/'/g, '%27').replace(/"/g, '%22');
  return 'data:image/svg+xml,' + encoded;
}

function drawStatusIcons(icons) {
  if (!icons) return;
  var iconsToDraw = Math.min(icons.length, 5);
  for (var i = 0; i < iconsToDraw; i++) {
    paper.image(icons[i], 100, i * statusIconSize, statusIconSize, statusIconSize);
  }
}

function drawTip(color) {
  var tip = paper.path('M75,50L91,78L50,150L75,50');
  tip.attr('stroke-width', 0);
  tip.attr('fill', color);
}

function drawTrashbinMarker(color, text, textColor, icons) {
  paper.clear();

  drawTip(color);

  var outerCircle = paper.circle(50, 50, 50);
  outerCircle.attr('stroke-width', 0);
  outerCircle.attr('fill', color);

  var innerCircle = paper.circle(50, 50, 37);
  innerCircle.attr('stroke-width', 0);
  innerCircle.attr('fill', '#fff');

  var label = paper.text(50, 50, text);
  label.attr('fill', textColor || color);
  label.attr('font-weight', 'bold');
  label.scale(3.7);

  drawStatusIcons(icons);

  return paperToDataUrl(paper);
}

function drawStationMarker(color, text, textColor, segments, icons) {
  paper.clear();

  drawTip(color);

  var outerRect = paper.rect(0, 0, 100, 100);
  outerRect.attr('stroke-width', 0);
  outerRect.attr('fill', color);

  if (segments && segments.length > 0) {
    if (segments.length === 1) {
      var segmentRect = paper.rect(0, 50, 100, 50);
      segmentRect.attr('stroke-width', 0);
      segmentRect.attr('fill', segments[0]);
    }
    else if (segments.length === 2) {
      var segment1Rect = paper.rect(0, 50, 50, 50);
      segment1Rect.attr('stroke-width', 0);
      segment1Rect.attr('fill', segments[0]);

      var segment2Rect = paper.rect(50, 50, 50, 50);
      segment2Rect.attr('stroke-width', 0);
      segment2Rect.attr('fill', segments[1]);
    }
    var horizontalDelimiter = paper.rect(0, 47, 100, 6);
    horizontalDelimiter.attr('stroke-width', 0);
    horizontalDelimiter.attr('fill', '#fff');
    if (segments.length === 2) {
      var verticalDelimiter = paper.rect(47, 47, 6, 53);
      verticalDelimiter.attr('stroke-width', 0);
      verticalDelimiter.attr('fill', '#fff');
    }
  }

  var innerRect = paper.rect(13, 13, 74, 74, 3);
  innerRect.attr('stroke-width', 0);
  innerRect.attr('fill', '#fff');

  var label = paper.text(50, 50, text);
  label.attr('fill', textColor || color);
  label.attr('font-weight', 'bold');
  label.scale(3.7);

  drawStatusIcons(icons);

  return paperToDataUrl(paper);
}

function drawSensorMarker(color, text, textColor, icons) {
  paper.clear();

  drawTip(color);

  var outerCircle = paper.circle(50, 50, 50);
  outerCircle.attr('stroke-width', 0);
  outerCircle.attr('fill', color);

  if (text) {
    var label = paper.text(50, 50, text);
    label.attr('fill', textColor);
    label.attr('font-weight', 'bold');
    label.scale(3.7);
  }

  drawStatusIcons(icons);

  return paperToDataUrl(paper);
}

function getBinImage(container, currentCard) {
  var markerColors = markerColorsByFullness[container.fullness.title];
  var primaryColor = typeof markerColors === 'string' ? markerColors : markerColors[0];
  var textColor = typeof markerColors === 'string' ? markerColors : markerColors[1];
  var text = currentCard && currentCard[0] === binDeviceType && currentCard[1] === container.id
    ? checkmark : container.fullness.value.toString();
  var icons = [];
  if (!!container.any_active_errors) icons.push(warningIconUrl);
  if (!!container.low_battery_level) icons.push(lowBatteryIconUrl);
  if (!!container.any_active_routes) icons.push(binOnRouteIconUrl);
  return drawTrashbinMarker(primaryColor, text, textColor, icons);
}

function getStationImage(station, currentCard) {
  var masterContainer = findCurrentDataContainerById(station.master);
  var satelliteContainers = _.map(station.satellites, findCurrentDataContainerById);
  var activeContainers = _.filter(_.concat([masterContainer], satelliteContainers), function(c) { return !!c; });

  var icons = [];
  if (_.some(activeContainers, function(c) { return !!c.any_active_errors; })) icons.push(warningIconUrl);
  if (_.some(activeContainers, function(c) { return !!c.low_battery_level; })) icons.push(lowBatteryIconUrl);
  if (_.some(activeContainers, function(c) { return !!c.any_active_routes; })) icons.push(binOnRouteIconUrl);

  var text = currentCard && currentCard[0] === binDeviceType && (
    station.master === currentCard[1] || station.satellites.indexOf(currentCard[1]) >=0)
    ? checkmark : undefined;
  if (activeContainers.length > 3 || (activeContainers.length === 3 && !masterContainer)) {
    if (!text) {
      var numberLabel = activeContainers.length > 9 ? '9+' : activeContainers.length.toString();
      text = 'x' + numberLabel;
    }
    return drawStationMarker(multiStationColor, text, multiStationColor, undefined, icons);
  }

  var containersSortedByFullness = _.reverse(_.sortBy(activeContainers, ['fullness.value']));
  var masterMarkerColors = masterContainer ? markerColorsByFullness[masterContainer.fullness.title] : disabledStationPartColor;
  var primaryColor = typeof masterMarkerColors === 'string' ? masterMarkerColors : masterMarkerColors[0];
  var maxFullnessColors = markerColorsByFullness[containersSortedByFullness[0].fullness.title];
  var textColor = typeof maxFullnessColors === 'string' ? maxFullnessColors : maxFullnessColors[1];
  var segments = _.chain(satelliteContainers)
    .map(function (c) {
      if (!c) return undefined;
      var auxMarkerColors = markerColorsByFullness[c.fullness.title];
      return typeof auxMarkerColors === 'string' ? auxMarkerColors : auxMarkerColors[0];
    })
    .filter(function (s) { return !!s; })
    .value();
  var totalSegments = Math.min(station.satellites.length, 2);
  if (segments.length < totalSegments) {
    segments = _.concat(segments, _.times(totalSegments - segments.length, _.constant(disabledStationPartColor)));
  }
  if (!text) text = containersSortedByFullness[0].fullness.value.toString();
  return drawStationMarker(primaryColor, text, textColor, segments, icons);
}

function getSensorImage(sensor, currentCard) {
  var markerColors = markerColorsByFullness[sensor.fullness.title];
  var icons = [];
  if (!!sensor.low_battery_level) icons.push(lowBatteryIconUrl);
  if (!!sensor.any_active_routes) icons.push(binOnRouteIconUrl);
  var primaryColor = typeof markerColors === 'string' ? markerColors : markerColors[0];
  var sensorSelected = currentCard && currentCard[0] === sensorDeviceType && currentCard[1] === sensor.id;
  if (sensor.mount_type === 'HORIZONTAL') {
    return drawSensorMarker(primaryColor, sensorSelected ? checkmark : undefined, '#ffffff', icons);
  } else {
    var textColor = typeof markerColors === 'string' ? markerColors : markerColors[1];
    var text = sensorSelected ? checkmark : sensor.fullness.value.toString();
    return drawTrashbinMarker(primaryColor, text, textColor, icons);
  }
}

function initDraw() {
  paper = new Raphael(document.getElementById('raphaelDiv'), 100 + statusIconSize, 150);
}
