var mapCenterStorageKey = "binology:map:center";
var mapZoomStorageKey = "binology:map:zoom";
var reportFiltersStorageKey = "binology:reports:filters";

function getSessionFilters() {
  return sessionStorage.getItem(reportFiltersStorageKey)
    ? JSON.parse(sessionStorage.getItem(reportFiltersStorageKey))
    : {};
}

function setSessionFilters(sessionFilters) {
  sessionStorage.setItem(reportFiltersStorageKey, JSON.stringify(sessionFilters));
}

function getMapCenter() {
  return sessionStorage.getItem(mapCenterStorageKey) ? JSON.parse(sessionStorage.getItem(mapCenterStorageKey)) : undefined;
}

function setMapCenter(mapCenter) {
 sessionStorage.setItem(mapCenterStorageKey, JSON.stringify(mapCenter));
}

function getMapZoomLevel() {
  return sessionStorage.getItem(mapZoomStorageKey) ? parseInt(sessionStorage.getItem(mapZoomStorageKey)) : undefined;
}

function setMapZoomLevel(zoomLevel) {
  sessionStorage.setItem(mapZoomStorageKey, zoomLevel);
}

function cleanupSession() {
  sessionStorage.removeItem(mapCenterStorageKey);
  sessionStorage.removeItem(mapZoomStorageKey);
  sessionStorage.removeItem(reportFiltersStorageKey);
}
