$(document).ready(function () {
  function showAccountInfoModal(event) {
    event.preventDefault();
    $('#accountModal').modal();
    $.get('/account/info/', function (data) {
        $('#accountModal .modal-body').html(data);
    });
  }

  $('.b-userinfo-icon').on('click', showAccountInfoModal);
  $('.b-userinfo-name').on('click', showAccountInfoModal);
  $('.b-userinfo-role').on('click', showAccountInfoModal);
  $('.invalid-license-page .show-account-modal').on('click', showAccountInfoModal);
});
