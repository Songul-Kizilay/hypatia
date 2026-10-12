"""The logical input/output shape of a capability that already exists.

This module declares no authority and starts no process, exactly like
`ProductCapabilityRecord`. A schema is a *description* of what a capability's
invocation arguments and result values already mean -- never a decision, never
a validator an execution path consults, and never a grant.

SCHEMA KNOWN != INPUT AUTHORIZED. SCHEMA VALID != EXECUTION AUTHORIZED. OUTPUT
SHAPE KNOWN != OUTPUT TRUSTED. Nothing here is checked before a tool
invocation or a Kali dispatch; `ToolInvocation.__post_init__`,
`ToolResult.__post_init__`, `FilesystemRoot.locate`, and the Kali
authorization chain remain exactly as authoritative as before this module
existed, and none of them import this module or anything in it.

The value-kind vocabulary is deliberately small and does not pretend to be a
general JSON Schema. `ToolInvocation` arguments are bounded strings today --
`FREE_TEXT` and `WHOLE_NUMBER_TEXT` both describe text, because that is what
the real boundary carries; a field whose value happens to be digits is not
rewritten here as though a native integer already crossed that boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.Exceptions import ResearchError
from tools.ProductCapabilityRecord import MAX_IDENTITY_LENGTH

MAX_FIELD_NAME_LENGTH = 100
MAX_ENUM_VALUE_LENGTH = 100
MAX_ENUM_VALUES = 20

#: A declarative ceiling on how many fields one schema may list, owned by
#: this type itself -- not derived from `ToolInvocation.MAX_ARGUMENTS` (which
#: bounds argument *count*, a different fact) or `ToolResult.MAX_TOOL_VALUES`
#: (which bounds result *value* count, not declared field-family count).
MAX_SCHEMA_FIELDS = 20


class ProductCapabilityFieldKind(StrEnum):
    """Name one logical value kind this vocabulary can honestly represent.

    Four members, deliberately: every input argument and labelled result
    value in the repository today is bounded text, so every kind below is a
    flavor of text rather than a native typed alternative. Adding a fifth
    member is a decision that a fifth, provably-distinct shape exists in a
    real boundary -- not a decision this module may make for convenience.
    """

    FREE_TEXT = "free_text"
    WHOLE_NUMBER_TEXT = "whole_number_text"
    BOOLEAN_TEXT = "boolean_text"
    CLOSED_ENUM_TEXT = "closed_enum_text"


class ProductCapabilityOutputChannel(StrEnum):
    """Name which of a capability's possible result shapes a schema describes.

    `ToolResult` carries two channels today, kept apart on purpose:
    ordinary `values` (bounded, labelled `name: value` strings) and the
    separate, success-only, typed `content` field, hidden from `repr`.
    `LABELLED_VALUES` and `CONTENT_PAYLOAD` name exactly those two. A schema
    that collapsed them into one list of fields would misdescribe
    `FILESYSTEM_READ`, whose result is never a labelled value.

    A reviewed Kali operation never produces a `ToolResult` at all -- its
    own result type carries process output as a plain, unlabelled, ordered
    tuple of text lines, with no synthesized per-line key. `ORDERED_TEXT_LINES`
    names that third, structurally different shape, so a schema never
    implies a `name_1`, `name_2`, ... labelled key that the real data never
    has.
    """

    LABELLED_VALUES = "labelled_values"
    CONTENT_PAYLOAD = "content_payload"
    ORDERED_TEXT_LINES = "ordered_text_lines"


class ProductCapabilitySchemaCompleteness(StrEnum):
    """Name how much of a real contract's shape this schema honestly states.

    COMPLETE: every field this schema declares is grounded in current
    authoritative code, and nothing about the contract's shape is known that
    this schema omits.

    PARTIAL: some real, dynamic, or implementation-specific shape exists
    (for example a native-typed channel this vocabulary cannot represent
    without inventing a parallel kind, or a value-syntax constraint finer
    than this vocabulary's kinds) and is deliberately left undeclared rather
    than approximated.

    UNDECLARED: no sufficiently grounded schema exists yet for this
    capability at all; `fields` is always empty for this value.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNDECLARED = "undeclared"


@dataclass(frozen=True, slots=True)
class ProductCapabilityField:
    """Describe one stable field, or one stable repeated field family.

    `name` is the exact key for an ordinary field (for example
    `"character_count"`). For a repeated field under a `LABELLED_VALUES`
    output channel, `name` is the stable family prefix whose real keys are
    synthesized as `entry_1`, `entry_2`, ...; for a repeated field under an
    `ORDERED_TEXT_LINES` channel, there is no synthesized per-item key at
    all (the real data is a plain, unlabelled, ordered tuple), so `name` is
    only a descriptive label for that one positional family, not a prefix
    that will ever actually appear. Which one `name` means is recorded by
    the field's owning `ProductCapabilityOutputSchema.channel`, never
    guessed from the string itself.

    `max_length` bounds text length where an authoritative constant already
    enforces it (for example `ToolInvocation.MAX_ARGUMENT_LENGTH`).
    `max_numeric_value` bounds the parsed integer a `WHOLE_NUMBER_TEXT`
    field's text may encode, where an authoritative constant enforces that
    separately from text length (for example `MAX_CONTENT_BYTES`). Both are
    `None` when no such bound is currently enforced -- a fact, not a gap.
    """

    name: str
    kind: ProductCapabilityFieldKind
    required: bool
    repeated: bool = False
    max_length: int | None = None
    max_numeric_value: int | None = None
    max_repeat_count: int | None = None
    enum_values: frozenset[str] | None = None

    def __post_init__(self) -> None:
        self._require_text(self.name, "field name", MAX_FIELD_NAME_LENGTH)
        if not isinstance(self.kind, ProductCapabilityFieldKind):
            raise ResearchError("A capability field kind must be bounded.")
        for value, label in (
            (self.required, "required flag"),
            (self.repeated, "repeated flag"),
        ):
            if not isinstance(value, bool):
                raise ResearchError(f"A capability field {label} must be boolean.")
        if self.repeated and self.required:
            raise ResearchError(
                "A repeated capability field cannot also be required: a "
                "family may legitimately contain zero members."
            )
        self._validate_bound(self.max_length, "maximum length", minimum=1)
        self._validate_bound(self.max_numeric_value, "maximum numeric value", minimum=0)
        self._validate_bound(self.max_repeat_count, "maximum repeat count", minimum=1)
        if self.max_numeric_value is not None and (
            self.kind is not ProductCapabilityFieldKind.WHOLE_NUMBER_TEXT
        ):
            raise ResearchError(
                "A maximum numeric value requires a whole-number-text field."
            )
        if self.max_repeat_count is not None and not self.repeated:
            raise ResearchError("A maximum repeat count requires a repeated field.")
        self._validate_enum_values()

    def _validate_enum_values(self) -> None:
        is_closed_enum = self.kind is ProductCapabilityFieldKind.CLOSED_ENUM_TEXT
        if is_closed_enum and self.enum_values is None:
            raise ResearchError(
                "A closed-enum-text field requires its bounded value set."
            )
        if not is_closed_enum and self.enum_values is not None:
            raise ResearchError("An enum value set requires a closed-enum-text field.")
        if self.enum_values is None:
            return
        if not isinstance(self.enum_values, frozenset) or not self.enum_values:
            raise ResearchError("A capability field enum value set is invalid.")
        if len(self.enum_values) > MAX_ENUM_VALUES:
            raise ResearchError("A capability field enum value set is too large.")
        for value in self.enum_values:
            self._require_text(value, "enum value", MAX_ENUM_VALUE_LENGTH)

    @staticmethod
    def _validate_bound(value: int | None, label: str, *, minimum: int) -> None:
        if value is None:
            return
        if isinstance(value, bool) or not isinstance(value, int):
            raise ResearchError(f"A capability field {label} must be a whole number.")
        if value < minimum:
            raise ResearchError(f"A capability field {label} is out of bounds.")

    @staticmethod
    def _require_text(value: object, label: str, maximum: int) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"A capability field {label} cannot be empty.")
        if "\x00" in value or "\r" in value or "\n" in value:
            raise ResearchError(f"A capability field {label} contains control data.")
        if len(value) > maximum:
            raise ResearchError(f"A capability field {label} is too long.")


def _validate_field_tuple(
    fields: tuple[ProductCapabilityField, ...],
    completeness: ProductCapabilitySchemaCompleteness,
) -> None:
    if not isinstance(fields, tuple):
        raise ResearchError("A capability schema requires an immutable field set.")
    if not all(isinstance(field, ProductCapabilityField) for field in fields):
        raise ResearchError("A capability schema field must be bounded.")
    if len(fields) > MAX_SCHEMA_FIELDS:
        raise ResearchError("A capability schema declares too many fields.")
    names = [field.name for field in fields]
    if len(names) != len(set(names)):
        raise ResearchError("A capability schema repeated a field name.")
    if not isinstance(completeness, ProductCapabilitySchemaCompleteness):
        raise ResearchError("A capability schema completeness must be bounded.")
    if completeness is ProductCapabilitySchemaCompleteness.UNDECLARED and fields:
        raise ResearchError("An undeclared capability schema cannot carry fields.")


@dataclass(frozen=True, slots=True)
class ProductCapabilityInputSchema:
    """Describe one capability's invocation-argument shape; grant nothing."""

    fields: tuple[ProductCapabilityField, ...]
    completeness: ProductCapabilitySchemaCompleteness

    def __post_init__(self) -> None:
        _validate_field_tuple(self.fields, self.completeness)


@dataclass(frozen=True, slots=True)
class ProductCapabilityOutputSchema:
    """Describe one capability's result shape; grant nothing.

    `channel` names which `ToolResult` channel the described fields belong
    to. A `CONTENT_PAYLOAD` channel always carries zero `fields`: the
    result's real native-typed shape is not representable in this
    text-flavored vocabulary without inventing a second, parallel kind for
    a boundary this module deliberately does not reach into, so the
    channel distinction itself -- "this is not an ordinary labelled value"
    -- is the honest fact stated, and `completeness` may never claim that
    silence is `COMPLETE`.
    """

    channel: ProductCapabilityOutputChannel
    fields: tuple[ProductCapabilityField, ...]
    completeness: ProductCapabilitySchemaCompleteness

    def __post_init__(self) -> None:
        if not isinstance(self.channel, ProductCapabilityOutputChannel):
            raise ResearchError("A capability output schema channel must be bounded.")
        _validate_field_tuple(self.fields, self.completeness)
        if self.channel is ProductCapabilityOutputChannel.CONTENT_PAYLOAD:
            if self.fields:
                raise ResearchError(
                    "A content-payload output channel cannot declare "
                    "labelled-value fields."
                )
            if self.completeness is ProductCapabilitySchemaCompleteness.COMPLETE:
                raise ResearchError(
                    "A content-payload output channel cannot be marked complete "
                    "while declaring no fields."
                )
        if self.channel is ProductCapabilityOutputChannel.ORDERED_TEXT_LINES:
            if any(not field.repeated for field in self.fields):
                raise ResearchError(
                    "An ordered-text-lines output channel can declare only "
                    "repeated fields: it has no fixed, labelled companion "
                    "values -- the real data is a plain ordered tuple."
                )


@dataclass(frozen=True, slots=True)
class ProductCapabilitySchema:
    """Bind one capability identity to its input and output shape."""

    capability_identity: str
    input_schema: ProductCapabilityInputSchema
    output_schema: ProductCapabilityOutputSchema

    def __post_init__(self) -> None:
        if (
            not isinstance(self.capability_identity, str)
            or not self.capability_identity.strip()
        ):
            raise ResearchError("A capability schema identity cannot be empty.")
        if len(self.capability_identity) > MAX_IDENTITY_LENGTH:
            raise ResearchError("A capability schema identity is too long.")
        if not isinstance(self.input_schema, ProductCapabilityInputSchema):
            raise ResearchError("A capability schema requires a bounded input schema.")
        if not isinstance(self.output_schema, ProductCapabilityOutputSchema):
            raise ResearchError("A capability schema requires a bounded output schema.")
