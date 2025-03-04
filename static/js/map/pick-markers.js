"use strict";
var vueApp;
var onViewMarker;

function pickContainers(ids) {
  vueApp.addContainers(_.chain(ids)
    .map(findCurrentDataContainerById)
    .filter(function(c) { return !!c; })
    .map(function(c) {
       return {
         'id': c.id,
         'serial': c.serial_number,
         'latLng': new google.maps.LatLng(c.location.y, c.location.x),
       };
    })
    .value());
}

function getMarkerDragListeners(marker) {
  var currentPos;
  var dragStart = function() {
    currentPos = marker.getPosition();
    vueApp.onDragStart();
  };
  var dragEnd = function() {
    var markerPos = pointToScreen(marker.getMap(), marker.getPosition());
    if (currentPos) marker.setPosition(currentPos);
    var boundingRect = $('#binPickerDiv')[0].getBoundingClientRect();
    var draggedInside = boundingRect.left < markerPos.x && markerPos.x < boundingRect.right &&
      boundingRect.top < markerPos.y && markerPos.y < boundingRect.bottom;
    if (draggedInside) {
      var containerIds = [];
      if (!!marker.container) containerIds.push(marker.container.id);
      if (!!marker.station) {
        containerIds.push(marker.station.master);
        marker.station.satellites.forEach(function(id) { containerIds.push(id); });
      }
      pickContainers(containerIds);
    }
    vueApp.onDragEnd();
  };
  return [ dragStart, dragEnd ];
}

function maxContainersSelected() {
  return vueApp.containers.length >= vueApp.maxContainers;
}

var vueAppCfg = {
    el: '#binPickerDiv',
    data: {
      collapsed: true,
      expanded: false,
      expectingDragDrop: false,
      containers: [],
      selectedBin: undefined,
    },
    computed: {
      maxContainers: function() {
        return 10;
      },
    },
    watch: {
      'containers': function() {
        this.selectedBin = undefined;
        if (this.containers.length > 0 && this.collapsed) this.collapsed = false;
        if (this.containers.length === 0 && !this.collapsed) this.collapsed = true;
      }
    },
    methods: {
      onDragStart: function() {
        if (this.containers.length === 0) this.collapsed = false;
        this.expectingDragDrop = true;
        this.expanded = true;
      },
      addContainers: function(containers) {
        var self = this;
        var containersToAdd = _.filter(containers, function (cta) {
          return !_.find(self.containers, function (c) { return c.id === cta.id });
        });
        containersToAdd = _.slice(containersToAdd, 0, Math.max(this.maxContainers - this.containers.length, 0));
        containersToAdd.forEach(function(c) { self.containers.push(c); });
      },
      onDragEnd: function() {
        this.expectingDragDrop = false;
        if (this.containers.length === 0) {
          this.expanded = false;
          this.collapsed = true;
        }
      },
      selectBin: function(bin) {
        this.selectedBin = bin;
      },
      removeSelected: function() {
        var idToRemove = this.selectedBin.id;
        this.containers = _.filter(this.containers, function(v) { return idToRemove !== v.id; });
      },
      removeAll: function() {
        this.containers = [];
        this.expanded = false;
      },
      closeBinsList: function() {
        this.selectedBin = undefined;
        this.expanded = false;
        if (this.containers.length === 0) this.collapsed = true;
      },
      viewSelected: function() {
        onViewMarker(this.selectedBin.latLng);
      },
    }
};

function initPickMarkers(viewMarker) {
  $('#binPickerDiv').show();
  onViewMarker = viewMarker;
  vueApp = new Vue(vueAppCfg);
}

function getPickedBinsSerials() {
  return _.map(vueApp.containers, function(c) { return c.serial; });
}
