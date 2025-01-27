
from ._aioredis import redis_manager
from ._aiomysql import mysql_manager


__all__ = ['db_manager', 'get_pool', 'get_manager']


db_manager_map = {
    'mysql': mysql_manager,
    'redis': redis_manager,
}


class DBManager:

    @staticmethod
    def get_manager(db_type):
        manager = db_manager_map.get(db_type)
        assert manager is not None, f"暂时不支持该类型数据库：{db_type}"
        return manager

    def get_pool(self, db_type, alias='default'):
        manager = self.get_manager(db_type)
        return manager.get_pool(alias)

    @staticmethod
    async def close_all():
        for manager in db_manager_map.values():
            await manager.close_all()

    @staticmethod
    async def from_settings(settings: "scrapy.settings.Setting"):
        for manager in db_manager_map.values():
            await manager.from_settings(settings)

    async def from_crawler(self, crawler):
        return await self.from_settings(crawler.settings)


db_manager = DBManager()
get_manager = db_manager.get_manager
get_pool = db_manager.get_pool
