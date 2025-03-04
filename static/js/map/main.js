var map;
var markers = [];
var mapRefreshInterval = 300000;
var animatedMarkersAppearance = false;
var refreshMapInterval;
var scaledMarkerImageSize;
var markerClusterer;
var effectiveAutoCard = undefined;

function addMarker(location, onClickHandler, pickable) {
  var markerOpts = {
    position: {lat: location.y, lng: location.x},
    draggable: pickable,
  };
  if (!animatedMarkersAppearance) markerOpts.animation = google.maps.Animation.DROP;

  var marker = new google.maps.Marker(markerOpts);

  google.maps.event.clearInstanceListeners(marker);
  if (onClickHandler) marker.addListener('click', onClickHandler);
  if (pickable && typeof getMarkerDragListeners === 'function') {
    var dragListeners = getMarkerDragListeners(marker);
    google.maps.event.addListener(marker, 'dragstart', dragListeners[0]);
    google.maps.event.addListener(marker, 'dragend', dragListeners[1]);
  }

  markers.push(marker);
  return marker;
}

function createMarkerClusterer(map, markers, avoidDrawClusters) {
  var clustererOpts = {};
  // Set cluster min size to arbitrary high number to avoid clusters being drawn
  if (avoidDrawClusters) clustererOpts.minimumClusterSize = 2147483647;  // 2^31
  var clusterer = new MarkerClusterer(map, markers, clustererOpts);
  // Had to hack the way through since overriding styles via official API doesn't work as expected
  for (var i = 0; i < 5; i++) {
    clusterer.styles_[i].url = clusterImagesUrls[i];
    clusterer.styles_[i].textSize = 15;
  }
  return clusterer;
}

function refreshMarkerIcon(m) {
  var iconUrl = undefined;
  if (!!m.container) iconUrl = getBinImage(m.container, getCurrentCard());
  if (!!m.station) iconUrl = getStationImage(m.station, getCurrentCard());
  if (!!m.sensor) iconUrl = getSensorImage(m.sensor, getCurrentCard());
  if (iconUrl) {
    m.setIcon({
      url: iconUrl,
      scaledSize: scaledMarkerImageSize,
      anchor: new google.maps.Point(24, scaledMarkerImageSize.height),
    });
  }
}

function showDevices() {
  var filters = getFilters();
  var bounds = getBounds(map);
  if (typeof bounds === "undefined") return;

  var binsRequest = fetchTrashbins
    ? $.getJSON('/api/containers/?' + filters + '&' + bounds)
    : [ { stations: [], containers: [] } ];
  var sensorsRequest = fetchSensors
    ? $.getJSON('/api/sensors/?' + filters + '&' + bounds)
    : [ { sensors: [] } ];

  var autoCardMarker = undefined;

  $.when(binsRequest, sensorsRequest).then(function (containersResp, sensorsResp) {
    setCurrentData(containersResp[0]);
    var oldClusterer = markerClusterer;
    markers = [];
    var clusteredContainers = [];

    containersResp[0].stations.forEach(function (station) {
      var marker = addMarker(station.location, function () {
        setCurrentStation(station);
        var firstActiveBin = _.chain(_.concat([station.master], station.satellites))
          .map(findCurrentDataContainerById)
          .filter(function(c) { return !!c; })
          .value()[0];
        initActiveCard(binDeviceType, firstActiveBin.id);
      }, true);
      marker.station = station;
      clusteredContainers.push(station.master);
      station.satellites.forEach(function(id) { clusteredContainers.push(id); });

      if (effectiveAutoCard && effectiveAutoCard.type === binDeviceType && (
          effectiveAutoCard.pk === station.master.toString() || _.some(station.satellites, function(s) { return s.toString() === effectiveAutoCard.pk; }))
      ) {
        autoCardMarker = marker;
      }
    });

    containersResp[0].containers.forEach(function (container) {
      // Don't show clustered containers on their own.
      if (clusteredContainers.indexOf(container.id) >= 0) return;

      var marker = addMarker(container.location, function () {
        setCurrentStation(undefined);
        initActiveCard(binDeviceType, container.id);
      }, true);
      marker.container = container;

      if (effectiveAutoCard && effectiveAutoCard.type === binDeviceType && effectiveAutoCard.pk === container.id.toString()) {
        autoCardMarker = marker;
      }
    });

    sensorsResp[0].sensors.forEach(function (sensor) {
      var marker = addMarker(sensor.location, function () {
        setCurrentStation(undefined);
        initActiveCard(sensorDeviceType, sensor.id);
      }, false);
      marker.sensor = sensor;

      if (effectiveAutoCard && effectiveAutoCard.type === sensorDeviceType && effectiveAutoCard.pk === sensor.id.toString()) {
        autoCardMarker = marker;
      }
    });

    if (!animatedMarkersAppearance) animatedMarkersAppearance = true;

    // Disallow clustering at highest zoom level to allow individual bins to be seen
    var avoidDrawClusters = map.getZoom() >= 22;
    markerClusterer = createMarkerClusterer(map, markers, avoidDrawClusters);
    markerClusterer.addListener("clusteringend", function() {
      var clusters = markerClusterer.getClusters();
      _.chain(clusters)
        .filter(function (c) { return c.getSize() === 1 || avoidDrawClusters })
        .map(function (c) { return c.getMarkers(); })
        .flatten()
        .value()
      .forEach(refreshMarkerIcon);
    });

    if (oldClusterer) {
      setTimeout(function() {
        oldClusterer.clearMarkers();
        oldClusterer.setMap(null);
      }, 100);
    }

    if (effectiveAutoCard && autoCardMarker) {
      map.setCenter(autoCardMarker.getPosition());
      google.maps.event.trigger(autoCardMarker, 'click');
      effectiveAutoCard = undefined;
    }
  });
}

var debouncedShowContainers = _.debounce(showDevices, 500);
var longDebouncedShowContainers = _.debounce(showDevices, 1000);

// This is actually a callback executed by Google Maps SDK upon loading.
// noinspection JSUnusedGlobalSymbols
function initMap() {
  var effectiveMapPositioning = mapPositioning;
  if (!mapPositioning.override) {
    var savedMapCenter = getMapCenter();
    if (savedMapCenter) effectiveMapPositioning.center = savedMapCenter;
    var savedZoomLevel = getMapZoomLevel();
    if (savedZoomLevel) effectiveMapPositioning.zoom = savedZoomLevel;
    else if (effectiveMapPositioning.bounds) {
      // Courtesy of this SO answer: https://stackoverflow.com/a/6055653/9335150
      var GLOBE_WIDTH = 256; // a constant in Google's map projection
      var west = effectiveMapPositioning.bounds.lngMin;
      var east = effectiveMapPositioning.bounds.lngMax;
      var angle = east - west;
      if (angle < 0) angle += 360;
      var zoomLevel = Math.floor(Math.log(document.body.clientWidth * 360 / angle / GLOBE_WIDTH) / Math.LN2);
      if (zoomLevel > 15) zoomLevel = 15;  // Empirical max zoom level
      effectiveMapPositioning.zoom = zoomLevel;
    }
  }
  // Create a map object and specify the DOM element for display.
  map = new google.maps.Map(document.getElementById('map-google-js'), {
    center: effectiveMapPositioning.center,
    scrollwheel: true,
    zoom: effectiveMapPositioning.zoom,
    mapTypeControl: false,
    scaleControl: false,
    zoomControl: true,
    zoomControlOptions: {
      position: google.maps.ControlPosition.LEFT_CENTER,
    },
    fullscreenControl: false,
    streetViewControl: false,
  });

  initPrint();

  if (typeof autoOpenCard !== 'undefined') {
    effectiveAutoCard = autoOpenCard;
  }

  map.addListener('dragend', function() {
    debouncedShowContainers();
  });
  map.addListener('center_changed', function() {
    setMapCenter(map.getCenter());
    debouncedShowContainers();
  });
  map.addListener('zoom_changed', function() {
    setMapZoomLevel(map.getZoom());
    debouncedShowContainers();
  });

  if (typeof initAreaSelectionOnMap === 'function') {
    initAreaSelectionOnMap(map, function() {
      return markers;
    });
  }

  google.maps.event.addListenerOnce(map, 'idle', function () {
    showDevices();
  });
}

function toggleClearFilters() {
  var anyFilterActive = $('.b-maps-filter').find('li.selected').length > 0;
  if (anyFilterActive) {
    $('.b-maps-clear-filters').show();
  } else {
    $('.b-maps-clear-filters').hide();
  }
}

$(document).ready(function () {
  scaledMarkerImageSize = new google.maps.Size(62.4, 72);
  initDraw();

  $('.b-maps-filter').find('li').on('click', function () {
    $(this).toggleClass('selected');
    var parent = $(this).parents('.b-maps-filter');
    var has_selected = parent.find('li.selected').length > 0;
    var button = parent.find('.b-maps-filter-button');
    var parentGroup = $(this).parent();
    var buttonGroup = parentGroup.prev('.b-maps-filter-group-header');

    if (has_selected) {
      button.addClass('selected');
    } else {
      button.removeClass('selected');
    }
    if (parentGroup.find('li.selected').length > 0) {
      buttonGroup.addClass('selected');
    } else {
      buttonGroup.removeClass('selected');
    }
    toggleClearFilters();
    longDebouncedShowContainers();
  });

  $('.b-maps-filter-group-header').click(function () {
    var is_open = $(this).parent('.b-maps-filter-group').hasClass('open');
    $('.b-maps-filter-group').removeClass('open');
    $('.b-maps-filter-grouper').css('transform', 'translateY(0)');
    if (is_open === false) {
      $(this).parent('.b-maps-filter-group').addClass('open');
      if ($(this).parent('#error_type')) {
        var shiftedGroup = $('#error_type');
        var secondGroup = shiftedGroup.find('.b-maps-filter-grouper').eq(1);
        var secondGroupBottom = secondGroup.length > 0 ? secondGroup.offset().top + secondGroup.outerHeight() : 0;
        var winHeight = $(window).height();
        var shift = secondGroupBottom - winHeight;
        if (shift > 0) {
          shiftedGroup.find('.b-maps-filter-grouper').css('transform', 'translateY(-' + shift + 'px)');
        }
      }
    }
  });

  $('#build-route').on('click', function (event) {
    event.preventDefault();
    var url = '/routes/create/?' + getFilters() + '&' + getBounds(map);
    if (typeof getPickedBinsSerials === 'function') {
      var pickedSerials = getPickedBinsSerials();
      if (pickedSerials.length > 0) {
        url += '&' + jQuery.param({'serial': pickedSerials}, true);
      }
    }
    window.location = url + '&returnTo=/main/';
  });

  $('.b-maps-clear-filters').on('click', function() {
    $('.b-maps-filter').find('li.selected').removeClass('selected');
    $('.b-maps-filter-button.selected').removeClass('selected');
    $('.b-maps-filter-group-header.selected').removeClass('selected')
      .parent('.b-maps-filter-group').removeClass('open');
    toggleClearFilters();
    longDebouncedShowContainers();
  });

  refreshMapInterval = setInterval(function () {
    showDevices();
  }, mapRefreshInterval);

  if (typeof initCards === 'function') {
    initCards(function(devices) {
      _.filter(
        _.map(devices, function (device) {
          var id = device[1];
          return _.find(markers, function (m) {
            if (device[0] === binDeviceType) {
              var markerForContainer = !!m.container && m.container.id === id;
              var markerForCluster = !!m.station && (m.station.master === id || m.station.satellites.indexOf(id) >=0);
              return markerForContainer || markerForCluster;
            } else if (device[0] === sensorDeviceType) {
              return !!m.sensor && m.sensor.id === id;
            } else {
              return undefined;
            }
          });
        }),
        function (m) {
          return !!m;
        },
      ).forEach(refreshMarkerIcon);
    });
  }

  if (typeof initPickMarkers === 'function') {
    initPickMarkers(function(latLng) {
      map.panTo(latLng);
    });
  }

  if (typeof addAreaSelectionDocumentBindings === 'function') addAreaSelectionDocumentBindings(map);

  if (typeof initEfficiencyMonitor === 'function') initEfficiencyMonitor();
});
