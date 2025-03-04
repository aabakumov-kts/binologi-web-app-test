$(document).ready(function () {
    function onManageWebPushSubscriptionButtonClicked(event) {
        var closeModalButtonSelector = "#notificationsSubscriptionModal button.close";
        getSubscriptionState().then(function(state) {
            if (state.isPushEnabled) {
                /* Subscribed, opt them out */
                OneSignal.setSubscription(false);
            } else {
                if (state.isOptedOut) {
                    /* Opted out, opt them back in */
                    OneSignal.setSubscription(true);
                } else {
                    /* Unsubscribed, subscribe them */
                    OneSignal.registerForPushNotifications();
                }
                var closeButton = document.querySelector(closeModalButtonSelector);
                if (closeButton !== null) closeButton.click();
            }
        });
        event.preventDefault();
    }

    function updateMangeWebPushSubscriptionButton() {
        var subscribeButtonSelector = "#subscribe-button";
        var unsubscribeButtonSelector = "#unsubscribe-button";

        getSubscriptionState().then(function(state) {
            var showSubscribeButton = !state.isPushEnabled || state.isOptedOut;

            var subscribeButton = document.querySelector(subscribeButtonSelector);
            if (subscribeButton !== null) {
                subscribeButton.removeEventListener('click', onManageWebPushSubscriptionButtonClicked);
                if (showSubscribeButton) {
                    subscribeButton.addEventListener('click', onManageWebPushSubscriptionButtonClicked);
                    subscribeButton.style.display = "";
                    if (autoShowSubscriptionModal) $('#notificationsSubscriptionModal').modal();
                } else {
                    subscribeButton.style.display = "none";
                }
            }

            var unsubscribeButton = document.querySelector(unsubscribeButtonSelector);
            if (unsubscribeButton !== null) {
                unsubscribeButton.removeEventListener('click', onManageWebPushSubscriptionButtonClicked);
                if (showSubscribeButton) {
                    unsubscribeButton.style.display = "none";
                } else {
                    unsubscribeButton.addEventListener('click', onManageWebPushSubscriptionButtonClicked);
                    unsubscribeButton.style.display = "";
                }
            }
        });
    }

    function getSubscriptionState() {
      return Promise.all([
        OneSignal.isPushNotificationsEnabled(),
        OneSignal.isOptedOut()
      ]).then(function(result) {
          var isPushEnabled = result[0];
          var isOptedOut = result[1];

          return {
              isPushEnabled: isPushEnabled,
              isOptedOut: isOptedOut
          };
      }).catch(function(err) {
        console.warn("Get subscription state error", err);
      });
    }

    window.OneSignal = window.OneSignal || [];

    /* This example assumes you've already initialized OneSignal */
    OneSignal.push(function() {
        // If we're on an unsupported browser, do nothing
        if (!OneSignal.isPushNotificationsSupported()) {
            return;
        }
        updateMangeWebPushSubscriptionButton();
        OneSignal.on("subscriptionChange", function(isSubscribed) {
            /* If the user's subscription state changes during the page's session, update the button text */
            updateMangeWebPushSubscriptionButton();
        });
    });

    $('button.open-push-subscription').on('click',function() {
        $('#notificationsSubscriptionModal').modal();
    });
});
