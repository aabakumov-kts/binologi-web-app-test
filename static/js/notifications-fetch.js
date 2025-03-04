$(document).ready(function () {
  var notificationsWs = new WebSocket(realtimeApiRootUrl + '/ws/notifications/' + realtimeApiAuthToken);
  notificationsWs.onmessage = function(msg) {
    var payload = JSON.parse(msg.data);
    var valueToRender = payload.unread_notifications_count > 9 ? '9+' : payload.unread_notifications_count.toString();
    $("#headerOpenNotificationsButton span").html(valueToRender).css("display", "");
    $("#mobileOpenNotificationsButton span").html(valueToRender).css("display", "");
    $("#headerOpenNotificationsButton").toggleClass("animate");
    $("#mobileOpenNotificationsButton").toggleClass("animate");
    setTimeout(() => {
      $("#headerOpenNotificationsButton").toggleClass("animate");
      $("#mobileOpenNotificationsButton").toggleClass("animate");
    }, 500);
  }
});
