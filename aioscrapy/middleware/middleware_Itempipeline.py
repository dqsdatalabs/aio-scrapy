import logging

from scrapy.utils.conf import build_component_list

from .middleware import MiddlewareManager


logger = logging.getLogger(__name__)


class ItemPipelineManager(MiddlewareManager):
    component_name = 'item pipeline'

    @classmethod
    def _get_mwlist_from_settings(cls, settings):
        return build_component_list(settings.getwithbase('ITEM_PIPELINES'))

    def _add_middleware(self, pipe):
        super()._add_middleware(pipe)
        if hasattr(pipe, 'process_item'):
            self.methods['process_item'].append(pipe.process_item)

    async def process_item(self, item, spider):
        return await self._process_chain('process_item', item, spider)
