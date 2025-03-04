/* global Vue */
"use strict";

Vue.http.headers.common['X-CSRFToken'] = document.querySelector('#token').getAttribute('value');

function parseJsonScript(id) {
    return JSON.parse(document.getElementById(id).textContent);
}

var App = Vue.extend({
    template: '#app-template',
    props: [
        'containerTypes',
        'mountTypes',
        'sensorAlreadyRegistered',
        'sensorAvailable',
        'userAuthenticated',
        'wasteTypes',
    ],
    data: function () {
        return {
            containerTypeSelected: undefined,
            mountTypeSelected: undefined,
            isLoading: false,
            sendFailed: false,
            step: 0,
            wasteTypeSelected: undefined,
        }
    },
    methods: {
        contactSupport: function () {
            FreshworksWidget('open', 'ticketForm');
        },
        isStep: function (step) {
            return this.step === step;
        },
        setStep: function (step) {
            this.step = step;
        },
        registerSensor: function() {
            this.isLoading = true;
            this.sendFailed = false;
            var self = this;

            this.$http.post(window.location.toString(), {
                container_type: this.containerTypeSelected,
                mount_type: this.mountTypeSelected,
                waste_type: this.wasteTypeSelected,
            }).then(function (res) {
                self.isLoading = false;
                self.setStep(2);
            }).catch(function (res) {
                self.isLoading = false;
                console.warn("Error registering sensor", res);
                self.sendFailed = true;
            });
        },
    },
    mounted: function () {
        if (this.containerTypes.length > 0) this.containerTypeSelected = this.containerTypes[0].id;
        if (this.mountTypes.length > 0) this.mountTypeSelected = this.mountTypes[0].id;
        if (this.wasteTypes.length > 0) this.wasteTypeSelected = this.wasteTypes[0].id;
    },
});

Vue.component('app', App);

new Vue({
    el: '#onboardSensorAppContainer',
    data: {
        containerTypes: parseJsonScript('container-types'),
        mountTypes: parseJsonScript('mount-types'),
        wasteTypes: parseJsonScript('waste-types'),
    },
});
