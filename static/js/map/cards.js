"use strict";
var currentCard = undefined; // Current card tuple: device type, device id
var currentStation = undefined;
var cardRefreshInterval = 100000;
var intervalEvents = [];
var deviceRefreshCallback = undefined;
var binDeviceType = 'bin';
var sensorDeviceType = 'sensor';

function stopIntervalEvents() {
  intervalEvents.forEach(function (interval) {
    clearInterval(interval);
  });
}

function updateCurrentCard(deviceInfo) {
  var devicesToRefresh = [];

  if (currentCard) devicesToRefresh.push(currentCard);
  currentCard = deviceInfo;
  if (deviceInfo) devicesToRefresh.push(deviceInfo);

  if (deviceRefreshCallback) deviceRefreshCallback(devicesToRefresh);
}

function refreshCardContent(content) {
  var collapsedFlags = [];
  $('#b-container-card').find('h5').each(function () {
    collapsedFlags.push($(this).next('div').hasClass('collapsed'));
  });

  $('#b-container-card').html(content).show();

  $('#map').addClass('with-card');
  $('#waste_type').addClass('b-filter-with-card');
  $('#sector-filter').addClass('b-filter-with-card');
  $('#clear-filters').addClass('b-filter-with-card');
  $('#efficiency-monitor').addClass('b-filter-with-card');

  $('.b-container-card-close').on('click', function () {
    $('#b-container-card').hide();

    $('#map').removeClass('with-card');
    $('#waste_type').removeClass('b-filter-with-card');
    $('#sector-filter').removeClass('b-filter-with-card');
    $('#clear-filters').removeClass('b-filter-with-card');
    $('#efficiency-monitor').removeClass('b-filter-with-card');

    updateCurrentCard(undefined);
    currentStation = undefined;
    stopIntervalEvents();
  });

  $('#b-container-card').find('h5').on('click', function () {
    $(this).next('div').toggleClass('collapsed');
  });

  if (collapsedFlags.length > 0) {
    $('#b-container-card').find('h5').each(function (index) {
      var divEl = $(this).next('div');
      if (collapsedFlags[index] !== divEl.hasClass('collapsed')) divEl.toggleClass('collapsed');
    });
  }

  $('#b-container-card h4 select').on('change', function () {
    window.location = $(this).children(":selected")[0].value;
  });
}

function getContainerCard(id) {
  if (currentCard && currentCard[0] === binDeviceType) {
    $('.b-container-card-next').hide();
    $('.b-container-card-previous').hide();
  }

  $.get('/settings/containers/' + id + '/map-card/', function (data) {
    refreshCardContent(data);

    if (currentStation) {
      $('.b-container-card-next').css('visibility','visible').on('click', function () {
        var new_id = undefined;
        if (currentCard[1] === currentStation.master) new_id = currentStation.satellites[0];
        else {
          var currentIndex = currentStation.satellites.indexOf(currentCard[1]);
          new_id = currentIndex === (currentStation.satellites.length - 1)
            ? currentStation.master : currentStation.satellites[currentIndex + 1];
        }
        initActiveCard(binDeviceType, new_id);
      });
      $('.b-container-card-previous').css('visibility','visible').on('click', function () {
        var new_id = undefined;
        if (currentCard[1] === currentStation.master) {
          new_id = currentStation.satellites[currentStation.satellites.length - 1];
        }
        else {
          var currentIndex = currentStation.satellites.indexOf(currentCard[1]);
          new_id = currentIndex === 0 ? currentStation.master : currentStation.satellites[currentIndex - 1];
        }
        initActiveCard(binDeviceType, new_id);
      });
    }

    var addToRouteLink = $('#b-container-card').find('a.add-to-route');
    if (typeof maxContainersSelected === 'function' && maxContainersSelected()) {
      addToRouteLink.parent().remove();
    } else {
      addToRouteLink.on('click', function () {
        pickContainers([id]);
      });
    }
  });
}

function getSensorCard(id) {
  $.get('/settings/sensors/' + id + '/map-card/', function (data) {
    refreshCardContent(data);
  });
}

function getDeviceCard(deviceInfo) {
  if (deviceInfo[0] === binDeviceType) {
    getContainerCard(deviceInfo[1]);
  } else if (deviceInfo[0] === sensorDeviceType) {
    getSensorCard(deviceInfo[1]);
  } else {
    console.warn("Unsupported device type: ", deviceInfo[0]);
  }
}

function initActiveCard(deviceType, deviceId) {
  // It's assumed that device type & id is always defined.
  updateCurrentCard([deviceType, deviceId]);
  stopIntervalEvents();
  intervalEvents.push(setInterval(function () {
    getDeviceCard(currentCard);
  }, cardRefreshInterval));
  getDeviceCard(currentCard);
}

function initCards(refreshCallback) {
  deviceRefreshCallback = refreshCallback;
}

function getCurrentCard() {
  return currentCard;
}

function setCurrentStation(station) {
  currentStation = station;
}
