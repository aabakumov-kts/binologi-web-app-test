var efMonContainer = $('#efficiency-monitor');
var efMonRefreshIntervalPeriod = 300000;
var efMonRefreshIntervalHandle;

function resetContainer() {
  efMonContainer.html('<p class="closed-monitor">' + efficiencyMonitorCta + '</p>');
  if (efMonRefreshIntervalHandle) {
    clearInterval(efMonRefreshIntervalHandle);
    efMonRefreshIntervalHandle = undefined;
  }
  // setTimeout helps overcome immediate triggering of loadMonitor by the same click
  setTimeout(() => efMonContainer.on('click', loadMonitor), 0);
}

function refreshMonitor(callback) {
  $.get('/tools/efficiency-monitor/', function(data) {
    efMonContainer.html(data);
    efMonContainer.find('span.close-icon').on('click', resetContainer);
    if (typeof callback === 'function') callback();
  });
}

function loadMonitor() {
  efMonContainer.off('click');
  efMonContainer.html('<div class="progress">' +
    '<div class="progress-bar progress-bar-striped active" role="progressbar" aria-valuenow="100" ' +
    'aria-valuemin="0" aria-valuemax="100" style="width: 100%"></div>' +
    '</div>');
  refreshMonitor(function() {
    efMonRefreshIntervalHandle = setInterval(function () {
      refreshMonitor();
    }, efMonRefreshIntervalPeriod);
  });
}

function initEfficiencyMonitor() {
  resetContainer();
  efMonContainer.show();
}
