from modeltranslation.translator import TranslationOptions, register

from apps.core.models import Country, City, WasteType


@register(Country)
class CountryTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(City)
class CityTranslationOptions(TranslationOptions):
    fields = ('title',)


@register(WasteType)
class WasteTypeTranslationOptions(TranslationOptions):
    fields = ('title',)
