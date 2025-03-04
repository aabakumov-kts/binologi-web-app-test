from modeltranslation.translator import TranslationOptions, register

from app.models import ContainerType, Equipment, ErrorType


@register(ContainerType)
class ContainerTypeTranslationOptions(TranslationOptions):
    fields = ('title', 'description')


@register(Equipment)
class EquipmentTranslationOptions(TranslationOptions):
    fields = ('title',)


@register(ErrorType)
class ErrorTypeTranslationOptions(TranslationOptions):
    fields = ('title',)
