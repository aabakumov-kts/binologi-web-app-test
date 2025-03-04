from modeltranslation.translator import TranslationOptions, register

from apps.sensors.models import ErrorType, ContainerType


@register(ErrorType)
class ErrorTypeTranslationOptions(TranslationOptions):
    fields = ('title',)


@register(ContainerType)
class ContainerTypeTranslationOptions(TranslationOptions):
    fields = ('description',)
