"""Build capability schemas by projecting existing authoritative facts.

Every function here reads an already-existing source of truth and renders it
as a `ProductCapabilitySchema`; none of them re-author a bound, an argument
name, or an output key a real tool, invocation contract, result contract, or
Kali runtime type already owns. If one of those sources changes, the next
projection reflects it -- there is no copied value here to go stale.

Mirrors `ProductCapabilityCatalogDefaults` deliberately: the same two
families (local tools projected from their own registered state; Kali
operations described from existing named constants and enums, never from a
duplicated copy of the dig/curl argv) and the same rule that only the
combinations a real production process adapter actually accepts are
described.

A local-tool capability with no schema builder below (for example
`RESEARCH_STATE_SUMMARY` or `KNOWLEDGE_DOCUMENT_LIST`, which today have no
concrete `Tool` implementation at all) is simply absent from the schema
catalog -- never given a fabricated or guessed shape.

One deliberate exception to "reads an already-existing source of truth":
the content-reading local tool and its result contract are each guarded by
an existing repository-wide isolation rule that keeps the set of modules
permitted to import them narrow (composition boundaries only). This module
does not import either, and restates their argument names as literals
instead -- see `filesystem_read_schema` -- so that boundary is preserved
rather than widened by a new, merely descriptive caller.
"""

from __future__ import annotations

from research.ResearchKaliOperationExecution import (
    MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
    MAX_KALI_OPERATION_OUTPUT_LINES,
)
from research.ResearchKaliOperationPreview import (
    ResearchDnsRecordType,
    ResearchKaliOperationKind,
)
from tools.FilesystemEntryKind import FilesystemEntryKind
from tools.FilesystemListTool import MAX_SCANNED_ENTRIES as LIST_MAX_SCANNED_ENTRIES
from tools.FilesystemListTool import OFFSET_ARGUMENT as LIST_OFFSET_ARGUMENT
from tools.FilesystemListTool import PAGE_SIZE
from tools.FilesystemListTool import PATH_ARGUMENT as LIST_PATH_ARGUMENT
from tools.FilesystemMetadataTool import (
    MAX_ENTRY_NAME_LENGTH as METADATA_MAX_ENTRY_NAME_LENGTH,
)
from tools.FilesystemMetadataTool import PATH_ARGUMENT as METADATA_PATH_ARGUMENT
from tools.ProductCapabilityCatalogDefaults import (
    _EXECUTABLE_KALI_OPERATIONS,
    kali_operation_identity,
    tool_capability_identity,
)
from tools.ProductCapabilitySchema import (
    ProductCapabilityField,
    ProductCapabilityFieldKind,
    ProductCapabilityInputSchema,
    ProductCapabilityOutputChannel,
    ProductCapabilityOutputSchema,
    ProductCapabilitySchema,
    ProductCapabilitySchemaCompleteness,
)
from tools.ProductCapabilitySchemaCatalog import ProductCapabilitySchemaCatalog
from tools.TextStatisticsTool import TEXT_ARGUMENT
from tools.ToolCapability import ToolCapability
from tools.ToolInvocation import MAX_ARGUMENT_LENGTH
from tools.ToolRegistry import ToolRegistry
from tools.ToolResult import MAX_TOOL_VALUE_LENGTH

_FREE_TEXT = ProductCapabilityFieldKind.FREE_TEXT
_WHOLE_NUMBER_TEXT = ProductCapabilityFieldKind.WHOLE_NUMBER_TEXT
_BOOLEAN_TEXT = ProductCapabilityFieldKind.BOOLEAN_TEXT
_CLOSED_ENUM_TEXT = ProductCapabilityFieldKind.CLOSED_ENUM_TEXT
_COMPLETE = ProductCapabilitySchemaCompleteness.COMPLETE
_PARTIAL = ProductCapabilitySchemaCompleteness.PARTIAL
_LABELLED_VALUES = ProductCapabilityOutputChannel.LABELLED_VALUES
_CONTENT_PAYLOAD = ProductCapabilityOutputChannel.CONTENT_PAYLOAD
_ORDERED_TEXT_LINES = ProductCapabilityOutputChannel.ORDERED_TEXT_LINES

#: Every entry's kind this output can actually produce, projected from
#: `FilesystemEntryKind`'s own members rather than a hand-copied literal set.
#: `LINK` is excluded: `FilesystemRoot.locate` refuses any path that is
#: itself a link before `FilesystemMetadataTool._describe` ever runs, so a
#: link can never reach this output -- if `FilesystemEntryKind` ever gains,
#: removes, or renames a member, this set reflects that on its own.
_FILESYSTEM_METADATA_KIND_VALUES = frozenset(
    kind.value for kind in FilesystemEntryKind if kind is not FilesystemEntryKind.LINK
)


def clock_read_schema() -> ProductCapabilitySchema:
    """Describe `CLOCK_READ`: zero arguments, four fixed output values."""
    return ProductCapabilitySchema(
        capability_identity=tool_capability_identity(ToolCapability.CLOCK_READ),
        input_schema=ProductCapabilityInputSchema(fields=(), completeness=_COMPLETE),
        output_schema=ProductCapabilityOutputSchema(
            channel=_LABELLED_VALUES,
            fields=(
                ProductCapabilityField(
                    "utc_iso",
                    _FREE_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                ),
                ProductCapabilityField(
                    "utc_date",
                    _FREE_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                ),
                ProductCapabilityField(
                    "utc_time",
                    _FREE_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                ),
                ProductCapabilityField(
                    "timezone",
                    _CLOSED_ENUM_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                    enum_values=frozenset({"UTC"}),
                ),
            ),
            completeness=_COMPLETE,
        ),
    )


def text_statistics_schema() -> ProductCapabilitySchema:
    """Describe `TEXT_STATISTICS`: one required `text` argument, four counts.

    Every count is itself bounded by `MAX_ARGUMENT_LENGTH`: none of
    `character_count`, `word_count`, `line_count`, or
    `non_whitespace_character_count` can exceed the length of the bounded
    `text` argument they are counted from.
    """
    counted_fields = tuple(
        ProductCapabilityField(
            name,
            _WHOLE_NUMBER_TEXT,
            required=True,
            max_length=MAX_TOOL_VALUE_LENGTH,
            max_numeric_value=MAX_ARGUMENT_LENGTH,
        )
        for name in (
            "character_count",
            "word_count",
            "line_count",
            "non_whitespace_character_count",
        )
    )
    return ProductCapabilitySchema(
        capability_identity=tool_capability_identity(ToolCapability.TEXT_STATISTICS),
        input_schema=ProductCapabilityInputSchema(
            fields=(
                ProductCapabilityField(
                    TEXT_ARGUMENT,
                    _FREE_TEXT,
                    required=True,
                    max_length=MAX_ARGUMENT_LENGTH,
                ),
            ),
            completeness=_COMPLETE,
        ),
        output_schema=ProductCapabilityOutputSchema(
            channel=_LABELLED_VALUES,
            fields=counted_fields,
            completeness=_COMPLETE,
        ),
    )


def filesystem_list_schema() -> ProductCapabilitySchema:
    """Describe `FILESYSTEM_LIST`: a required `path`, an optional `offset`,
    five fixed page-description values, and one repeated `entry` family.

    `entry_count` is bounded by `MAX_SCANNED_ENTRIES`: the scan stops
    counting past it. `page_size` is bounded by `PAGE_SIZE`, the exact page
    budget the tool carves from the shared `ToolResult` value ceiling.
    `page_offset` has no authoritative upper bound -- the tool accepts any
    whole-number offset text, however large -- so none is stated.
    """
    return ProductCapabilitySchema(
        capability_identity=tool_capability_identity(ToolCapability.FILESYSTEM_LIST),
        input_schema=ProductCapabilityInputSchema(
            fields=(
                ProductCapabilityField(
                    LIST_PATH_ARGUMENT,
                    _FREE_TEXT,
                    required=True,
                    max_length=MAX_ARGUMENT_LENGTH,
                ),
                ProductCapabilityField(
                    LIST_OFFSET_ARGUMENT,
                    _WHOLE_NUMBER_TEXT,
                    required=False,
                    max_length=MAX_ARGUMENT_LENGTH,
                ),
            ),
            completeness=_COMPLETE,
        ),
        output_schema=ProductCapabilityOutputSchema(
            channel=_LABELLED_VALUES,
            fields=(
                ProductCapabilityField(
                    "entry_count",
                    _WHOLE_NUMBER_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                    max_numeric_value=LIST_MAX_SCANNED_ENTRIES,
                ),
                ProductCapabilityField(
                    "entries_exceeded",
                    _BOOLEAN_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                ),
                ProductCapabilityField(
                    "page_offset",
                    _WHOLE_NUMBER_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                ),
                ProductCapabilityField(
                    "page_size",
                    _WHOLE_NUMBER_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                    max_numeric_value=PAGE_SIZE,
                ),
                ProductCapabilityField(
                    "more_pages",
                    _BOOLEAN_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                ),
                ProductCapabilityField(
                    "entry",
                    _FREE_TEXT,
                    required=False,
                    repeated=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                    max_repeat_count=PAGE_SIZE,
                ),
            ),
            completeness=_COMPLETE,
        ),
    )


def filesystem_metadata_schema() -> ProductCapabilitySchema:
    """Describe `FILESYSTEM_METADATA`: a required `path`, four output facts.

    `size_bytes` is present only when `kind` is `"file"`
    (`FilesystemEntryKind.has_byte_size`), so it is optional here, never
    required.
    """
    return ProductCapabilitySchema(
        capability_identity=tool_capability_identity(
            ToolCapability.FILESYSTEM_METADATA
        ),
        input_schema=ProductCapabilityInputSchema(
            fields=(
                ProductCapabilityField(
                    METADATA_PATH_ARGUMENT,
                    _FREE_TEXT,
                    required=True,
                    max_length=MAX_ARGUMENT_LENGTH,
                ),
            ),
            completeness=_COMPLETE,
        ),
        output_schema=ProductCapabilityOutputSchema(
            channel=_LABELLED_VALUES,
            fields=(
                ProductCapabilityField(
                    "name",
                    _FREE_TEXT,
                    required=True,
                    max_length=METADATA_MAX_ENTRY_NAME_LENGTH,
                ),
                ProductCapabilityField(
                    "kind",
                    _CLOSED_ENUM_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                    enum_values=_FILESYSTEM_METADATA_KIND_VALUES,
                ),
                ProductCapabilityField(
                    "modified_utc",
                    _FREE_TEXT,
                    required=True,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                ),
                ProductCapabilityField(
                    "size_bytes",
                    _WHOLE_NUMBER_TEXT,
                    required=False,
                    max_length=MAX_TOOL_VALUE_LENGTH,
                ),
            ),
            completeness=_COMPLETE,
        ),
    )


#: `FILESYSTEM_READ`'s own argument names, restated as literals rather than
#: imported. An existing repository-wide isolation rule deliberately keeps
#: the set of modules that may import the content-reading tool and its
#: content-result contract narrow (composition boundaries only); reaching
#: into either from this descriptive module would widen that boundary, so
#: these three names -- and the numeric ceilings that contract enforces --
#: are intentionally not read from there. Each local filesystem tool
#: already keeps its own same-valued `PATH_ARGUMENT` constant rather than
#: sharing one, so restating these three names here follows that existing
#: convention rather than breaking it.
_READ_PATH_ARGUMENT = "path"
_READ_OFFSET_ARGUMENT = "offset"
_READ_MAX_BYTES_ARGUMENT = "max_bytes"


def filesystem_read_schema() -> ProductCapabilitySchema:
    """Describe `FILESYSTEM_READ`: three required bounded arguments, and a
    result carried entirely by the separate `content` channel.

    Only presence, order-independence, and the generic `ToolInvocation`
    string-boundary length apply to the two numeric arguments here: the
    tighter authoritative byte-count and offset ceilings exist on the
    content-reading tool and its result contract, which this module
    deliberately does not import (see `_READ_PATH_ARGUMENT` above), so
    `PARTIAL` is honest for both the input and the output here -- restating
    those ceilings would mean duplicating a value from a boundary this
    schema layer does not reach into, which is a second source of truth,
    not a more complete description.
    """
    return ProductCapabilitySchema(
        capability_identity=tool_capability_identity(ToolCapability.FILESYSTEM_READ),
        input_schema=ProductCapabilityInputSchema(
            fields=(
                ProductCapabilityField(
                    _READ_PATH_ARGUMENT,
                    _FREE_TEXT,
                    required=True,
                    max_length=MAX_ARGUMENT_LENGTH,
                ),
                ProductCapabilityField(
                    _READ_OFFSET_ARGUMENT,
                    _WHOLE_NUMBER_TEXT,
                    required=True,
                    max_length=MAX_ARGUMENT_LENGTH,
                ),
                ProductCapabilityField(
                    _READ_MAX_BYTES_ARGUMENT,
                    _WHOLE_NUMBER_TEXT,
                    required=True,
                    max_length=MAX_ARGUMENT_LENGTH,
                ),
            ),
            completeness=_PARTIAL,
        ),
        output_schema=ProductCapabilityOutputSchema(
            channel=_CONTENT_PAYLOAD,
            fields=(),
            completeness=_PARTIAL,
        ),
    )


_LOCAL_TOOL_SCHEMA_BUILDERS = {
    ToolCapability.CLOCK_READ: clock_read_schema,
    ToolCapability.TEXT_STATISTICS: text_statistics_schema,
    ToolCapability.FILESYSTEM_LIST: filesystem_list_schema,
    ToolCapability.FILESYSTEM_METADATA: filesystem_metadata_schema,
    ToolCapability.FILESYSTEM_READ: filesystem_read_schema,
}


def local_tool_schema_records(
    registry: ToolRegistry,
) -> tuple[ProductCapabilitySchema, ...]:
    """Describe every registered local tool that has an honest schema.

    Reads `registry.registered_capabilities` -- never a second, separately
    maintained list -- so a capability absent from the supplied registry is
    correctly absent here too. A registered capability with no entry in
    `_LOCAL_TOOL_SCHEMA_BUILDERS` (none exist today) is skipped rather than
    given a guessed shape.
    """
    records = []
    for capability in registry.registered_capabilities:
        builder = _LOCAL_TOOL_SCHEMA_BUILDERS.get(capability)
        if builder is not None:
            records.append(builder())
    return tuple(records)


#: `ResearchKaliOperationPreview.__post_init__` bounds
#: `MAX_KALI_OPERATION_HOSTNAME_CHARACTERS` against the *normalized* hostname
#: (`hostname.strip().lower().removesuffix(".")`), never the raw argument
#: text -- `.strip()` can discard arbitrarily much leading/trailing
#: whitespace, so the raw text this field actually receives has no
#: authoritative length ceiling of its own. Stating `max_length` here would
#: misdescribe a bound on a normalized value as a bound on the raw one, so
#: `hostname` deliberately carries no `max_length`, and both Kali input
#: schemas below are `PARTIAL` rather than `COMPLETE` for exactly this
#: reason.
_KALI_HOSTNAME_FIELD = ProductCapabilityField("hostname", _FREE_TEXT, required=True)


def _dns_record_lookup_input_schema() -> ProductCapabilityInputSchema:
    return ProductCapabilityInputSchema(
        fields=(
            _KALI_HOSTNAME_FIELD,
            ProductCapabilityField(
                "dns_record_type",
                _CLOSED_ENUM_TEXT,
                required=True,
                enum_values=frozenset(member.value for member in ResearchDnsRecordType),
            ),
        ),
        completeness=_PARTIAL,
    )


def _https_header_lookup_input_schema() -> ProductCapabilityInputSchema:
    """`resolved_address` is a parsed, valid IPv4/IPv6 literal
    (`ResearchKaliOperationPreview.__post_init__` calls `ipaddress.ip_address`
    on it); no authoritative length bound exists for it today, and "valid IP
    address syntax" is not a fact this vocabulary's closed kinds can state,
    so this input schema is marked `PARTIAL` rather than claiming more than
    `hostname` and presence can honestly support.
    """
    return ProductCapabilityInputSchema(
        fields=(
            _KALI_HOSTNAME_FIELD,
            ProductCapabilityField("resolved_address", _FREE_TEXT, required=True),
        ),
        completeness=_PARTIAL,
    )


def _kali_operation_output_schema() -> ProductCapabilityOutputSchema:
    """Describe only the one logical output every reviewed Kali operation
    shares: a bounded, ordered family of untrusted stdout lines.

    This is `ORDERED_TEXT_LINES`, not `LABELLED_VALUES`: a Kali operation
    never produces a `ToolResult` at all, and its own result type's
    `stdout_lines` is a plain, unlabelled, positionally-ordered tuple --
    there is no synthesized `stdout_line_1`, `stdout_line_2`, ... key for
    any line, so this channel must not claim one exists.

    `exit_code`, `timed_out`, and `stderr_lines`
    (`ResearchKaliOperationProcessResult`) are deliberately left undeclared:
    they are execution mechanics the authority chain already owns, not the
    operation's logical result, and restating them here would blur that
    line rather than sharpen it. Hence `PARTIAL`, not `COMPLETE`.
    """
    return ProductCapabilityOutputSchema(
        channel=_ORDERED_TEXT_LINES,
        fields=(
            ProductCapabilityField(
                "stdout_line",
                _FREE_TEXT,
                required=False,
                repeated=True,
                max_length=MAX_KALI_OPERATION_OUTPUT_LINE_CHARACTERS,
                max_repeat_count=MAX_KALI_OPERATION_OUTPUT_LINES,
            ),
        ),
        completeness=_PARTIAL,
    )


_KALI_INPUT_SCHEMA_BY_KIND = {
    ResearchKaliOperationKind.DNS_RECORD_LOOKUP: _dns_record_lookup_input_schema,
    ResearchKaliOperationKind.HTTPS_HEADER_LOOKUP: _https_header_lookup_input_schema,
}


def kali_operation_schema_records() -> tuple[ProductCapabilitySchema, ...]:
    """Describe every Kali operation/transport pair a real production
    process adapter accepts -- reusing the exact combinations
    `ProductCapabilityCatalogDefaults._EXECUTABLE_KALI_OPERATIONS` already
    enumerates, never a second, independently maintained copy of that list.
    """
    records = []
    for operation_kind, transport in _EXECUTABLE_KALI_OPERATIONS:
        records.append(
            ProductCapabilitySchema(
                capability_identity=kali_operation_identity(operation_kind, transport),
                input_schema=_KALI_INPUT_SCHEMA_BY_KIND[operation_kind](),
                output_schema=_kali_operation_output_schema(),
            )
        )
    return tuple(records)


def default_product_capability_schema_catalog(
    tool_registry: ToolRegistry,
) -> ProductCapabilitySchemaCatalog:
    """Build the one catalog describing every currently-schematized capability.

    Takes an already-constructed `ToolRegistry` rather than building one, so
    this function never decides which local tools exist -- that decision
    stays exactly where it already lives, in `ToolRuntime`.
    """
    return ProductCapabilitySchemaCatalog(
        local_tool_schema_records(tool_registry) + kali_operation_schema_records()
    )
