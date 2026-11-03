"""Minimal deterministic, language-neutral locator specification."""
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


class LocatorSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str
    value: str | None = None
    role: str | None = None
    name: str | None = None

    @field_validator('kind')
    @classmethod
    def allowed(cls, kind):
        if kind not in ('css', 'test_id', 'role', 'label', 'placeholder', 'text'):
            raise ValueError('Unsupported locator kind')
        return kind


def locate(page, spec):
    obj = LocatorSpec.model_validate(spec)
    if obj.kind == 'css' and obj.value:
        return page.locator(obj.value)
    if obj.kind == 'test_id' and obj.value:
        return page.get_by_test_id(obj.value)
    if obj.kind == 'role' and obj.role and obj.name:
        return page.get_by_role(obj.role, name=obj.name, exact=True)
    if obj.kind == 'label' and obj.value:
        return page.get_by_label(obj.value, exact=True)
    if obj.kind == 'placeholder' and obj.value:
        return page.get_by_placeholder(obj.value, exact=True)
    if obj.kind == 'text' and obj.value:
        return page.get_by_text(obj.value, exact=True)
    raise ValueError('Incomplete locator')


def unique(page, spec):
    """Wait for visibility, then assert exactly one match. Compatible with fake test locators."""
    loc = locate(page, spec)
    initial = loc.count()
    if initial > 1:
        raise AssertionError(f'Locator matched {initial} elements, expected exactly 1: {spec}')
    wait = getattr(loc, 'wait_for', None)
    if callable(wait):
        try:
            wait(state='visible', timeout=12000)
        except PlaywrightTimeoutError as err:
            raise AssertionError(
                f'Element not visible on current page within 12 seconds. '
                f'Current URL: {getattr(page, "url", "unknown")}. Locator: {spec}'
            ) from err
    count = loc.count()
    if count != 1:
        raise AssertionError(f'Locator matched {count} elements, expected exactly 1: {spec}')
    return loc


class Step(BaseModel):
    model_config = ConfigDict(extra='ignore')
    action: str
    locator: LocatorSpec | None = None
    target: str | None = None
    value: str | bool | int | float | None = None
    target_text: str = Field(default='', max_length=200)
    page_url: str = ''
    output: str | None = None
    observed_count: int = -1
    observed_candidates: list = Field(default_factory=list)
    locator_quality: str | None = None
    field_meta: dict[str, str | bool] = Field(default_factory=dict)

    @field_validator('action')
    @classmethod
    def action_allowed(cls, v):
        if v not in ('click', 'fill', 'select_option', 'check', 'uncheck', 'press','capture_text','capture_value','assert_text','assert_value','assert_visible'):
            raise ValueError('Unsupported action')
        return v


class Workflow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 1
    project_id: str
    name: str
    start_url: str
    steps: list[Step]
    reviewed: bool = False
    locator_fingerprint: str | None = None

    @model_validator(mode="after")
    def step_shape(self):
        for s in self.steps:
            if self.schema_version == 1 and (s.locator is None or s.target is not None):
                raise ValueError("Schema 1 steps need inline locator")
            if self.schema_version == 2 and (s.target is None or s.locator is not None):
                raise ValueError("Schema 2 steps need target and no inline locator")
        if self.schema_version == 2 and not self.locator_fingerprint:
            raise ValueError("Schema 2 needs locator fingerprint")
        return self

    @field_validator('schema_version')
    @classmethod
    def schema_version_ok(cls, v):
        if v not in (1,2):
            raise ValueError('Unknown schema version')
        return v
