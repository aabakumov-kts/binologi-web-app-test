from datetime import date
from django.contrib.gis.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from apps.core.models import Company
from app.models import Container


class CompanyTrashbinsLicense(models.Model):
    company = models.ForeignKey(Company, verbose_name=_('company'), on_delete=models.CASCADE)
    begin = models.DateField(verbose_name=_('period begin'), default=date.today)
    end = models.DateField(verbose_name=_('period end'))
    description = models.CharField(max_length=256, blank=True)

    @property
    def is_valid(self):
        return self.begin <= date.today() <= self.end


class TrashReceiverStatistic(models.Model):
    trashbin = models.ForeignKey(Container, related_name='trash_recv_stats', on_delete=models.CASCADE)
    ctime = models.DateTimeField(default=timezone.now)
    open_count = models.IntegerField(default=0)
    actual = models.BooleanField(default=False, verbose_name=_('actual data'))

    class Meta:
        ordering = ('ctime',)

    def __str__(self):
        return '%s %s %s' % (self.trashbin, self.open_count, self.ctime)
