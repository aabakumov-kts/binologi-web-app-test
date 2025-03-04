from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _

from apps.core.models import WasteType
from app.models import ErrorType, Equipment, FullnessValues, Collection, Container
from apps.core.views import BaseCreateRouteView, BaseFullnessForecastView


class CreateRouteView(BaseCreateRouteView):
    template_name = 'trashbins/routes/create.html'

    def get_error_types(self):
        return ErrorType.objects.order_by('equipment__id')\
            .values('id', 'title', 'equipment__title', 'equipment__id')

    def get_route_point_attributes(self, json_point):
        return {
            'container_id': json_point['id'],
        }

    def get_render_context(self):
        waste_types = list(WasteType.objects.values())
        equipment = Equipment.objects.order_by('id').values('id', 'title')
        return {
            'fetch_sensors': False,
            'points_templates_prefix': 'trashbins',
            'waste_types': waste_types,
            'equipment': equipment,
        }


class TrashbinFullnessForecastView(BaseFullnessForecastView):
    def get_context_data(self, **kwargs):
        result = super().get_context_data(**kwargs)

        trashbin = get_object_or_404(Container, pk=kwargs.get('pk'))
        result['device_serial'] = trashbin.serial_number
        if trashbin.fullness >= 90:
            result[self.ERROR_MESSAGE_CONTEXT_KEY] =\
                _("SmartCity Bin has fullness over 90 percent already, there's nothing to forecast at the moment")
            return result

        last_3_collections = Collection.objects.filter(container=trashbin).order_by('-ctime')[:3]
        if last_3_collections.count() < 3:
            result[self.ERROR_MESSAGE_CONTEXT_KEY] = \
                _("There's not enough collections of this SmartCity Bin yet, can't forecast at the moment")
            return result

        fullness_range_latest = FullnessValues.objects\
            .filter(container=trashbin, ctime__gt=last_3_collections[0].ctime)\
            .order_by('-ctime') \
            .extra({'day': "date_trunc('day', app_fullness.ctime)::date", 'value': 'fullness_value'})\
            .values('day', 'value')[0:15]
        if fullness_range_latest.count() == 0:
            result[self.ERROR_MESSAGE_CONTEXT_KEY] = \
                _("There's was no fullness measurements of this SmartCity Bin after the last collection, "
                  "can't forecast at the moment")
            return result

        result[self.FULLNESS_RANGE_LATEST_CONTEXT_KEY] = list(reversed(fullness_range_latest))
        result[self.FULLNESS_RANGES_COLLECTION_CONTEXT_KEY] = [
            self._get_fullness_range_for_dataframe(trashbin, last_3_collections[1].ctime, last_3_collections[0].ctime),
            self._get_fullness_range_for_dataframe(trashbin, last_3_collections[2].ctime, last_3_collections[1].ctime),
        ]
        if any((len(rng) < 2 for rng in result[self.FULLNESS_RANGES_COLLECTION_CONTEXT_KEY])):
            result[self.ERROR_MESSAGE_CONTEXT_KEY] = \
                _("There's was not enough fullness measurements between latest collections of this SmartCity Bin, "
                  "can't forecast at the moment")
            return result

        return result

    def _get_fullness_range_for_dataframe(self, trashbin, ctime_begin, ctime_end):
        qs = FullnessValues.objects\
            .filter(container=trashbin, ctime__lte=ctime_end, ctime__gt=ctime_begin)\
            .values('ctime', 'fullness_value')
        return list(map(
            lambda f: {'ds': f['ctime'].strftime(self.dataframe_datetime_format), 'y': f['fullness_value']}, qs))
