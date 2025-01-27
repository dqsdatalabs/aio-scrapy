import asyncio
import logging
from aioscrapy.db import get_manager

logger = logging.getLogger(__name__)


class SqlFormat:

    @staticmethod
    def ck_insert(table: str, fields: list, *args) -> str:
        fields = ','.join(fields)
        return f'''INSERT INTO {table} ({fields}) VALUES '''

    @staticmethod
    def mysql_insert(table: str, fields: list, *args) -> str:
        placeholder = ','.join(['%s'] * len(fields))
        fields = ','.join(fields)
        return f'''INSERT INTO {table} ({fields}) VALUES ({placeholder})'''

    @staticmethod
    def mysql_ignore_insert(table: str, fields: list, *args) -> str:
        placeholder = ','.join(['%s'] * len(fields))
        fields = ','.join(fields)
        return f'''INSERT IGNORE INTO {table} ({fields}) VALUES ({placeholder})'''

    @staticmethod
    def mysql_update_insert(table: str, fields: list, update_fields: list, *args) -> str:
        placeholder = ','.join(['%s'] * len(fields))
        if not update_fields:
            update_fields = fields
        update_fields = ','.join([f"{key} = VALUES({key})" for key in update_fields])
        fields = ','.join(fields)
        return f'INSERT INTO {table} ({fields}) VALUES ({placeholder}) ON DUPLICATE KEY UPDATE {update_fields}'

    def __call__(self, *args, db_type='mysql', insert_type='insert'):
        if getattr(self, f'{db_type}_{insert_type}'):
            func = getattr(self, f'{db_type}_{insert_type}')
            return func(*args)
        raise Exception(f"不支持该写入类型： {db_type}_{insert_type}")


get_sql = SqlFormat()


class ItemCache(object):
    def __init__(self, db_type):
        self.db_type = db_type
        self.item_cache = {}
        self.fields_cache = {}
        self.table_cache = {}
        self.insert_sql_cache = {}
        self.db_alias_cache = {}

    def parse_item_to_cache(self, item: dict):
        # 取出要存储的表名
        table_name = item.pop('save_table_name')
        if table_name is None:
            raise Exception('please set save_table_name')

        # 取出要存储的方式
        insert_type = item.pop('save_insert_type', 'insert')

        # 取出要更新的字段
        update_fields = item.pop('save_update_fields', [])

        # 取出要存储的数据库
        save_db_alias = item.pop('save_db_alias', ['default'])
        if isinstance(save_db_alias, str):
            save_db_alias = [save_db_alias]

        # 以item的key值更新方式表名做缓存key
        fields = list(item.keys())
        cache_key = ''.join(fields + update_fields) + insert_type + table_name

        if self.fields_cache.get(cache_key) is None:
            # 缓存要存储的数据库链接别名
            self.db_alias_cache[cache_key] = save_db_alias

            # 缓存要链接的数据库表名
            self.table_cache[cache_key] = table_name

            # 缓存字段
            self.fields_cache[cache_key] = fields

            self.item_cache[cache_key] = []

            # 缓存写入的sql语句
            self.insert_sql_cache[cache_key] = get_sql(table_name, fields, update_fields,
                                                       db_type=self.db_type,
                                                       insert_type=insert_type)

        # 缓存数据
        self.item_cache[cache_key].append([item[field] for field in self.fields_cache[cache_key]])
        return cache_key, len(self.item_cache[cache_key])


class DBPipelineBase:
    def __init__(self, settings, db_type: str):
        self.cache_num = settings.getint('SAVE_CACHE_NUM', 500)
        self.save_cache_interval = settings.getint('SAVE_CACHE_INTERVAL', 10)
        self.db_type = db_type
        self.save_interval_task = None
        self.lock = asyncio.Lock()
        self.cache = ItemCache(db_type)

    async def open_spider(self, spider):
        # 创建数据库链接
        await get_manager(self.db_type).from_crawler(spider)
        self.save_interval_task = asyncio.create_task(self.save_interval(self.save_cache_interval))

    async def process_item(self, item, spider):
        await self.save_item(item)
        return item

    async def close_spider(self, spider):
        self.save_interval_task and self.save_interval_task.cancel()
        await self.close()

    async def close(self, *args, **kwargs):
        async with self.lock:
            for cache_key, items in self.cache.item_cache.items():
                items and await self._save(cache_key)

    async def save_interval(self, interval=10):
        await asyncio.sleep(interval)
        async with self.lock:
            for cache_key, items in self.cache.item_cache.items():
                items and await self._save(cache_key)
        self.save_interval_task = asyncio.create_task(self.save_interval(interval))

    async def save_item(self, item: dict):
        async with self.lock:
            cache_key, cache_count = self.cache.parse_item_to_cache(item)
            if cache_count >= self.cache_num:
                await self._save(cache_key)

    async def _save(self, cache_key):
        raise NotImplementedError


class MysqlPipeline(DBPipelineBase):

    @classmethod
    def from_settings(cls, settings):
        return cls(settings, 'mysql')

    async def _save(self, cache_key):
        table_name = self.cache.table_cache[cache_key]
        try:
            for alias in self.cache.db_alias_cache[cache_key]:
                async with get_manager(self.db_type).get(alias, ping=True) as (conn, cursor):
                    try:
                        num = await cursor.executemany(
                            self.cache.insert_sql_cache[cache_key], self.cache.item_cache[cache_key])
                        await conn.commit()
                        logger.info(f'table:{alias}->{table_name} sum:{len(self.cache.item_cache[cache_key])} ok:{num}')
                    except Exception as e:
                        await conn.rollback()
                        logger.exception(f'save data error, table:{alias}->{table_name}, err_msg:{e}')
        finally:
            self.cache.item_cache[cache_key] = []
