def split_value_among_segments(value, segments, set_segment_value, clip_peak=True):
    if len(segments) == 0:
        raise ValueError('Segments should be non-empty iterable')
    if set_segment_value is None or not callable(set_segment_value):
        raise ValueError('set_segment_value should be defined callable')

    effective_value = value
    try:
        segment_index = next(index for index, limit in enumerate(segments) if value < limit)
    except StopIteration:
        # This means value is higher than the upper segment limit
        segment_index = len(segments) - 1
        effective_value = segments[segment_index] if clip_peak else value

    i = 0
    while i <= segment_index:
        previous_segment_limit = segments[i - 1] if i > 0 else 0
        current_segment_value = effective_value if i == segment_index else segments[i]
        set_segment_value(i, current_segment_value - previous_segment_limit)
        i += 1

    i = segment_index + 1
    while i < len(segments):
        set_segment_value(i, None)
        i += 1


notification_subject_generators = {}

notification_message_generators = {}

notification_link_generators = {}
