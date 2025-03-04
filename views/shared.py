from apps.core.reports import BaseChartView as CoreBaseChartView, BaseReportDatatableView as CoreBaseReportDatatableView

# Following imports are a shortcut to avoid existing reports overhauling
from apps.core.reports import check_report_access  # noqa: F401
from apps.core.reports import filter_queryset_by_date_range  # noqa: F401
from apps.core.reports import fill_stacked_chart_datasets  # noqa: F401
from apps.core.reports import COMMON_STACKED_LINE_CHART_SETTINGS  # noqa: F401
from apps.core.reports import calculate_line_chart_max_height  # noqa: F401
from apps.core.reports import default_render_column  # noqa: F401
from apps.core.reports import TIMESINCE_STRINGS  # noqa: F401
from apps.core.reports import filter_columns  # noqa: F401
from apps.core.reports import underline_columns  # noqa: F401
from apps.trashbins.reports.shared import collect_trashbin_request_context as collect_common_request_context  # noqa: F401
from apps.trashbins.reports.shared import common_filter_trashbin_queryset as common_filter_queryset  # noqa: F401
from apps.core.reports import COMMON_PIE_CHART_SETTINGS  # noqa: F401
from apps.core.reports import COMMON_LINE_CHART_SETTINGS  # noqa: F401


# This class should be removed in favor of CoreBaseReportDatatableView
class BaseReportDatatableView(CoreBaseReportDatatableView):
    def filter_queryset(self, qs):
        qs = common_filter_queryset(qs, self.request.GET, self.get_filter_qs_options())
        qs = qs.order_by('-ctime')
        return qs


# This class should be removed in favor of CoreBaseChartView
class BaseChartView(CoreBaseChartView):
    def filter_queryset(self, qs):
        return common_filter_queryset(qs, self.request.GET, self.get_filter_qs_options())
