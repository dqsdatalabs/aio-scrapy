import asyncio

from scrapy import signals
from scrapy.exceptions import DontCloseSpider
from scrapy.spiders import Spider, CrawlSpider

from aioscrapy.settings import aio_settings

__all__ = ["AioSpider", "AioCrawlSpider"]


class ExtensionMixin:

    @classmethod
    def start(cls):
        from aioscrapy.crawler import Crawler
        import sys
        from scrapy.utils.log import configure_logging
        crawler = Crawler(cls)
        configure_logging(crawler.settings)

        if not sys.platform.startswith('win'):
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        asyncio.run(crawler.crawl())

    @classmethod
    def update_settings(cls, settings):
        settings.setmodule(aio_settings, priority='default')
        if (property_settings := getattr(cls, 'property_settings', None)) is not None:
            settings.setmodule(property_settings)
        settings.setdict(cls.custom_settings or {}, priority='spider')

    def spider_idle(self):
        raise DontCloseSpider


class AioSpider(ExtensionMixin, Spider):
    def _set_crawler(self, crawler):
        super()._set_crawler(crawler)
        crawler.signals.connect(self.spider_idle, signal=signals.spider_idle)


class AioCrawlSpider(ExtensionMixin, CrawlSpider):
    def _set_crawler(self, crawler):
        super()._set_crawler(crawler)
        crawler.signals.connect(self.spider_idle, signal=signals.spider_idle)