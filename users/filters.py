from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from .models import SubscriptionPlan, User, UserRole


class AdminUserFilterSet(filters.FilterSet):
    role = filters.ChoiceFilter(field_name="role", choices=UserRole.choices)
    gender = filters.CharFilter(method="filter_gender")
    subscription_plan = filters.ChoiceFilter(
        field_name="subscription_plan",
        choices=SubscriptionPlan.choices,
    )
    is_active = filters.BooleanFilter(field_name="is_active")
    is_verified = filters.BooleanFilter(field_name="is_verified")
    date_of_birth = filters.DateFilter(method="filter_date_of_birth")
    age = filters.NumberFilter(method="filter_age")
    sect = filters.CharFilter(method="filter_basic_info_choice")
    city = filters.CharFilter(method="filter_basic_info_text")
    country = filters.CharFilter(method="filter_basic_info_text")
    marital_status = filters.CharFilter(method="filter_basic_info_choice")
    ethnicity = filters.CharFilter(method="filter_basic_info_json")
    nationality = filters.CharFilter(method="filter_basic_info_json")
    has_children = filters.BooleanFilter(method="filter_basic_info_boolean")
    children_count = filters.CharFilter(method="filter_basic_info_choice")
    height = filters.CharFilter(method="filter_basic_info_choice")
    weight = filters.CharFilter(method="filter_basic_info_choice")
    pray_5x = filters.CharFilter(method="filter_basic_info_choice")
    open_to_relocate = filters.CharFilter(method="filter_basic_info_choice")
    how_found = filters.CharFilter(method="filter_how_found")
    employment = filters.CharFilter(method="filter_basic_info_text")
    education = filters.CharFilter(method="filter_basic_info_choice")
    income = filters.CharFilter(method="filter_basic_info_choice")
    frame = filters.CharFilter(method="filter_basic_info_choice")
    languages_spoken = filters.CharFilter(method="filter_basic_info_json")
    pref_age_min = filters.NumberFilter(method="filter_basic_info_number")
    pref_age_max = filters.NumberFilter(method="filter_basic_info_number")
    pref_marital_status = filters.CharFilter(method="filter_basic_info_json")
    pref_ethnicity = filters.CharFilter(method="filter_basic_info_json")
    pref_country_of_residence = filters.CharFilter(method="filter_basic_info_json")
    relationship_with_islam = filters.CharFilter(method="filter_basic_info_text")
    role_as_spouse = filters.CharFilter(method="filter_basic_info_text")
    about_yourself = filters.CharFilter(method="filter_basic_info_text")
    envision_spouse = filters.CharFilter(method="filter_basic_info_text")
    envision_marriage = filters.CharFilter(method="filter_basic_info_text")
    spouse_religious_status_pref = filters.CharFilter(method="filter_basic_info_text")
    open_to_relocate_details = filters.CharFilter(method="filter_basic_info_text")
    other_preferences = filters.CharFilter(method="filter_basic_info_text")
    dress = filters.CharFilter(method="filter_basic_info_choice")
    preferred_dress = filters.CharFilter(method="filter_basic_info_choice")
    about = filters.CharFilter(method="filter_basic_info_text")
    wali_profile_how_found = filters.CharFilter(method="filter_wali_profile_json")
    wali_profile_gender = filters.CharFilter(method="filter_wali_profile_choice")
    wali_profile_relation_to_sister = filters.CharFilter(method="filter_wali_profile_choice")
    wali_profile_phone = filters.CharFilter(method="filter_wali_profile_text")

    class Meta:
        model = User
        fields = [
            "role",
            "gender",
            "subscription_plan",
            "is_active",
            "is_verified",
            "date_of_birth",
            "age",
            "sect",
            "city",
            "country",
            "marital_status",
            "ethnicity",
            "nationality",
            "has_children",
            "children_count",
            "height",
            "weight",
            "pray_5x",
            "open_to_relocate",
            "how_found",
            "employment",
            "education",
            "income",
            "frame",
            "languages_spoken",
            "pref_age_min",
            "pref_age_max",
            "pref_marital_status",
            "pref_ethnicity",
            "pref_country_of_residence",
            "relationship_with_islam",
            "role_as_spouse",
            "about_yourself",
            "envision_spouse",
            "envision_marriage",
            "spouse_religious_status_pref",
            "open_to_relocate_details",
            "other_preferences",
            "dress",
            "preferred_dress",
            "about",
            "wali_profile_how_found",
            "wali_profile_gender",
            "wali_profile_relation_to_sister",
            "wali_profile_phone",
        ]

    @staticmethod
    def _basic_info_relations():
        return ("male_basic_info", "female_basic_info", "wali_basic_info")

    @staticmethod
    def _wali_profile_relation():
        return ("wali_profile",)

    @staticmethod
    def _or_filter(queryset, relations, field, value, lookup="icontains"):
        query = Q()
        for relation in relations:
            query |= Q(**{f"{relation}__{field}__{lookup}": value})
        return queryset.filter(query)

    def filter_gender(self, queryset, name, value):
        value = (value or "").strip().lower()
        if value == "female":
            return queryset.filter(Q(gender="female") | Q(role=UserRole.WALI))
        if value == "male":
            return queryset.filter(gender="male")
        return queryset.filter(gender=value)

    def filter_date_of_birth(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), "date_of_birth", value, lookup="exact")

    def filter_age(self, queryset, name, value):
        try:
            age = int(value)
        except (TypeError, ValueError):
            return queryset

        today = timezone.now().date()

        def _shift_years(base_date, years):
            try:
                return base_date.replace(year=base_date.year - years)
            except ValueError:
                return base_date.replace(month=2, day=28, year=base_date.year - years)

        start = _shift_years(today, age + 1) + timedelta(days=1)
        end = _shift_years(today, age)
        query = Q()
        for relation in self._basic_info_relations():
            query |= Q(**{f"{relation}__date_of_birth__range": (start, end)})
        return queryset.filter(query)

    def filter_basic_info_text(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), name, value, lookup="icontains")

    def filter_basic_info_choice(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), name, value, lookup="iexact")

    def filter_basic_info_number(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), name, value, lookup="exact")

    def filter_basic_info_boolean(self, queryset, name, value):
        query = Q()
        for relation in self._basic_info_relations():
            query |= Q(**{f"{relation}__{name}": value})
        return queryset.filter(query)

    def filter_basic_info_json(self, queryset, name, value):
        return self._or_filter(queryset, self._basic_info_relations(), name, value, lookup="icontains")

    def filter_how_found(self, queryset, name, value):
        relations = self._basic_info_relations() + self._wali_profile_relation()
        return self._or_filter(queryset, relations, "how_found", value, lookup="icontains")

    def filter_wali_profile_text(self, queryset, name, value):
        field = name.replace("wali_profile_", "")
        return self._or_filter(queryset, self._wali_profile_relation(), field, value, lookup="icontains")

    def filter_wali_profile_choice(self, queryset, name, value):
        field = name.replace("wali_profile_", "")
        return self._or_filter(queryset, self._wali_profile_relation(), field, value, lookup="iexact")

    def filter_wali_profile_json(self, queryset, name, value):
        field = name.replace("wali_profile_", "")
        return self._or_filter(queryset, self._wali_profile_relation(), field, value, lookup="icontains")
