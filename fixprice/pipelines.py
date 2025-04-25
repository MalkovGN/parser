# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

import time

class FixPricePipeline:
    def process_item(self, item, spider):
        # Add current timestamp
        item['timestamp'] = int(time.time())
        # Compute sale tag if discount exists
        current = item['price_data'].get('current', item['price_data'].get('original', 0))
        original = item['price_data'].get('original', current)
        if original and current < original:
            discount = round((original - current) / original * 100)
            item['price_data']['sale_tag'] = f'Скидка {discount}%'
        else:
            item['price_data']['sale_tag'] = ''
        return item


class FixpricePipeline:
    def process_item(self, item, spider):
        return item
