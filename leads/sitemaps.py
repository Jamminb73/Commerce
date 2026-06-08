# leads/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        # These match the 'name' parameters in your urls.py
        return ['home', 'leads_list']

    def location(self, item):
        return reverse(item)
    