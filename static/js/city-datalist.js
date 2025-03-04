function updateDatalist(datalistId, country, options, loadCallback) {
    var datalist = $(datalistId);
    $.get('/api/cities/' + country + '/', function (data) {
        var datalistValues = [];
        if (options.addEmptyOption) datalistValues.push($('<option/>'));
        data.forEach(function (item) {
            var value = $('<option/>');
            if (options.useTitleAsValue)
                value.attr('value', item.title);
            else
                value.attr('value', item.id).text(item.title);
            datalistValues.push(value);
        });
        datalist.html(datalistValues);
        if (loadCallback) loadCallback();
    });
}

function initCityDataList(countrySelectId, citySelectId, cityDatalistId, options = {}) {
    if (options.addEmptyOption === undefined) options.addEmptyOption = true;
    var country = $(countrySelectId);
    var city = $(citySelectId);
    var initialLoadCallback = options.initialLoadCallback;
    if (initialLoadCallback) delete options.initialLoadCallback;
    $(country).on('change', function (e) {
        city.val('');
        if (country.val()) updateDatalist(cityDatalistId, country.val(), options);
        city.prop('disabled', !country.val());
    });
    if (country.val()) updateDatalist(cityDatalistId, country.val(), options, initialLoadCallback);
    city.prop('disabled', !country.val());
}
