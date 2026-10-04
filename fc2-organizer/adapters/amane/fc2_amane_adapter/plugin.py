"""FC2 Metadata（ffcc）Amane 来源插件 —— 宿主侧入口（合同第 8-9 节）。

这是**唯一**允许 import ``amane.plugin`` 与 ``pydantic`` 的 adapter 模块。其它模块是纯模块（不 import 二者）。
本文件只做：descriptor、配置模型、顶层导入守门、provider 骨架与向 Amane 类型的转换；
所有规则都在纯模块中，由主进程测试直接覆盖。

S1 骨架：``fetch`` 的 Core 引擎段在 S2 接入；该 checkpoint 不可发布。
"""

from amane.plugin import (
    ContentType,
    FailureReason,
    FetchOptions,
    FilmSourcePlugin,
    FilmSourceProvider,
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
    from ._bridge import AmaneHttpBridge
    from ._number import read_query_fields
    from ._outcome import AdapterFailure
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


class _Fc2MetadataProvider(FilmSourceProvider):
    def __init__(self, settings: object, bridge: object) -> None:
        self._settings = settings
        self._bridge = bridge

    async def fetch(self, query: SearchQuery, options: FetchOptions | None = None):
        fields = read_query_fields(query)
        if isinstance(fields, AdapterFailure):
            raise SourceError(FailureReason(fields.reason), detail=fields.detail)
        raise NotImplementedError("Core engine invocation is wired in S2")


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
        bridge = AmaneHttpBridge(
            context.web_client,
            request_error_types=(RequestError,),
            source_error_types=(SourceError,),
        )
        return _Fc2MetadataProvider(settings, bridge)
