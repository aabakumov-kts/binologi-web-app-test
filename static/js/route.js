"use strict";

Vue.http.headers.common['X-CSRFToken'] = document.querySelector('#token').getAttribute('value');
Vue.http.options.emulateHTTP = true;

var eventHub = new Vue();

var stepMixin = {
    created: function () {
        eventHub.$on('step', this.onStep);
    },
    beforeDestroy: function () {
        eventHub.$off('step', this.onStep);
    },
    methods: {
        isStep: function (step) {
            return this.step === step;
        },
        setStep: function (step) {
            this.step = step;
            eventHub.$emit('step', step);
        },
        onStep: function (step) {
            this.step = step;
        },
    },
};

var Points = Vue.extend({
    mixins: [stepMixin],
    props: ['sectors'],
    data: function () {
        return {
            filtered: [],
            heap: [],
            waste: wasteTypesSelected,
            fullness: fullnessSelected,
            errors: errorTypesSelected,
            selected: 0,
            step: 0,
            bounds: mapBounds,
            applyBounds: binSerials.length === 0,
            serials: binSerials,
            applySerials: true,
            sectorsToFilterBy: sectorsSelected,
            applySectorsFilter: binSerials.length === 0,
        }
    },
    computed: {
        boundsSpecified: function () {
            return Object.keys(this.bounds).length === 4;
        },
        serialsSpecified: function () {
            return this.serials.length > 0;
        },
        sectorsFilterSpecified: function () {
            return this.sectorsToFilterBy.length > 0;
        },
    },
    template: '#points-template',
    mounted: function () {
        this.doFilter();
    },
    watch: {
        'waste': function () {
            this.doFilter();
        },
        'fullness': function () {
            this.doFilter();
        },
        'errors': function () {
            this.doFilter();
        },
        'filtered': function() {
            eventHub.$emit('sectors', this.getSectors());
            eventHub.$emit('points', this.filtered);
        },
        'applyBounds': function() {
            this.doFilter();
        },
        'applySerials': function() {
            this.doFilter();
        },
        'applySectorsFilter': function() {
            this.doFilter();
        },
    },
    methods: {
        doFilter: function() {
            var filters = jQuery.param({
                'waste_type': this.waste,
                'fullness': this.fullness,
                'error_type': this.errors,
            }, true);
            var query = filters +
                (this.boundsSpecified && this.applyBounds ? '&' + jQuery.param(this.bounds) : '') +
                (this.serialsSpecified && this.applySerials ? '&' + jQuery.param({'serial': this.serials}, true) : '') +
                (this.sectorsFilterSpecified && this.applySectorsFilter ? '&' + jQuery.param({'sector': this.sectorsToFilterBy}, true) : '');
            var url = fetchSensors ? '/api/sensors/?' : '/api/containers/?';
            this.$http.get(url + query).then(function (response) {
                this.filtered = fetchSensors ? response.data.sensors : response.data.containers;
                this.heap = [];
                this.updateSelected();
            });
        },
        updateSelected: function () {
            this.selected = this.heap.length - 1;
        },
        add: function () {
            if (this.heap.length) {
                this.filtered.push(this.heap.splice(this.selected, 1)[0]);
                this.updateSelected();
            }
        },
        remove: function (index) {
            this.heap.push(this.filtered.splice(index, 1)[0]);
            this.updateSelected();
        },
        getSectors: function () {
            var sectorIds = jQuery.unique(this.filtered.map(function (item) {
                return item.sector.id;
            }));
            return this.sectors.filter(function (item) {
                return sectorIds.indexOf(item.id) !== -1;
            });
        },
    }
});

var Drivers = Vue.extend({
    mixins: [stepMixin],
    props: ['drivers', 'totalDriversCount'],
    template: '#drivers-template',
    computed: {
        orderedDrivers: function() {
            return _.orderBy(this.drivers, 'name')
        },
        someDriversUnavailable: function() {
            return this.totalDriversCount > this.drivers.length;
        },
        someDriversWithActiveRoutes: function() {
            return _.some(this.drivers, function(d) { return d.active_routes_count > 0; });
        },
    },
    data: function () {
        return {
            selected: [],
            step: 0
        }
    },
    watch: {
        'selected': function (newValue) {
            eventHub.$emit('drivers', newValue);
        }
    },
    methods: {
        getActiveRoutesStatus: function(driver) {
            return driver.active_routes_count > 0 ? yesStr : noStr;
        }
    },
    mounted: function () {
        this.selected = _.filter(this.drivers, function(d) { return d.active_routes_count === 0; });
    },
});

Vue.component('points', Points);
Vue.component('drivers', Drivers);

new Vue({
    mixins: [stepMixin],
    el: '#vue-app-container',
    data: {
        points: [],
        sectors: [],
        drivers: [],
        routes: [],
        step: 0,
        sendFailed: false,
    },
    computed: {
      orderedDrivers: function () {
        return _.orderBy(this.drivers, 'name')
      },
      orderedSectors: function () {
        return _.orderBy(this.sectors, 'name')
      },
      canSendRoutes: function() {
          if (this.routes.length === 0) return false;
          var totalRouteSectors = _.sumBy(this.routes, 'sectors.length');
          return this.sectors.length === totalRouteSectors;
      }
    },
    created: function () {
        eventHub.$on('points', this.onPoints);
        eventHub.$on('sectors', this.onSectors);
        eventHub.$on('drivers', this.onDrivers);
    },
    beforeDestroy: function () {
        eventHub.$off('points', this.onPoints);
        eventHub.$off('sectors', this.onSectors);
        eventHub.$off('drivers', this.onDrivers);
    },
    watch: {
        'sectors': function () {
            this.autoAssignSectors();
            this.createRoutes();
        },
        'drivers': function () {
            this.autoAssignSectors();
            this.createRoutes();
        },
    },
    methods: {
        onPoints: function (points) {
            this.points = points;
        },
        onSectors: function (sectors) {
            this.sectors = sectors.map(function (sector) {
                return {'id': sector.id, 'name': sector.name, 'driver': null};
            });
        },
        onDrivers: function (drivers) {
            this.drivers = drivers;
        },
        bindSector: function (di, si) {
            if (this.sectors[si].driver == null) {
                this.sectors[si].driver = this.drivers[di];
            } else {
                this.sectors[si].driver = null;
            }
            this.createRoutes();
        },
        isBinded: function (si) {
            return this.sectors[si].driver != null;
        },
        isActive: function (di, si) {
            return this.sectors[si].driver === this.drivers[di];
        },
        isHidden: function (di, si) {
            if (this.isActive(di, si)) {
                return false;
            }
            if (this.isBinded(si)) {
                return true;
            }
        },
        createRoutes: function () {
            var sectors = this.sectors;
            var points = this.points;
            this.routes = this.drivers.map(function (driver) {
                var driver_sectors = sectors.filter(function (sector) {
                    return sector.driver === driver;
                }).map(function (sector) {
                    return sector.name;
                });
                var driver_points = points.filter(function (point) {
                    return driver_sectors.indexOf(point.sector.name) !== -1;
                });

                return {
                    'id': driver.id,
                    'name': driver.username,
                    'sectors': driver_sectors,
                    'points': driver_points,
                }
            }).filter(function (route) {
                return route.points.length > 0;
            });
        },
        sendRoutes: function () {
          if (!this.canSendRoutes) return;
          this.sendFailed = false;
          var self = this;
          this.$http.post(window.location.toString(), {data: this.routes})
              .then(function (res) {
                  window.location = !!res.body.returnToUrl ? res.body.returnToUrl : '/routes/list/';
              })
              .catch(function (err) {
                  console.warn("Error sending routes", err);
                  self.sendFailed = true;
              });
        },
        // UX enhancer: if just one driver selected assign all sectors to him/her.
        autoAssignSectors: function() {
            var driverToAssign = this.drivers.length === 1 ? this.drivers[0] : null;
            this.sectors.forEach(function(s) { s.driver = driverToAssign; });
        },
    }
});
