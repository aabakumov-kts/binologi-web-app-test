from django import forms
from django.conf import settings
from django.forms.utils import flatatt
from django.forms.widgets import Input
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.text import capfirst
from django.utils.translation import get_language, ugettext_lazy as _


class PointInput(Input):
    input_type = 'text'

    def __init__(self, attrs=None):
        if attrs is not None:
            self.input_type = attrs.pop('type', self.input_type)
        super().__init__(attrs)

    def render(self, name, value, attrs=None, **kwargs):
        if value is None:
            value = ''
        final_attrs = self.build_attrs(attrs, {'type': self.input_type, 'name': name})
        if value != '':
            # Only add the 'value' attribute if a value is non-empty.
            final_attrs['value'] = force_text(value)
        return format_html(
            '<div><input{} style="display: none"/>{}:<input type="text" id="{}_lat">&nbsp;{}:'
            '<input type="text" id="{}_lon"><div class="widgetpoint" id="map_{}"></div>'
            '<script>$(document).ready(function() {{ widgetpoint("{}"); }});</script></div>',
            flatatt(final_attrs), _('latitude'), final_attrs['id'], _('longitude'), final_attrs['id'],
            final_attrs['id'], final_attrs['id'])

    @property
    def media(self):
        return forms.Media(css={'all': ('/static/css/widgetpoint.css',)},
                           js=('https://maps.googleapis.com/maps/api/js?key={}&language={}'.format(
                                   settings.GOOGLE_MAPS_API_KEY, get_language()),
                               '/static/js/widgetpoint.js',))


class CityWidget(forms.TextInput):
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        if 'placeholder' not in attrs:
            attrs['placeholder'] = capfirst(_('start to type city then select it from the dropdown if present'))
        super().__init__(attrs)

    class Media:
        js = (
            'external/jquery/dist/jquery.min.js',
            'js/city-datalist.js',
            'js/city-widget.js',
        )

    def render(self, name, value, attrs=None, **kwargs):
        html = super().render(name, value, attrs)
        html += '<datalist id="id_city_list"></datalist>'
        return html

    def build_attrs(self, base_attrs, extra_attrs=None):
        extra = dict(list='id_city_list', autocomplete='off')
        if extra_attrs:
            extra_attrs.update(extra)
        else:
            extra_attrs = extra
        return super().build_attrs(base_attrs, extra_attrs)
