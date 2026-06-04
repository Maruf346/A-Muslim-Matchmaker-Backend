from rest_framework.pagination import PageNumberPagination

class FlexiblePageNumberPagination(PageNumberPagination):
    page_size = 8                     # default
    page_size_query_param = 'page_size'   # allows ?page_size=20
    max_page_size = 600               # cap to prevent abuse