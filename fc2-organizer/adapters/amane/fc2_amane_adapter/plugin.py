"""FC2 Metadata（ffcc）Amane 来源插件 —— 宿主侧入口（合同第 8-9 节）。

这是**唯一**允许 import ``amane.plugin`` 与 ``pydantic`` 的 adapter 模块。其它模块是纯模块（不 import 二者）。
本文件只做：descriptor、配置模型、顶层导入守门、provider 与向 Amane 类型的转换；
所有规则都在纯模块中，由主进程测试直接覆盖；本文件由真实 Amane v0.15.0 宿主见证（H-01..H-15）覆盖。
"""

from amane.plugin import (
    ContentType,
    FailureReason,
    FetchOptions,
    FilmActor,
    FilmSourcePlugin,
    FilmSourceProvider,
    MediaMetadata,
    PluginContext,
    RequestError,
    SearchQuery,
    SourceCapability,
    SourceDescriptor,
    SourceError,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._core_gate import translate_core_import_error

try:
    from ._number import read_query_fields
    from ._outcome import AdapterFailure, AdapterFound, AdapterNoMatch, AdapterRecord
    from ._runtime import AdapterRuntime
    from ._settings import (
        DEFAULT_DEADLINE_SECONDS,
        METADATA_FIELDS,
        PLUGIN_ID,
        PLUGIN_NAME,
        PLUGIN_VERSION,
        descriptor_urls,
        parse_settings,
    )
except ImportError as _exc:
    _translated = translate_core_import_error(_exc)
    if _translated is None:
        raise
    raise _translated from _exc


class SourceEntry(BaseModel):
    """一个被配置的 Core 来源。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(strict=True)
    enabled: bool = Field(default=True, strict=True)
    base_url: str | None = Field(default=None, strict=True)


class Fc2MetadataConfig(BaseModel):
    """用户可配置项（合同第 11.1 节）：只暴露有真实用户价值且安全的项。"""

    model_config = ConfigDict(extra="forbid")

    sources: list[SourceEntry] | None = None
    source_deadline_seconds: float = DEFAULT_DEADLINE_SECONDS

    @field_validator("source_deadline_seconds", mode="before")
    @classmethod
    def _reject_bool(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("source_deadline_seconds must be a number")
        return value

    @model_validator(mode="after")
    def _validate_with_adapter_rules(self) -> "Fc2MetadataConfig":
        parse_settings(self.raw_settings())
        return self

    def raw_settings(self) -> dict[str, object]:
        sources = None
        if self.sources is not None:
            sources = [
                {"id": entry.id, "enabled": entry.enabled, "base_url": entry.base_url} for entry in self.sources
            ]
        return {"sources": sources, "source_deadline_seconds": self.source_deadline_seconds}


def _media_metadata(record: AdapterRecord) -> MediaMetadata:
    """表 H：中立记录 -> ``MediaMetadata``。演员性别取 ``FilmActor`` 缺省 ``unknown``（不使用 FEMALE 缺省 helper）。"""
    return MediaMetadata(
        number=record.number,
        title=record.title,
        actors=[FilmActor(name=name) for name in record.actors],
        studio=record.studio,
        publisher=record.publisher,
        release=record.release,
        runtime=record.runtime,
        tags=list(record.tags),
        plot=record.plot,
        poster_urls=list(record.poster_urls),
        thumb_urls=list(record.thumb_urls),
        external_id=record.external_id,
        source_url=record.source_url,
        extrafanart=list(record.extrafanart),
    )


class _Fc2MetadataProvider(FilmSourceProvider):
    def __init__(self, runtime: AdapterRuntime) -> None:
        self._runtime = runtime

    async def fetch(self, query: SearchQuery, options: FetchOptions | None = None) -> MediaMetadata | None:
        fields = read_query_fields(query)
        if isinstance(fields, AdapterFailure):
            outcome = fields
        else:
            outcome = await self._runtime.lookup(*fields)
        if isinstance(outcome, AdapterFound):
            return _media_metadata(outcome.record)
        if isinstance(outcome, AdapterNoMatch):
            return None
        # url / http_status 恒为 None：SourceResult 不携带状态码，不猜测；也不把任何 URL 放进 SourceError。
        raise SourceError(FailureReason(outcome.reason), detail=outcome.detail)


class Plugin(FilmSourcePlugin):
    config_model = Fc2MetadataConfig

    @classmethod
    def descriptor(cls) -> SourceDescriptor:
        return SourceDescriptor(
            id=PLUGIN_ID,
            name=PLUGIN_NAME,
            version=PLUGIN_VERSION,
            capabilities=frozenset({SourceCapability.FILM_METADATA.value}),
            content_types=frozenset({ContentType.FC2.value}),
            metadata_fields=METADATA_FIELDS,
            languages=frozenset(),
            urls=descriptor_urls(),
        )

    def build(self, context: PluginContext, config: BaseModel) -> FilmSourceProvider:
        settings = parse_settings(config.model_dump())
        runtime = AdapterRuntime(
            settings,
            context.web_client,
            request_error_types=(RequestError,),
            source_error_types=(SourceError,),
        )
        return _Fc2MetadataProvider(runtime)
