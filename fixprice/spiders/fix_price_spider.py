import time
import re

import scrapy

from fixprice.items import FixPriceItem


class FixPriceSpider(scrapy.Spider):
    name = 'fixprice'
    custom_settings = {
        'ITEM_PIPELINES': {
            'fixprice.pipelines.FixPricePipeline': 300,
        }
    }

    def __init__(self, categories=None, region_id='512', *args, **kwargs):
        super().__init__(*args, **kwargs)
        if categories:
            self.start_urls = [url.strip() for url in categories.split(',')]
        else:
            self.start_urls = []
        self.region_id = region_id

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                cookies={'region_id': self.region_id},
                dont_filter=True
            )

    def parse_category(self, response):
        links = response.css('a::attr(href)').getall()
        product_paths = [l for l in links if '/catalog/' in l and '/p-' in l]
        for path in product_paths:
            yield response.follow(
                path,
                callback=self.parse_product,
                cookies={'region_id': self.region_id}
            )

        current_page = 1
        if 'page=' in response.url:
            try:
                current_page = int(response.url.split('page=')[-1])
            except ValueError:
                current_page = 1

        MAX_PAGES = 3
        if current_page < MAX_PAGES:
            base = response.url.split('?')[0]
            next_page = f"{base}?page={current_page + 1}"
            yield scrapy.Request(
                next_page,
                callback=self.parse_category,
                cookies={'region_id': self.region_id}
            )

    def parse_product(self, response):
        item = FixPriceItem()
        item['timestamp'] = int(time.time())

        item['RPC'] = (
            response
            .css('div.additional-information span.value::text')
            .get(default='')
            .strip()
        )

        title = response.css('div[itemtype="http://schema.org/Product"] h1.title::text') \
            .get(default='').strip()
        item['title'] = title

        item['marketing_tags'] = response.css('div.sticker span::text').getall()

        crumbs = response.css(
            'div[itemtype="http://schema.org/BreadcrumbList"] '
            'span[itemprop="name"]::text'
        ).getall()
        item['section'] = [c.strip() for c in crumbs[1:] if c.strip()]

        offer = response.css('div[itemprop="offers"]')
        price_meta = offer.css('meta[itemprop="price"]::attr(content)').get()
        availability = offer.css('meta[itemprop="availability"]::attr(content)').get()

        original = float(price_meta) if price_meta else 0.0

        script = response.xpath(
            '//script[contains(., "window.__NUXT__")]/text()'
        ).get()

        m = re.search(r'specialPrice\s*:\s*\{[^}]*price:"(?P<price>\d+)"', script)
        if m:
            price = float(m.group('price'))
        else:
            price = 0.0

        item['price_data'] = {
            'current': price,
            'original': original,
            'sale_tag': ''  # Вычисляется в pipeline
        }

        item['stock'] = {
            'in_stock': bool(availability and availability.endswith('InStock')),
            'count': 0
        }

        all_imgs = response.css('div.gallery img')
        images = all_imgs.xpath('@src | @data-src').getall()
        thumbs = response.css('div.gallery-thumbs img').xpath('@src | @data-src').getall()
        set_images = []
        for url in images + thumbs:
            if url and url not in set_images:
                set_images.append(response.urljoin(url))

        view360 = response.css('div.view360 img').xpath('@src | @data-src').getall()
        view360 = [response.urljoin(u) for u in view360 if u]

        videos = response.css('video source::attr(src)').getall()
        videos = [response.urljoin(u) for u in videos if u]

        item['assets'] = {
            'main_image': set_images[0] if set_images else '',
            'set_images': set_images,
            'view360': view360,
            'video': videos
        }

        metadata = {}
        metadata['__description'] = response.css(
            'div[itemtype="http://schema.org/Product"] '
            'meta[itemprop="description"]::attr(content)'
        ).get(default='').strip()

        for prop in response.css('div.properties-block p.property'):
            key = prop.css('span.title::text').get(default='').strip().rstrip(':')
            val = ''.join(prop.css('span.value *::text').getall()).strip()
            if not val:
                val = prop.css('span.value::text').get(default='').strip()
            if key:
                metadata[key] = val

        if 'Бренд' in metadata and metadata['Бренд']:
            item['brand'] = metadata['Бренд']
        else:
            parts = [p.strip() for p in title.split(',')]
            item['brand'] = parts[1] if len(parts) > 1 else ''

        item['metadata'] = metadata


        variants = response.css('ul.product-variants li::attr(data-variant)').getall()
        item['variants'] = len(variants)
        item['url'] = response.url

        yield item
