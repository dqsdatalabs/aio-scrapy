import re
from urllib.parse import unquote
import logging

from scrapy import Request
from aioscrapy.spiders import AioSpider

logger = logging.getLogger(__name__)


class DemoScrapySpider(AioSpider):
    name = 'DemoScrapy'
    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36",
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1,

        # 使用scrapy的调度
        'SCHEDULER': 'scrapy.core.scheduler.Scheduler',
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.RFPDupeFilter',
    }

    start_urls = ['https://hanyu.baidu.com/zici/s?wd=王&query=王']

    def parse(self, response):
        img_url = response.xpath('//img[@class="bishun"]/@data-gif').get()
        chinese_character = re.search('wd=(.*?)&', response.url).group(1)
        item = {
            'img_url': img_url,
            'response_url': response.url,
            'chinese_character': unquote(chinese_character)
        }
        yield item
        new_character = response.xpath('//a[@class="img-link"]/@href').getall()
        for character in new_character:
            new_url = 'https://hanyu.baidu.com/zici' + character
            yield Request(new_url, callback=self.parse, dont_filter=True)

    def spider_idle(self):
        """跑完关闭爬虫"""


if __name__ == '__main__':
    DemoScrapySpider.start()
