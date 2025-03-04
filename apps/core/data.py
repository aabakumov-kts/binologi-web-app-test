class Fullness(object):
    __collection = []
    css_class = ''
    card_class = ''
    lower = 0
    marker_color = ''
    title = ''
    upper = 0

    def __init__(self, title, lower, upper, css_class, marker_color,
                 card_class):
        self.title = title
        self.lower, self.upper = lower, upper
        self.css_class, self.marker_color = css_class, marker_color
        self.card_class = card_class
        self.__collection.append(self)

    def __repr__(self):
        return '<Fullness: %s (%s, %s)>' % (self.title, self.lower, self.upper)

    def in_range(self, value):
        return self.lower <= value <= self.upper

    @classmethod
    def get_member(cls, value):
        for member in cls.__collection:
            if member.in_range(value):
                return member

    @classmethod
    def get_marker_color(cls, value):
        member = cls.get_member(value)
        return member.marker_color

    @classmethod
    def get_css_class(cls, value):
        member = cls.get_member(value)
        return member.css_class

    @classmethod
    def get_title(cls, value):
        member = cls.get_member(value)
        return member.title

    @classmethod
    def get_card_class(cls, value):
        member = cls.get_member(value)
        return member.card_class


FULLNESS = [
    Fullness('0', 0, 49, 'b-filter-0', '#1ea51b', 'green'),
    Fullness('50', 50, 74, 'b-filter-50', '#ffe400', 'yellow'),
    Fullness('75', 75, 89, 'b-filter-75', '#ff7200', 'orange'),
    Fullness('90', 90, 300, 'b-filter-90', '#ff0000', 'red'),
]


def get_battery_card_class(value):
    cls = 'green'
    if value < 70:
        cls = 'yellow'
    if value < 35:
        cls = 'red'
    return cls
